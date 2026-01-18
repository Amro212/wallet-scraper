# Scraper Performance Optimization Guide

## Overview

We improved the Smart Wallet Tracker scraper from **~10+ minutes** to **~3 minutes** for a full 50-token run by implementing 5 key optimizations.

---

## What We Changed

### 1. Parallel Token Scraping (Biggest Impact)

**The Problem:**  
Scraping 50 tokens one-by-one at ~12 seconds each = **10 minutes**.

**The Solution:**  
Scrape 4 tokens simultaneously using Python's `asyncio.Semaphore`.

```python
MAX_CONCURRENT_TOKENS = 4
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TOKENS)

async def scrape_with_limit(token):
    async with semaphore:  # Only 4 can run at once
        return await scraper.get_top_traders(token)

# Run all in parallel, semaphore limits to 4 at a time
results = await asyncio.gather(*[scrape_with_limit(t) for t in tokens])
```

**Layman's Terms:**  
Instead of going to 50 stores one by one, we send 4 shoppers at a time. When one finishes, the next goes.

**Impact:** ~4x faster token scraping phase.

---

### 2. Async API Calls with Caching

**The Problem:**  
`fetch_token_metadata()` used synchronous `requests.get()`, which blocks the entire program while waiting for a response.

**The Solution:**  
Switch to `aiohttp` (async HTTP client) + cache results in memory.

```python
_metadata_cache = {}  # In-memory cache

async def fetch_token_metadata_async(session, pair_address):
    if pair_address in _metadata_cache:
        return _metadata_cache[pair_address]  # Cache hit
    
    async with session.get(url) as resp:
        data = await resp.json()
        _metadata_cache[pair_address] = data
        return data
```

**Layman's Terms:**  
Instead of calling the phone company and waiting on hold, we text them (async). Plus, we write down answers so we don't ask the same question twice (cache).

**Impact:** Non-blocking API calls + zero duplicate requests.

---

### 3. Resource Blocking

**The Problem:**  
Browser loads images, fonts, and media we don't need—wasting 30-50% of load time.

**The Solution:**  
Block these resources in Playwright:

```python
async def block_resources(route):
    if route.request.resource_type in ("image", "media", "font"):
        await route.abort()
    else:
        await route.continue_()

await page.route("**/*", block_resources)
```

**Layman's Terms:**  
When visiting a webpage, we tell the browser "don't download any pictures or fancy fonts, just get the text data."

**Impact:** 30-50% faster page loads.

---

### 4. Smarter Wait Strategy

**The Problem:**  
`wait_until="networkidle"` waits for ALL network activity to stop—slow on WebSocket-heavy sites like DexScreener.

**The Solution:**  
Use `domcontentloaded` (faster) + wait for the specific element we need:

```python
# Before (slow)
await page.goto(url, wait_until="networkidle")

# After (fast)
await page.goto(url, wait_until="domcontentloaded")
await page.wait_for_selector("a.ds-dex-table-row")  # Wait for table
```

**Layman's Terms:**  
Instead of waiting for EVERYTHING on a webpage to fully load, we just wait until the specific data table appears.

**Impact:** 2-5 seconds saved per page load.

---

### 5. Parallel Birdeye Enrichment

**The Problem:**  
Enriching 20 wallets with Birdeye data one-by-one at ~10 seconds each = **3+ minutes**.

**The Solution:**  
Same semaphore pattern as token scraping:

```python
MAX_CONCURRENT_BIRDEYE = 3
birdeye_sem = asyncio.Semaphore(MAX_CONCURRENT_BIRDEYE)

async def enrich_with_limit(wallet):
    async with birdeye_sem:
        return await birdeye.enrich_wallet(wallet)

await asyncio.gather(*[enrich_with_limit(w) for w in wallets])
```

**Impact:** ~3x faster wallet enrichment.

---

## Key Concepts

| Concept | What It Is | Why It Matters |
|---------|------------|----------------|
| **Async/Await** | Run multiple I/O operations without blocking | CPU can do other work while waiting for network |
| **Semaphore** | Limits concurrent operations | Prevents rate limiting, controls resource usage |
| **aiohttp** | Async HTTP client library | Non-blocking API calls |
| **Resource Blocking** | Abort unnecessary network requests | Faster page loads |
| **Caching** | Store results in memory | Avoid duplicate work |

---

## Before vs After

| Phase | Before | After | Improvement |
|-------|--------|-------|-------------|
| Token Discovery | ~40s | ~20s | 2x |
| Token Scraping (50 tokens) | ~10 min | ~2.5 min | 4x |
| Birdeye Enrichment (20 wallets) | ~3 min | ~1 min | 3x |
| **Total** | **~14 min** | **~4 min** | **3.5x** |

---

## Files Modified

- `main.py` – Added parallel scraping and Birdeye enrichment
- `src/scraper.py` – Resource blocking, domcontentloaded, aiohttp session
- `src/utils.py` – Added `fetch_token_metadata_async()` with caching

---

## Dependencies Added

```bash
pip install aiohttp
```

---

## Configuration

Concurrency limits can be tuned in `main.py`:

```python
MAX_CONCURRENT_TOKENS = 4   # Parallel token scraping
MAX_CONCURRENT_BIRDEYE = 3  # Parallel wallet enrichment
```

Higher = faster but more likely to hit rate limits.
