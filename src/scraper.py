"""
DEX Screener Scraper for Smart Wallet Tracker.

Scrapes trending tokens and top traders from DEX Screener using
Playwright with stealth measures to avoid bot detection.

URL Patterns:
    - Gainers: https://dexscreener.com/gainers/solana
    - Token page: https://dexscreener.com/solana/{token_address}

Selectors:
    - Token rows: a.ds-dex-table-row or a[href^="/solana/"]
    - Top Traders tab: button with "Top Traders" text
    - Wallet links: a[href*="solscan.io/account/"]

Known Issues:
    - Page uses WebSocket for real-time updates
    - Dynamic class names (use attribute selectors)
    - Some pages may have loading delays
"""

import asyncio
import random
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
    TimeoutError as PlaywrightTimeout
)
from playwright_stealth import stealth_async

from .models import Token, Trader
from .utils import (
    extract_token_from_dexscreener_url,
    extract_wallet_from_solscan_url,
    load_config,
    parse_currency,
    parse_percentage,
    parse_txn_count,
    save_debug_html,
    setup_logging
)

# Module logger
logger = setup_logging("scraper")

# DEX Screener URLs
BASE_URL = "https://dexscreener.com"
GAINERS_URL = f"{BASE_URL}/gainers/solana"

# Configurable selectors (for easy updates if DEX Screener changes)
SELECTORS = {
    "token_row": "a.ds-dex-table-row, a[href^='/solana/']",
    "top_traders_tab": "button:has-text('Top Traders')",
    "trader_row": "div[class*='custom-'] > div",  # Dynamic classes
    "solscan_link": "a[href*='solscan.io/account/']",
    "loading_indicator": "text=Loading",
    "pair_info": "[class*='ds-dex-table-row']",
}


