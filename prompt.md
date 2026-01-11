# Smart Wallet Tracker - Project Specification

## Project Overview

This project aims to identify and track "smart money" wallets in the Solana memecoin market. Smart wallets are traders who consistently demonstrate:
- High win rates (70-80%+)
- Early entry into successful tokens
- Strong conviction with meaningful position sizes
- Disciplined profit-taking strategies

By analyzing wallets that appear as top traders across multiple successful token launches, we can identify skilled traders worth following for alpha.

---

## What We're Building

A Python-based system that:

1. **Discovers successful Solana memecoins** that have recently pumped
2. **Extracts top trader data** from each successful token
3. **Cross-references wallets** to find those appearing in multiple successful launches
4. **Scores and ranks wallets** based on consistency, profitability, and trading patterns
5. **Outputs a ranked list** of "smart wallets" to monitor

---

## Implementation Strategy

### OPTION 1: DEX Screener Only (IMPLEMENT THIS)

This is the primary approach to implement now. It's completely free and provides strong signal.

**Data Source**: DEX Screener website scraping only
- No API keys required
- No rate limits to worry about
- All relevant data available in the UI

**Workflow**:
1. Scrape DEX Screener's "Gainers & Losers" or trending tokens page for Solana
2. Filter for successful tokens (e.g., 5x+ in 24h, volume > $100K)
3. For each successful token, scrape the "Top Traders" tab
4. Extract: wallet addresses, bought amount, sold amount, PnL, transaction count
5. Build a database of all wallets and their performance across tokens
6. Score wallets based on:
   - **Consistency**: Appears in multiple successful tokens (most important)
   - **Profitability**: Total PnL across all tokens
   - **Entry Timing**: How early they entered (inferred from "Top Trader" ranking)
   - **Position Sizing**: Average buy amounts
7. Generate ranked output of top wallets

**Key Metrics to Calculate**:
- Number of successful tokens wallet appeared in
- Total PnL across all tokens
- Average PnL per token
- Win rate (% of tokens where PnL > 0)
- Average position size
- Consistency score (higher weight for wallets in 3+ tokens)

### OPTION 2: Hybrid with Solscan (DO NOT IMPLEMENT YET - KEEP IN MIND)

This is a future enhancement to get more complete wallet history.

**Additional Data Source**: Solscan Public API (free tier)
- Rate Limits: 150 requests per 30 seconds, 100K requests per day
- Base URL: `https://public-api.solscan.io/`

**Enhanced Workflow** (when implemented later):
1. Use Option 1 to identify promising wallets (appear in 2+ successful tokens)
2. For these high-potential wallets only, query Solscan API for full transaction history
3. Calculate true overall win rate across ALL their trades (not just successful tokens)
4. Detect red flags: insider behavior, wash trading, bot activity
5. Enhance scoring with complete trading history

**Additional Metrics** (from Solscan):
- True overall win rate (all trades, not just winners)
- Trading frequency (trades per week)
- Wallet age and activity patterns
- Bot detection (trades within 1 second of launch)
- Insider detection (only appears in 1 token with massive gains)

**Implementation Notes for Later**:
- Implement rate limiting and request queuing
- Cache all API responses locally to avoid duplicate requests
- Only query wallets that meet threshold (e.g., 2+ tokens from Option 1)
- Add retry logic with exponential backoff

---

## Technical Stack

### Core Libraries
- **requests**: HTTP requests for web scraping
- **beautifulsoup4**: HTML parsing (if data is in static HTML)
- **selenium** OR **playwright**: Browser automation (if data loads via JavaScript)
- **pandas**: Data manipulation and analysis
- **json**: Data storage and intermediate processing

### Optional/Supporting Libraries
- **lxml**: Fast HTML parsing (optional, beautifulsoup can use it)
- **numpy**: Numerical calculations for scoring algorithms
- **tqdm**: Progress bars for long-running scrapes
- **python-dotenv**: Configuration management (if needed later)

### Data Storage (Start Simple)
- **CSV files**: Store scraped data (tokens, wallets, trades)
- **JSON files**: Store configuration and intermediate results
- Can upgrade to SQLite or PostgreSQL later if needed

---

## Project Structure

```
smart-wallet-tracker/
│
├── src/
│   ├── __init__.py
│   ├── scraper.py          # DEX Screener scraping logic
│   ├── analyzer.py         # Wallet analysis and scoring
│   ├── models.py           # Data models (Token, Wallet, Trade)
│   └── utils.py            # Helper functions
│
├── data/
│   ├── tokens.csv          # Successful tokens found
│   ├── traders.csv         # All trader data scraped
│   └── smart_wallets.csv   # Final ranked output
│
├── config/
│   └── config.json         # Configuration (thresholds, filters)
│
├── tests/                  # Unit tests
│   └── test_scraper.py
│
├── requirements.txt        # Python dependencies
├── README.md              # Project documentation
└── main.py                # Main entry point
```

