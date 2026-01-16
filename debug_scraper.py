"""Debug script to trace token extraction step by step."""
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from src.utils import extract_token_from_dexscreener_url, parse_currency, parse_percentage

async def debug_token_extraction():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()
        await stealth_async(page)
        
        url = "https://dexscreener.com/solana/pumpswap?rankBy=trendingScoreH1&order=desc"
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="networkidle")
        
        # Wait for Age header and click twice
        print("Sorting by Age (Newest First)...")
        await page.wait_for_selector("button.ds-table-th-button", timeout=10000)
        age_btn = page.locator("button.ds-table-th-button", has_text="Age").first
        if await age_btn.is_visible():
            await age_btn.click()
            await asyncio.sleep(1)
            await age_btn.click()
            await asyncio.sleep(3)
        
        # Find token rows
        print("\nFinding token rows...")
        rows = await page.query_selector_all("a.ds-dex-table-row, a[href^='/solana/']")
        print(f"Found {len(rows)} rows with combined selector")
        
        # Also try just the table row selector
        table_rows = await page.query_selector_all("a.ds-dex-table-row")
        print(f"Found {len(table_rows)} rows with a.ds-dex-table-row only")
        
        # Parse first 5 rows in detail
        print("\n=== DETAILED ROW ANALYSIS ===")
        for i, row in enumerate(table_rows[:5]):
            print(f"\n--- Row {i+1} ---")
            
            # Get href
            href = await row.get_attribute("href")
            print(f"  href: {href}")
            
            # Extract address
            address = extract_token_from_dexscreener_url(href)
            print(f"  extracted address: {address}")
            
            # Get volume
            volume_cell = await row.query_selector(".ds-dex-table-row-col-volume")
            if volume_cell:
                volume_text = await volume_cell.inner_text()
                parsed_volume = parse_currency(volume_text)
                print(f"  volume_text: '{volume_text}' -> parsed: {parsed_volume}")
            else:
                print(f"  volume_cell: NOT FOUND")
            
            # Get 6H price change (what we should be using now)
            price_cell_h6 = await row.query_selector(".ds-dex-table-row-col-price-change-h6")
            if price_cell_h6:
                price_text = await price_cell_h6.inner_text()
                parsed_price = parse_percentage(price_text)
                print(f"  6H price_text: '{price_text}' -> parsed: {parsed_price}")
                print(f"  MEETS CRITERIA? volume >= 100000: {parsed_volume >= 100000 if parsed_volume else False}, gain >= 30: {parsed_price >= 30 if parsed_price else False}")
            else:
                print(f"  6H price_cell: NOT FOUND")
        
        await browser.close()
        print("\n=== DEBUG COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(debug_token_extraction())