class DexScreenerScraper:
    """
    Scraper for DEX Screener with stealth browser automation.
    
    Uses Playwright with stealth plugin to avoid bot detection.
    Implements polite scraping with random delays between requests.
    
    Attributes:
        config: Configuration dictionary
        browser: Playwright browser instance
        context: Browser context with stealth settings
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize scraper with configuration.
        
        Args:
            config: Optional config dict (loads from file if not provided)
        """
        self.config = config or load_config()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._playwright: Optional[Playwright] = None
        
    async def __aenter__(self) -> "DexScreenerScraper":
        """Async context manager entry - starts browser."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit - closes browser."""
        await self.close()
        
    async def start(self) -> None:
        """
        Start the browser with stealth settings.
        
        Configures browser to evade bot detection:
        - Random viewport size
        - Realistic user agent
        - Disabled automation flags
        """
        logger.info("Starting stealth browser...")
        
        self._playwright = await async_playwright().start()
        
        # Launch with settings to avoid detection
        headless = self.config["scraping"].get("headless", True)
        self.browser = await self._playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
            ]
        )
        
        # Create context with realistic settings
        viewport_width = random.randint(1200, 1920)
        viewport_height = random.randint(800, 1080)
        
        self.context = await self.browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
        )
        
        logger.info(f"Browser started with viewport {viewport_width}x{viewport_height}")
        
    async def close(self) -> None:
        """Close browser and cleanup resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")
        
    async def _new_stealth_page(self) -> Page:
        """
        Create a new page with stealth settings applied.
        
        Returns:
            Playwright Page with stealth modifications
        """
        if not self.context:
            raise RuntimeError("Browser not started. Call start() first.")
            
        page = await self.context.new_page()
        await stealth_async(page)
        return page
        
    async def _random_delay(self) -> None:
        """Apply random delay between requests to be polite."""
        delay_min = self.config["scraping"]["delay_min_seconds"]
        delay_max = self.config["scraping"]["delay_max_seconds"]
        delay = random.uniform(delay_min, delay_max)
        logger.debug(f"Waiting {delay:.1f}s before next request...")
        await asyncio.sleep(delay)
        
    async def _wait_for_content(
        self, 
        page: Page, 
        selector: str, 
        timeout_ms: Optional[int] = None
    ) -> bool:
        """
        Wait for content to load on page.
        
        Args:
            page: Playwright page
            selector: CSS selector to wait for
            timeout_ms: Timeout in milliseconds
            
        Returns:
            True if content loaded, False if timeout
        """
        timeout = timeout_ms or self.config["scraping"]["page_load_timeout_ms"]
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return True
        except PlaywrightTimeout:
            logger.warning(f"Timeout waiting for selector: {selector}")
            return False
            
    async def get_trending_tokens(
        self,
        min_volume: Optional[float] = None,
        min_gain: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> List[Token]:
        """
        Scrape trending/gainer tokens from DEX Screener.
        
        Navigates to the Solana gainers page and extracts tokens
        that meet the volume and price gain criteria.
        
        Args:
            min_volume: Minimum 24h volume in USD (default from config)
            min_gain: Minimum price gain percentage (default from config)
            max_tokens: Maximum tokens to return (default from config)
            
        Returns:
            List of Token objects meeting criteria
            
        Raises:
            RuntimeError: If browser not started
        """
        min_volume = min_volume or self.config["filters"]["min_token_volume"]
        min_gain = min_gain or self.config["filters"]["min_price_gain_pct"]
        max_tokens = max_tokens or self.config["scraping"]["max_tokens_per_run"]
        
        logger.info(f"Scraping gainers (min_volume=${min_volume:,}, min_gain={min_gain}%)")
        
        page = await self._new_stealth_page()
        tokens: List[Token] = []
        
        try:
            # Navigate to gainers page
            logger.info(f"Navigating to {GAINERS_URL}")
            await page.goto(GAINERS_URL, wait_until="networkidle")
            
            # Wait for token rows to load
            await asyncio.sleep(3)  # Initial wait for JS content
            
            if not await self._wait_for_content(page, SELECTORS["token_row"]):
                # Save debug HTML if loading fails
                html = await page.content()
                save_debug_html(html, "gainers_failed")
                logger.error("Failed to load gainers page")
                return tokens
                
            # Scroll to load more content
            await self._scroll_page(page, scroll_count=3)
            
            # Extract token data
            rows = await page.query_selector_all(SELECTORS["token_row"])
            logger.info(f"Found {len(rows)} token rows")
            
            for row in rows[:max_tokens * 2]:  # Get extra to filter
                token = await self._parse_token_row(row)
                if token and token.meets_criteria(min_volume, min_gain):
                    tokens.append(token)
                    if len(tokens) >= max_tokens:
                        break
                        
            logger.info(f"Extracted {len(tokens)} tokens meeting criteria")
            
        except Exception as e:
            logger.error(f"Error scraping gainers: {e}")
            # Save debug HTML on error
            try:
                html = await page.content()
                save_debug_html(html, "gainers_error")
            except:
                pass
                
        finally:
            await page.close()
            
        return tokens
        
    async def _parse_token_row(self, row) -> Optional[Token]:
        """
        Parse a token row element to extract Token data.
        
        DEX Screener table structure (column indices):
            0: Rank (#1, #2, etc.)
            1: Token name
            2: Separator (/)
            3: Base token (SOL)
            4: Token name again
            5: Age (30, 5d, etc.)
            6: Price
            7: Age again
            8: Makers count
            9: Volume 24h (e.g., $7.3M)
            10: Txns count
            11: Price change (various timeframes)
            12-14: More price changes (5m, 1h, 6h, 24h)
        
        Args:
            row: Playwright element handle for token row
            
        Returns:
            Token object or None if parsing fails
        """
        try:
            # Get token address from href
            href = await row.get_attribute("href")
            address = extract_token_from_dexscreener_url(href)
            if not address:
                return None
            
            # Try to get data from specific column selectors (more reliable)
            volume = 0.0
            price_change = 0.0
            name = "Unknown"
            symbol = "Unknown"
            
            # Get volume from the volume column
            volume_cell = await row.query_selector(".ds-dex-table-row-col-volume")
            if volume_cell:
                volume_text = await volume_cell.inner_text()
                parsed_volume = parse_currency(volume_text)
                if parsed_volume is not None:
                    volume = parsed_volume
            
            # Get 24h price change from the specific column
            price_cell = await row.query_selector(".ds-dex-table-row-col-price-change-h24")
            if price_cell:
                price_text = await price_cell.inner_text()
                parsed_price = parse_percentage(price_text)
                if parsed_price is not None:
                    price_change = parsed_price
            
            # Get token name/symbol from first cells
            text_content = await row.inner_text()
            lines = [line.strip() for line in text_content.split("\n") if line.strip()]
            
            # Skip rank (e.g., #1), get the token name
            for line in lines:
                if not line.startswith("#") and line != "/" and line != "SOL":
                    name = line
                    symbol = name.split("/")[0] if "/" in name else name
                    break
            
            # Fallback: if column selectors failed, try text parsing
            if volume == 0.0:
                for line in lines:
                    if "$" in line and ("K" in line.upper() or "M" in line.upper() or "B" in line.upper()):
                        parsed = parse_currency(line)
                        if parsed and parsed > volume:
                            volume = parsed
            
            if price_change == 0.0:
                # Look for percentage values - typically the last few are price changes
                percentages = []
                for line in lines:
                    if "%" in line:
                        parsed = parse_percentage(line)
                        if parsed is not None:
                            percentages.append(parsed)
                # Take the largest percentage as 24h change (gainers have high % gains)
                if percentages:
                    price_change = max(percentages)
            
            logger.debug(f"Parsed token: {symbol} vol=${volume:,.0f} change={price_change:.1f}%")
            
            return Token(
                address=address,
                name=name,
                symbol=symbol,
                volume_24h=volume,
                price_change_24h=price_change,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse token row: {e}")
            return None
            
    async def _scroll_page(self, page: Page, scroll_count: int = 3) -> None:
        """
        Scroll page to trigger lazy loading.
        
        Args:
            page: Playwright page
            scroll_count: Number of scroll iterations
        """
        for i in range(scroll_count):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.5)
            
    async def get_top_traders(
        self,
        token_address: str,
        limit: Optional[int] = None
    ) -> List[Trader]:
        """
        Scrape top traders for a specific token.
        
        Navigates to the token page, clicks the "Top Traders" tab,
        and extracts trader wallet addresses and performance data.
        
        Args:
            token_address: Solana token contract address
            limit: Maximum traders to return (default from config)
            
        Returns:
            List of Trader objects
            
        Known Issues:
            - Top Traders tab may need time to load
            - Some wallets may have incomplete data
        """
        limit = limit or self.config["scraping"]["top_traders_limit"]
        token_url = f"{BASE_URL}/solana/{token_address}"
        
        logger.info(f"Scraping top traders for {token_address[:16]}...")
        
        page = await self._new_stealth_page()
        traders: List[Trader] = []
        
        try:
            # Navigate to token page (use domcontentloaded - faster than networkidle)
            logger.debug(f"Navigating to {token_url}")
            await page.goto(token_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)  # Wait for JavaScript to render content
            
            # Scroll down to make tabs visible (they're below the chart)
            await page.evaluate("window.scrollBy(0, 400)")
            await asyncio.sleep(1)
            
            # Click Top Traders tab
            tab_clicked = await self._click_top_traders_tab(page)
            if not tab_clicked:
                logger.warning(f"Could not find Top Traders tab for {token_address}")
                # Save debug HTML for inspection
                html = await page.content()
                save_debug_html(html, f"no_tab_{token_address[:16]}")
                await page.close()
                return traders
            
            # Wait for Solscan links to appear (confirms data loaded)
            logger.debug("Waiting for trader data to load...")
            try:
                await page.wait_for_selector(
                    SELECTORS["solscan_link"], 
                    timeout=10000
                )
            except PlaywrightTimeout:
                logger.warning(f"Trader data did not load for {token_address[:16]}")
                html = await page.content()
                save_debug_html(html, f"no_data_{token_address[:16]}")
                await page.close()
                return traders
            
            # Additional wait for all rows to render
            await asyncio.sleep(2)
            
            # Find all Solscan wallet links
            wallet_elements = await page.query_selector_all(SELECTORS["solscan_link"])
            logger.info(f"Found {len(wallet_elements)} wallet links")
            
            # Extract trader data
            processed_wallets = set()
            for element in wallet_elements:
                trader = await self._parse_trader_element(
                    page, element, token_address
                )
                if trader and trader.wallet_address not in processed_wallets:
                    traders.append(trader)
                    processed_wallets.add(trader.wallet_address)
                    if len(traders) >= limit:
                        break
                        
            logger.info(f"Extracted {len(traders)} traders for {token_address[:16]}")
            
        except Exception as e:
            logger.error(f"Error scraping traders for {token_address}: {e}")
            try:
                html = await page.content()
                save_debug_html(html, f"traders_error_{token_address[:16]}")
            except:
                pass
                
        finally:
            await page.close()
            
        return traders
        
    async def _click_top_traders_tab(self, page: Page) -> bool:
        """
        Click the Top Traders tab on a token page.
        
        The tab is located below the price chart in a horizontal tab bar.
        Tabs include: Transactions, Top Traders, KOLs, Holders.
        
        Args:
            page: Playwright page
            
        Returns:
            True if clicked successfully, False otherwise
        """
        try:
            # Try multiple selectors for the tab (in order of reliability)
            selectors_to_try = [
                # Most reliable: text-based selector
                "button:has-text('Top Traders')",
                # Alternative: partial text match
                "text=Top Traders",
                # Chakra UI button class (site uses Chakra)
                ".chakra-button:has-text('Top Traders')",
                # Role-based selector
                "[role='tab']:has-text('Top Traders')",
            ]
            
            for selector in selectors_to_try:
                try:
                    logger.debug(f"Trying selector: {selector}")
                    element = await page.wait_for_selector(selector, timeout=8000)
                    if element:
                        # Scroll element into view first
                        await element.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        await element.click()
                        logger.info("Successfully clicked Top Traders tab")
                        await asyncio.sleep(2)  # Wait for tab content to load
                        return True
                except PlaywrightTimeout:
                    logger.debug(f"Selector not found: {selector}")
                    continue
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
                    
            logger.warning("Could not find Top Traders tab with any selector")
            return False
            
        except Exception as e:
            logger.error(f"Failed to click Top Traders tab: {e}")
            return False
            
    async def _parse_trader_element(
        self,
        page: Page,
        wallet_element,
        token_address: str
    ) -> Optional[Trader]:
        """
        Parse trader data from wallet link element and surrounding context.
        
        DEX Screener Top Traders table structure:
        Row text pattern: "# | rank | walletAbbrev | $ | bought_usd | bought_tokens | / | buy_txns | txns | $ | sold_usd | sold_tokens | / | sell_txns | txns | $ | pnl_usd | unrealized | balance"
        
        Example: "# | 1 | 65G...ADu | $ | 854 | 774.0K | / | 1 | txns | $ | 86.6K | 10.6M | / | 32 | txns | $ | 85.8K | - | Unknown"
        
        Dollar amounts appear in this order:
        1. Bought USD
        2. Sold USD  
        3. PNL USD
        
        Args:
            page: Playwright page
            wallet_element: Element containing Solscan link
            token_address: Token being analyzed
            
        Returns:
            Trader object or None if parsing fails
        """
        try:
            # Extract wallet address from Solscan link
            href = await wallet_element.get_attribute("href")
            wallet_address = extract_wallet_from_solscan_url(href)
            if not wallet_address:
                return None
                
            # Try to find parent row containing the full trader data
            # We need to go up the DOM tree until we find a parent that contains
            # the rank (#), wallet, and at least 2-3 dollar amounts (bought, sold, pnl)
            parent = await wallet_element.evaluate_handle(
                """el => {
                    let current = el;
                    for (let i = 0; i < 10 && current; i++) {
                        current = current.parentElement;
                        if (!current) break;
                        const text = current.innerText || '';
                        // Look for a parent that contains rank (#) and at least 2 dollar amounts
                        const hasDollar = (text.match(/\\$/g) || []).length >= 2;
                        const hasRank = text.includes('#');
                        if (hasDollar && hasRank) {
                            return current;
                        }
                    }
                    // Fallback: return the 5th parent level
                    current = el;
                    for (let i = 0; i < 5 && current; i++) {
                        current = current.parentElement;
                    }
                    return current;
                }"""
            )
            
            pnl = 0.0
            bought = 0.0
            sold = 0.0
            txn_count = 0
            
            # Extract data from the parent row
            if parent:
                text = await parent.evaluate("el => el.innerText")
                
                # Verify this is actually a trader row
                # Must contain rank (#) and financial data ($)
                if "#" not in text or "$" not in text:
                    logger.debug(f"Skipping link - not a trader row (text preview: {text[:50]}...)")
                    return None
                
                # Collect all dollar amounts in order
                # Row pattern: bought_usd, sold_usd, pnl_usd
                dollar_amounts = []
                txn_counts = []
                
                # Split by newlines and pipes to get individual fragments
                parts = text.replace("|", "\n").split("\n")
                
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    # Look for dollar sign followed by a number (or just the number after $)
                    if part.startswith("$") or (part.startswith("-$")):
                        parsed = parse_currency(part)
                        if parsed is not None:
                            dollar_amounts.append(parsed)
                    # Also check if the line contains a dollar amount pattern
                    elif "$" in part:
                        parsed = parse_currency(part)
                        if parsed is not None:
                            dollar_amounts.append(parsed)
                            
                    # Look for transaction counts
                    if "txn" in part.lower():
                        count = parse_txn_count(part)
                        if count:
                            txn_counts.append(count)
                
                # Map dollar amounts based on order:
                # [0] = Bought, [1] = Sold, [2] = PNL
                if len(dollar_amounts) >= 3:
                    bought = abs(dollar_amounts[0])
                    sold = abs(dollar_amounts[1])
                    pnl = dollar_amounts[2]  # Can be negative
                elif len(dollar_amounts) == 2:
                    bought = abs(dollar_amounts[0])
                    sold = abs(dollar_amounts[1])
                elif len(dollar_amounts) == 1:
                    pnl = dollar_amounts[0]
                    
                # Sum all transaction counts
                txn_count = sum(txn_counts)
                
                logger.debug(f"Trader {wallet_address[:8]}: bought=${bought:.0f} sold=${sold:.0f} pnl=${pnl:.0f} txns={txn_count}")
                
            return Trader(
                wallet_address=wallet_address,
                token_address=token_address,
                bought_usd=bought,
                sold_usd=sold,
                pnl_usd=pnl,
                txn_count=txn_count,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.debug(f"Failed to parse trader element: {e}")
            return None
            
    async def scrape_token_batch(
        self,
        token_addresses: List[str],
        progress_callback=None
    ) -> List[Trader]:
        """
        Scrape top traders for multiple tokens with delays.
        
        Args:
            token_addresses: List of token addresses to scrape
            progress_callback: Optional callback(current, total) for progress
            
        Returns:
            Aggregated list of all traders from all tokens
        """
        all_traders: List[Trader] = []
        total = len(token_addresses)
        
        logger.info(f"Starting batch scrape for {total} tokens")
        
        for i, address in enumerate(token_addresses):
            if progress_callback:
                progress_callback(i + 1, total)
                
            traders = await self.get_top_traders(address)
            all_traders.extend(traders)
            
            # Delay before next token (except last)
            if i < total - 1:
                await self._random_delay()
                
        logger.info(f"Batch complete: {len(all_traders)} total traders from {total} tokens")
        return all_traders


# Convenience function for simple usage
async def scrape_trending_tokens(**kwargs) -> List[Token]:
    """
    Convenience function to scrape trending tokens.
    
    See DexScreenerScraper.get_trending_tokens for args.
    """
    async with DexScreenerScraper() as scraper:
        return await scraper.get_trending_tokens(**kwargs)


async def scrape_top_traders(token_address: str, **kwargs) -> List[Trader]:
    """
    Convenience function to scrape top traders for a token.
    
    See DexScreenerScraper.get_top_traders for args.
    """
    async with DexScreenerScraper() as scraper:
        return await scraper.get_top_traders(token_address, **kwargs)
