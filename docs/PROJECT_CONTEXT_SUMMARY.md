# Smart Wallet Tracker: Project Context & Summary

## **Project Identity**
A robust, automated pipeline for identifying and tracking "Smart Money" wallets in the Solana memecoin market. The app discovers trending tokens, identifies top-earning traders, and enriches their profiles with deep performance metrics from Birdeye.

---

## **Architectural Overview**

### **1. Backend (Python)**
- **Playwright (Stealth)**: Used for scraping DEX Screener and Birdeye. Implements `playwright-stealth` and custom resource blocking (images/fonts) for performance and bot-detection avoidance.
- **Analysis Engine**: Aggregates trader data across multiple tokens, applying a proprietary scoring algorithm (consistency, PnL, regularity).
- **Database (SQLite)**: Stores tokens, traders, and aggregated wallet stats to prevent data loss and enable historical tracking.
- **API Server (FastAPI)**: Serves the analyzed data to the frontend.

### **2. Frontend (React/Vite)**
- **Dashboard**: A premium, "glassmorphism" themed UI for visualizing smart wallets.
- **Features**: 
    - Real-time filtering and sorting by "Degen Score".
    - **One-click Copy**: Wallet addresses can be copied to clipboard with a single click.
    - **Token Breakdown**: Displays which tokens each wallet traded and the PnL per token.
    - **Direct Links**: Quick access to Birdeye and Solscan for verification.

---

## **Current Implementation State**

### **Data Flow**
1. **Token Discovery**: `scraper.py` hits DEX Screener trending pages (Pump.fun specific).
2. **Trader Extraction**: For each token, the top 100 traders are extracted (parallelized with semaphores).
3. **Aggregated Analysis**: `analyzer.py` combines these into unique `SmartWallet` profiles.
4. **Birdeye Enrichment**: High-scoring wallets are enriched with 7D/30D metrics (Win Rate, Realized PnL, Avg Hold Time).
5. **Score Logic**: Final ranking using the "Degen Score" (0-100 scale).

---

## **Critical Issues & Technical Blockers**

### **1. Birdeye Data Extraction (Priority: HIGH)**
- **The Issue**: In large batches, most wallets show missing data (`-`) for Birdeye metrics (Win Rate, Realized PnL, etc.).
- **Root Cause**: Birdeye implements aggressive rate limiting and anti-bot measures. Additionally, UI labels vary (e.g., `7D` vs `7d`) and data loads dynamically after clicking timeframe buttons.
- **Implemented Fixes**:
    - **Regex Refinement**: Case-insensitive matching (`/7[Dd]/`) and support for optional spaces in currency (e.g., `+$ 2.3K`).
    - **Throttling**: Reduced concurrency to `MAX_CONCURRENT_BIRDEYE = 2`.
    - **Staggering**: Added random delays (2-6 seconds) between enrichment requests.
    - **Retries**: Implemented exponential backoff (5s, 10s) in `birdeye.py`.
- **Current State**: Improved success rate for small batches, but large runs (50+ tokens) still suffer from intermittent data gaps.

### **2. Database/API Synchronization**
- **The Issue**: `sqlite3.OperationalError: no such table: smart_wallets` in `api_server.py`.
- **Diagnosis**: Occurs if the API server is started before the first run of the scraper completes, or if the database file is deleted and re-created without the full schema initialization being triggered correctly.

---

## **Performance Benchmarks**
- **Discovery Phase**: ~20s
- **Scraping Phase (50 Tokens)**: ~2.5 min (Parallelized & resource blocking)
- **Enrichment Phase (20 Wallets)**: ~1-1.5 min (Staggered for stability)
- **Total Run Time**: ~4-5 minutes.

---

## **Next Steps for Other Agents**
- **Improve Scraping Robustness**: Consider using rotating proxies or residential IP headers for Birdeye.
- **Edge Case Handling**: Handle wallets with "0" activity on Birdeye more gracefully (currently might show as missing).
- **UI Resilience**: Add "Loading" and "No Data" states for wallets that haven't been enriched yet.
- **DB Fix**: Ensure `api_server.py` handles the absence of the `smart_wallets` table gracefully or triggers a schema check.

---
*Last Updated: 2026-01-18 18:30 (Antigravity)*