---

## Detailed Implementation Plan

### Phase 1: DEX Screener Scraper

**File**: `src/scraper.py`

**Functions to implement**:

1. `get_trending_tokens(chain='solana', min_volume=100000, min_gain=500)` → List[Token]
   - Scrapes DEX Screener gainers/trending page
   - Filters by volume and price gain
   - Returns list of Token objects with: address, name, symbol, volume, price_change, market_cap

2. `get_top_traders(token_address: str, limit=50)` → List[Trader]
   - Navigates to specific token page
   - Clicks/loads "Top Traders" tab
   - Extracts trader data: wallet_address, bought_amount, sold_amount, pnl, txn_count
   - Returns list of Trader objects

3. `scrape_token_batch(token_addresses: List[str])` → Dict
   - Scrapes top traders for multiple tokens
   - Implements delays between requests to be respectful
   - Returns aggregated data

**Technical Considerations**:
- Determine if DEX Screener uses static HTML or JavaScript rendering
- If JavaScript: use Selenium/Playwright with headless browser
- Implement polite scraping: delays between requests (2-3 seconds)
- Add error handling for network issues, missing data
- Log all scraping activity for debugging

### Phase 2: Data Models

**File**: `src/models.py`

```python
@dataclass
class Token:
    address: str
    name: str
    symbol: str
    volume_24h: float
    price_change_24h: float
    market_cap: float
    timestamp: datetime

@dataclass
class Trader:
    wallet_address: str
    token_address: str
    bought_usd: float
    sold_usd: float
    pnl_usd: float
    txn_count: int
    timestamp: datetime

@dataclass
class SmartWallet:
    wallet_address: str
    appearances: int  # Number of successful tokens
    total_pnl: float
    avg_pnl: float
    win_rate: float
    avg_position_size: float
    score: float
    tokens_list: List[str]
```

### Phase 3: Analysis Engine

**File**: `src/analyzer.py`

**Functions to implement**:

1. `aggregate_wallet_data(traders: List[Trader])` → Dict[str, WalletStats]
   - Groups traders by wallet_address
   - Calculates aggregate statistics per wallet
   - Returns dict mapping wallet_address to statistics

2. `calculate_wallet_score(wallet_stats: WalletStats)` → float
   - Implements scoring algorithm:
     ```
     Score = (Consistency × 0.40) +      # Most important
             (Profitability × 0.25) +
             (Win_Rate × 0.20) +
             (Position_Size × 0.15)
     ```
   - Normalize each component to 0-1 scale
   - Returns final score

3. `apply_filters(wallets: List[SmartWallet])` → List[SmartWallet]
   - Filters out:
     - Wallets with < 2 token appearances (likely lucky)
     - Wallets with negative total PnL
     - Wallets with < 3 total transactions
   - Returns filtered list

4. `rank_wallets(wallets: List[SmartWallet])` → List[SmartWallet]
   - Sorts by score descending
   - Returns top N wallets

### Phase 4: Main Pipeline

**File**: `main.py`

```python
def main():
    # 1. Discover successful tokens
    tokens = get_trending_tokens(min_volume=100000, min_gain=500)
    
    # 2. Scrape top traders for each token
    all_traders = []
    for token in tokens:
        traders = get_top_traders(token.address)
        all_traders.extend(traders)
    
    # 3. Aggregate and analyze
    wallet_stats = aggregate_wallet_data(all_traders)
    smart_wallets = [calculate_smart_wallet(addr, stats) 
                     for addr, stats in wallet_stats.items()]
    
    # 4. Filter and rank
    filtered = apply_filters(smart_wallets)
    ranked = rank_wallets(filtered)
    
    # 5. Output results
    save_to_csv(ranked, 'data/smart_wallets.csv')
    print_top_wallets(ranked[:10])
```

---

## Configuration File

**File**: `config/config.json`

```json
{
  "scraping": {
    "delay_between_requests": 2,
    "max_tokens_per_run": 20,
    "top_traders_limit": 50
  },
  "filters": {
    "min_token_volume": 100000,
    "min_price_gain_pct": 500,
    "min_appearances": 2,
    "min_total_pnl": 1000,
    "min_transactions": 3
  },
  "scoring": {
    "consistency_weight": 0.40,
    "profitability_weight": 0.25,
    "win_rate_weight": 0.20,
    "position_size_weight": 0.15
  }
}
```

---

## Output Format

### Console Output
```
=== TOP 10 SMART WALLETS ===

1. Wallet: 4zB...x9Q2
   Score: 94.5/100
   Appearances: 7 tokens
   Total PnL: $45,320
   Win Rate: 85.7%
   Avg Position: $3,200
   
2. Wallet: us4...dfo
   Score: 89.2/100
   ...
```

