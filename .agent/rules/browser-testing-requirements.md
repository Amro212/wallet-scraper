---
trigger: always_on
---

# Browser Testing & Scraping Rules

## CRITICAL: Browser Testing Requirements

### Rule 1: Test in Browser Before Coding
**MANDATORY before implementing any scraper:**
1. Open target webpage in browser (Chrome/Firefox)
2. Use Developer Tools (F12) to inspect HTML
3. Identify exact elements, classes, IDs
4. Test selectors in browser console
5. Document findings before writing code

**Browser Console Testing:**
```javascript
// Test CSS selector
document.querySelector('.trader-row')

// Test multiple elements
document.querySelectorAll('.trader-address')

// Verify data extraction
Array.from(document.querySelectorAll('.pnl')).map(el => el.textContent)
```

### Rule 2: Verify Every Feature After Implementation
**After coding any scraper function:**
1. Run code against live website
2. Print/log extracted data
3. Compare output to browser view
4. Test edge cases (missing data, different formats)
5. Return to browser if output doesn't match

### Rule 3: Use Browser Dev Tools
- **Elements Tab**: Inspect HTML structure
- **Console Tab**: Test selectors and JavaScript
- **Network Tab**: Check if data loads via API or HTML
- **Screenshots**: Document what you're scraping

### Rule 4: Test Incrementally
**Never implement everything at once:**
1. Extract ONE element first → verify
2. Extract next element → verify
3. Combine extractions → verify
4. Process batch → verify

### Rule 5: Handle Dynamic Content
**If content loads via JavaScript:**
1. Check Network tab for XHR/Fetch requests
2. Consider calling API directly if available
3. Use Selenium/Playwright with proper waits
4. Verify elements exist before extraction

---

## Error Handling

### Rule 6: Expect All Failures
**Every scraper must handle:**
- Network errors (timeout, connection refused)
- Missing elements (selector not found)
- Changed HTML structure
- Rate limiting (429 errors)
- Invalid data formats (null, unexpected text)

```python
try:
    element = soup.find('div', class_='target')
    data = element.text.strip() if element else None
except Exception as e:
    logger.error(f"Error scraping {url}: {e}")
    return None
```

### Rule 7: Fail Gracefully
- Log errors with full context (URL, selector, message)
- Don't crash entire program for one failure
- Return None or empty structure
- Continue with other items
- Collect failures for review

---

## Logging & Debugging

### Rule 8: Log Everything
**Every scraping operation logs:**
- URL/page being scraped
- Data successfully extracted
- Missing or failed data
- Operation duration
- Errors and warnings

```python
logger.info(f"Scraping token: {token_address}")
logger.debug(f"Found {len(traders)} traders")
logger.warning(f"Missing PnL for: {wallet}")
logger.error(f"Failed to load: {url}")
```

### Rule 9: Save Raw HTML for Debugging
```python
with open(f'debug_html/{token_address}.html', 'w') as f:
    f.write(response.text)
```

---

## Respectful Scraping

### Rule 10: Implement Delays
- Minimum 2-3 seconds between requests
- Randomize delays: `time.sleep(random.uniform(2.0, 4.0))`
- Respect 429 responses by backing off

### Rule 11: Use Proper Headers
```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'text/html,application/xhtml+xml',
}
```

### Rule 12: Cache Everything
- Cache successful responses to disk
- Check cache before new requests
- Invalidate after reasonable time (1 hour)

---

## Data Validation

### Rule 13: Validate All Data
```python
def validate_trader(trader_dict):
    required = ['wallet_address', 'pnl_usd']
    for field in required:
        if field not in trader_dict or trader_dict[field] is None:
            return False
    return isinstance(trader_dict['pnl_usd'], (int, float))
```

### Rule 14: Handle Data Inconsistencies
- Different formats: $1,234 vs 1234 vs 1.23K
- Missing fields on some pages
- Inconsistent date formats
- Handle all variations gracefully

---

## Selenium/Playwright Rules

### Rule 15: Wait Properly
```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "trader-row"))
)
```

### Rule 16: Clean Up Resources
```python
try:
    driver = webdriver.Chrome()
    # scraping code
finally:
    driver.quit()
```

---

## Code Organization

### Rule 17: Separate Concerns
- `fetch_page(url)` → Get HTML
- `parse_page(html)` → Extract data
- `validate_data(data)` → Validate
- Keep scraping separate from business logic

### Rule 18: Configurable Selectors
```python
SELECTORS = {
    'trader_row': 'div.trader-row',
    'wallet': 'span.wallet-address',
    'pnl': 'td.pnl-column',
}
```

---

## Documentation

### Rule 19: Document Selectors
```python
def scrape_top_traders(token_address: str) -> List[Trader]:
    """
    Scrapes top traders from DEX Screener.
    
    URL: https://dexscreener.com/solana/{token_address}
    Selectors:
        - Rows: 'div.trader-row'
        - Wallet: 'span.wallet-address'
        - PNL: 'td[data-label="PNL"]'
    
    Returns: List of Trader objects or empty list
    
    Known Issues:
        - Page loads via JavaScript (2-3 sec wait)
        - Some traders may have missing PnL
    """
```

---

## Testing Checklist

Before marking scraper as "done":
- [ ] Tested manually in browser
- [ ] Selectors verified in console
- [ ] Code tested against live site
- [ ] Error handling implemented
- [ ] Logging added
- [ ] Delays/rate limiting in place
- [ ] Data validation added
- [ ] Edge cases tested
- [ ] Documentation written
- [ ] Results match expectations

**REMEMBER: If you haven't tested it in a browser, you haven't tested it.**