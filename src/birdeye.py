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
            
    async def enrich_wallet(self, wallet: SmartWallet) -> SmartWallet:
        """
        Enrich a SmartWallet with data from Birdeye.
        updates the wallet object in-place and returns it.
        """
        url = f"https://birdeye.so/solana/wallet-analyzer/{wallet.wallet_address}"
        logger.info(f"Analyzing wallet on Birdeye: {wallet.get_short_address()}")
        
        context = await self.browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_async(page)
        
        try:
            # Navigate with a generous timeout
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            
            # Wait for key elements to appear (Birdeye is slow/dynamic)
            # Wait for key elements to appear (Birdeye is slow/dynamic)
            try:
                # Wait for "Win Rate" text to appear
                await page.wait_for_selector("text=Win Rate", timeout=15000)
                
                # Switch to 7D view
                try:
                    logger.debug("Switching to 7D view...")
                    # Try specific time filter button
                    await page.click("button:has-text('7D'), div[role='button']:has-text('7D')", timeout=5000)
                    await asyncio.sleep(2) # Wait for data to update
                except Exception as e:
                    logger.warning(f"Could not set 7D filter for {wallet.get_short_address()}: {e}")

            except PlaywrightTimeout:
                logger.warning(f"Birdeye timeout for {wallet.get_short_address()}")
                return wallet

            # Extract data using robust JS evaluation
            data = await page.evaluate("""() => {
                const getTextAfterLabel = (label) => {
                    // Find all elements containing the label
                    const candidates = Array.from(document.querySelectorAll('*'))
                        .filter(el => el.textContent.trim() === label);
                    
                    if (!candidates.length) return null;
                    
                    const el = candidates[0];
                    
                    // Birdeye structure: usually Label is in a <p> or <div>, Value is next sibling or child of parent's next sibling
                    // Check next sibling
                    if (el.nextElementSibling && el.nextElementSibling.textContent.trim()) {
                        return el.nextElementSibling.textContent.trim();
                    }
                    
                    // Check parent's next sibling (common in grid layouts)
                    if (el.parentElement && el.parentElement.nextElementSibling) {
                        return el.parentElement.nextElementSibling.textContent.trim();
                    }
                    
                    return null;
                };

                return {
                    winRate: getTextAfterLabel('Win Rate'),
                    realized: getTextAfterLabel('Realized'),
                    unrealized: getTextAfterLabel('Unrealized'),
                    avgHold: getTextAfterLabel('Avg Holding Duration')
                };
            }""")
            
            logger.debug(f"Birdeye data for {wallet.get_short_address()}: {data}")
            
            # Parse and assign values
            if data['winRate']:
                # Format: "10.77%" -> 0.1077 or just keep as float 10.77
                # Our models use float, assuming 0.0-1.0 or 0-100. Let's use 0-1
                wr_str = data['winRate'].replace('%', '').strip()
                try:
                    wallet.win_rate_7d = float(wr_str) / 100.0
                except:
                    pass
                    
            if data['avgHold']:
                wallet.avg_holding_time = data['avgHold']
                
            if data['realized']:
                val_str = data['realized'].split('(')[0].strip()
                wallet.realized_pnl = self._parse_birdeye_currency(val_str)
                
            if data['unrealized']:
                wallet.unrealized_pnl = self._parse_birdeye_currency(data['unrealized'])
                
            return wallet
            
        except Exception as e:
            logger.error(f"Error enriching wallet {wallet.get_short_address()}: {e}")
            return wallet
        finally:
            await context.close()
            
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