### CSV Output (`data/smart_wallets.csv`)
```csv
rank,wallet_address,score,appearances,total_pnl,avg_pnl,win_rate,avg_position_size,tokens_list
1,4zB...x9Q2,94.5,7,45320,6474,0.857,3200,"token1,token2,token3..."
2,us4...dfo,89.2,5,31250,6250,0.800,2500,"token1,token4,token5..."
```

---

## Key Algorithms

### Scoring Algorithm (Detailed)

```python
def calculate_score(wallet_stats):
    # 1. Consistency Score (0-1)
    # Higher weight for appearing in multiple tokens
    appearances = wallet_stats.appearances
    consistency = min(appearances / 10, 1.0)  # Cap at 10 tokens = perfect score
    
    # 2. Profitability Score (0-1)
    # Normalize PnL (assume $50K is exceptional)
    total_pnl = wallet_stats.total_pnl
    profitability = min(total_pnl / 50000, 1.0)
    
    # 3. Win Rate Score (0-1)
    # Already a percentage
    win_rate = wallet_stats.win_rate
    
    # 4. Position Size Score (0-1)
    # Normalize position size (assume $5K is strong conviction)
    avg_position = wallet_stats.avg_position_size
    position_score = min(avg_position / 5000, 1.0)
    
    # Weighted combination
    score = (consistency * 0.40 +
             profitability * 0.25 +
             win_rate * 0.20 +
             position_score * 0.15)
    
    return score * 100  # Convert to 0-100 scale
```

### Win Rate Calculation

```python
def calculate_win_rate(trades: List[Trader]) -> float:
    winning_trades = sum(1 for t in trades if t.pnl_usd > 0)
    total_trades = len(trades)
    return winning_trades / total_trades if total_trades > 0 else 0
```

---

## Testing Strategy

### Manual Browser Testing (Critical for Scraping)
- Before implementing, manually inspect DEX Screener pages
- Check if data loads immediately or via JavaScript
- Identify exact HTML elements/selectors for data extraction
- Test with multiple tokens to ensure consistency

### Unit Tests
- Test each scraper function with mock HTML
- Test scoring algorithm with known inputs
- Test filter functions with edge cases

### Integration Tests
- Full pipeline test with 2-3 real tokens
- Verify output format matches expected schema

---

## Future Enhancements (Post Option 2)

1. **Real-time monitoring**: Run continuously, alert when smart wallets make new trades
2. **Web dashboard**: Visualize wallet performance over time
3. **Wallet comparison**: Compare multiple wallets side-by-side
4. **Trade alerts**: Get notified when tracked wallets buy new tokens
5. **Historical analysis**: Track how smart wallets evolve over months
6. **Bot detection**: Advanced algorithms to filter out bots and insiders
7. **Portfolio tracking**: See what smart wallets are currently holding

---

## Important Notes

### Ethical Scraping
- Implement delays between requests (2-3 seconds minimum)
- Don't overload DEX Screener's servers
- Cache results to avoid redundant requests
- Respect robots.txt if present

### Data Accuracy
- DEX Screener data may have delays or inaccuracies
- Cross-reference suspicious results manually
- Don't rely on this for financial advice (educational purposes)

### Limitations
- Option 1 only shows performance on successful tokens (survivor bias)
- Can't see full wallet history without Option 2
- Smart wallets may change strategies over time
- Past performance doesn't guarantee future results

---

## Success Criteria

### MVP (Minimum Viable Product)
- Successfully scrapes 10+ successful tokens from DEX Screener
- Extracts top traders for each token
- Identifies at least 3-5 wallets appearing in multiple tokens
- Outputs ranked list with scores

### Full Success
- Scrapes 50+ tokens per run
- Identifies 20+ smart wallets with score > 70
- Processing completes in < 10 minutes
- Output data is clean and actionable
- Code is well-documented and maintainable

---

## Getting Started

1. Set up Python virtual environment
2. Install dependencies from requirements.txt
3. Test DEX Screener scraping on 1-2 tokens manually
4. Implement scraper.py functions incrementally
5. Test each function before moving to next
6. Build analyzer.py once scraper is working
7. Connect everything in main.py
8. Run full pipeline on small dataset (5 tokens)
9. Iterate and improve based on results

---

## Questions to Resolve During Implementation

1. Does DEX Screener use static HTML or JavaScript rendering?
2. What are the exact CSS selectors / XPath for top trader data?
3. How should we handle tokens with < 10 top traders?
4. Should we filter out very new tokens (< 24 hours old)?
5. How do we handle wallets with same performance (tie-breaking)?

---

This specification provides complete context for building Option 1 while keeping Option 2 in mind for future enhancement. The focus is on a working, free solution that provides actionable insights into smart money wallet behavior in the Solana memecoin market.