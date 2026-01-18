import asyncio
import logging
from typing import Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_async

from .models import SmartWallet

logger = logging.getLogger("wallet_tracker")

class BirdeyeScraper:
    """
    Scraper for Birdeye wallet analysis.
    Target URL: https://birdeye.so/solana/wallet-analyzer/{address}
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.playwright = None
        self.browser = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        headless = self.config["scraping"].get("headless", True)
        
        # Launch options for stability
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def enrich_wallet(self, wallet: SmartWallet, max_retries: int = 2) -> SmartWallet:
        """
        Enrich a SmartWallet with data from Birdeye (all 7D and 30D metrics).
        Includes retry logic for rate limiting.
        """
        url = f"https://birdeye.so/solana/wallet-analyzer/{wallet.wallet_address}"
        
        # Extraction script that looks for TIMEFRAME-PREFIXED labels
        def make_extract_js(prefix: str) -> str:
            """Generate JS extraction for a specific timeframe prefix (7D, 30D)."""
            return f"""() => {{
                const text = document.body.innerText;
                
                // Win Rate - appears after "WIN RATE" label
                const winRateMatch = text.match(/WIN\\s*RATE[^\\d]*?(\\d+\\.?\\d*)\\s*%/i);
                const winRate = winRateMatch ? winRateMatch[1] + '%' : null;
                
                // {prefix} Realized - currency can be "+$ 2.3K" (space after $)
                const realizedMatch = text.match(/{prefix}\\s*Realized[\\s\\S]*?([+-]?\\$\\s*[\\d.,]+\\s*[KMB]?)/i);
                const realized = realizedMatch ? realizedMatch[1].replace(/\\s/g, '') : null;
                
                // {prefix} Unrealized
                const unrealizedMatch = text.match(/{prefix}\\s*Unrealized[\\s\\S]*?([+-]?\\$\\s*[\\d.,]+\\s*[KMB]?)/i);
                const unrealized = unrealizedMatch ? unrealizedMatch[1].replace(/\\s/g, '') : null;
                
                // {prefix} Total PNL (fallback)
                const totalPnlMatch = text.match(/{prefix}\\s*Total\\s*PNL[\\s\\S]*?([+-]?\\$\\s*[\\d.,]+\\s*[KMB]?)/i);
                const totalPnl = totalPnlMatch ? totalPnlMatch[1].replace(/\\s/g, '') : null;
                
                // {prefix} Avg Holding Duration
                const holdMatch = text.match(/{prefix}\\s*Avg\\s*Holding\\s*Duration[\\s\\S]*?(\\d+\\s*[smhdw]?)/i);
                const avgHold = holdMatch ? holdMatch[1].replace(/\\s/g, '') : null;
                
                return {{ 
                    winRate, 
                    realized: realized || totalPnl,
                    unrealized, 
                    avgHold
                }};
            }}"""
        
        EXTRACT_7D_JS = make_extract_js("7D")
        EXTRACT_30D_JS = make_extract_js("30D")
        
        for attempt in range(max_retries + 1):
            context = None
            try:
                if attempt > 0:
                    backoff = 5 * (2 ** (attempt - 1))  # 5s, 10s
                    logger.warning(f"Retry {attempt}/{max_retries} for {wallet.get_short_address()}, waiting {backoff}s...")
                    await asyncio.sleep(backoff)
                
                logger.debug(f"Analyzing wallet on Birdeye: {wallet.get_short_address()} (attempt {attempt + 1})")
                
                context = await self.browser.new_context(
                    viewport={"width": 1400, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                await stealth_async(page)
                
                # Navigate and wait for page load
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for Trading PNL tab content
                await page.wait_for_selector("text=TRADING PNL", timeout=20000)
                await asyncio.sleep(3)
                
                # --- Extract 7D Metrics ---
                try:
                    await page.click("button:has-text('7D')", timeout=5000)
                    await asyncio.sleep(4)
                    
                    d7 = await page.evaluate(EXTRACT_7D_JS)
                    logger.debug(f"7D raw data: {d7}")
                    
                    if d7.get('winRate'):
                        wallet.win_rate_7d = self._parse_percentage(d7['winRate'])
                    if d7.get('realized'):
                        wallet.realized_pnl_7d = self._parse_birdeye_currency(d7['realized'])
                    if d7.get('unrealized'):
                        wallet.unrealized_pnl_7d = self._parse_birdeye_currency(d7['unrealized'])
                    if d7.get('avgHold'):
                        wallet.avg_holding_time_7d = d7['avgHold']
                except Exception as e:
                    logger.warning(f"7D extraction failed for {wallet.get_short_address()}: {e}")
                
                # --- Extract 30D Metrics ---
                try:
                    await page.click("button:has-text('30D')", timeout=5000)
                    await asyncio.sleep(4)
                    
                    d30 = await page.evaluate(EXTRACT_30D_JS)
                    logger.debug(f"30D raw data: {d30}")
                    
                    if d30.get('winRate'):
                        wallet.win_rate_30d = self._parse_percentage(d30['winRate'])
                    if d30.get('realized'):
                        wallet.realized_pnl_30d = self._parse_birdeye_currency(d30['realized'])
                    if d30.get('unrealized'):
                        wallet.unrealized_pnl_30d = self._parse_birdeye_currency(d30['unrealized'])
                    if d30.get('avgHold'):
                        wallet.avg_holding_time_30d = d30['avgHold']
                except Exception as e:
                    logger.warning(f"30D extraction failed for {wallet.get_short_address()}: {e}")
                
                # Success - return enriched wallet
                return wallet
                
            except PlaywrightTimeout as e:
                logger.warning(f"Timeout for {wallet.get_short_address()}: {e}")
                if attempt >= max_retries:
                    logger.error(f"All retries failed for {wallet.get_short_address()}")
                    return wallet
            except Exception as e:
                logger.error(f"Error enriching wallet {wallet.get_short_address()}: {e}")
                if attempt >= max_retries:
                    return wallet
            finally:
                if context:
                    await context.close()
        
        return wallet
            
    def _parse_percentage(self, text: str) -> Optional[float]:
        try:
            if not text: return None
            val = float(text.replace('%', '').strip())
            return val / 100.0
        except:
            return None
            
    def _parse_birdeye_currency(self, text: str) -> Optional[float]:
        """Parse Birdeye currency format (e.g. -$36.18K, +$99.13K)."""
        try:
            if not text:
                return None
            # Clean string
            text = text.replace('+', '').replace('$', '').replace(',', '').strip()
            multiplier = 1.0
            
            if 'K' in text.upper():
                multiplier = 1000.0
                text = text.upper().replace('K', '')
            elif 'M' in text.upper():
                multiplier = 1000000.0
                text = text.upper().replace('M', '')
            elif 'B' in text.upper():
                multiplier = 1000000000.0
                text = text.upper().replace('B', '')
                
            return float(text) * multiplier
        except:
            return None
