"""
Smart Wallet Tracker - Main Entry Point

Identifies "smart money" wallets in the Solana memecoin market by:
1. Discovering successful memecoins from DEX Screener
2. Extracting top trader data from each token
3. Cross-referencing wallets that appear in multiple successful tokens
4. Scoring and ranking wallets based on consistency and profitability

Usage:
    python main.py [--visible] [--headless]

Output:
    - Console: Top 10 smart wallets with scores
    - CSV: data/smart_wallets.csv with full ranked list
"""

import argparse
import asyncio
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List

from tqdm import tqdm

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.analyzer import analyze_traders, rescore_wallets
from src.database import get_database
from src.models import SmartWallet, Token, Trader
from src.scraper import DexScreenerScraper
from src.birdeye import BirdeyeScraper
from src.utils import (
    format_currency,
    format_percentage,
    load_config,
    save_to_csv,
    save_to_json,
    save_to_xlsx,
    setup_logging
)

# Main logger
logger = setup_logging("main", log_file="wallet_tracker.log")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Smart Wallet Tracker")
    parser.add_argument(
        "--visible", 
        action="store_true", 
        help="Run browser in visible mode (not headless) for debugging"
    )
    return parser.parse_args()


def print_header() -> None:
    """Print application header."""
    print("\n" + "=" * 60)
    print("  SMART WALLET TRACKER - Solana Memecoin Analysis")
    print("=" * 60 + "\n")


def print_results(wallets: List[SmartWallet], top_n: int = 10) -> None:
    """
    Print formatted results to console.
    
    Args:
        wallets: Ranked list of SmartWallet objects
        top_n: Number of wallets to display
    """
    print("\n" + "=" * 60)
    print(f"  TOP {min(top_n, len(wallets))} SMART WALLETS")
    print("=" * 60 + "\n")
    
    if not wallets:
        print("No smart wallets found matching criteria.")
        return
    
    for i, wallet in enumerate(wallets[:top_n], 1):
        print(f"{i}. Wallet: {wallet.get_short_address()}")
        print(f"   Score: {wallet.score:.1f}/100")
        print(f"   Appearances: {wallet.appearances} tokens")
        print(f"   Total PnL: {format_currency(wallet.total_pnl)}")
        print(f"   Win Rate: {format_percentage(wallet.win_rate * 100)}")
        print(f"   Avg Position: {format_currency(wallet.avg_position_size)}")
        print(f"   Transactions: {wallet.total_txn_count}")
        print()


def save_results(
    tokens: List[Token],
    traders: List[Trader],
    wallets: List[SmartWallet],
    config: dict
) -> None:
    """
    Save all results to CSV files.
    
    Args:
        tokens: List of scraped tokens
        traders: List of scraped traders
        wallets: Ranked smart wallets
        config: Configuration dictionary
    """
    output = config["output"]
    
    # Save tokens
    if tokens:
        token_dicts = [
            {
                "address": t.address,
                "name": t.name,
                "symbol": t.symbol,
                "volume_24h": t.volume_24h,
                "price_change_24h": t.price_change_24h,
                "timestamp": t.timestamp.isoformat()
            }
            for t in tokens
        ]
        save_to_csv(token_dicts, output["tokens_file"])
        logger.info(f"Saved {len(tokens)} tokens to {output['tokens_file']}")
    
    # Save traders
    if traders:
        trader_dicts = [
            {
                "wallet_address": t.wallet_address,
                "token_address": t.token_address,
                "bought_usd": t.bought_usd,
                "sold_usd": t.sold_usd,
                "pnl_usd": t.pnl_usd,
                "txn_count": t.txn_count,
                "timestamp": t.timestamp.isoformat()
            }
            for t in traders
        ]
        save_to_csv(trader_dicts, output["traders_file"])
        logger.info(f"Saved {len(traders)} traders to {output['traders_file']}")
    
    # Save smart wallets
    if wallets:
        # Get database instance
        db = get_database()
        
        # Prepare rich data for JSON (web app) and database
        json_data = []
        for i, w in enumerate(wallets, 1):
            wallet_dict = {
                "rank": i,
                "wallet_address": w.wallet_address,
                "score": round(w.score, 1),
                "appearances": w.appearances,
                "total_pnl": round(w.total_pnl) if w.total_pnl is not None else 0,
                "avg_pnl": round(w.avg_pnl) if w.avg_pnl is not None else 0,
                "avg_position_size": round(w.avg_position_size) if w.avg_position_size is not None else 0,
                "total_txn_count": w.total_txn_count,
                # Birdeye 7D Data
                "win_rate_7d": f"{w.win_rate_7d*100:.1f}%" if w.win_rate_7d is not None else "-",
                "realized_pnl_7d": round(w.realized_pnl_7d) if w.realized_pnl_7d is not None else "-",
                "unrealized_pnl_7d": round(w.unrealized_pnl_7d) if w.unrealized_pnl_7d is not None else "-",
                "avg_holding_time_7d": w.avg_holding_time_7d or "-",
                # Birdeye 30D Data
                "win_rate_30d": f"{w.win_rate_30d*100:.1f}%" if w.win_rate_30d is not None else "-",
                "realized_pnl_30d": round(w.realized_pnl_30d) if w.realized_pnl_30d is not None else "-",
                "unrealized_pnl_30d": round(w.unrealized_pnl_30d) if w.unrealized_pnl_30d is not None else "-",
                "avg_holding_time_30d": w.avg_holding_time_30d or "-",
                # Token list (Full objects with dex_url)
                "tokens_list": w.tokens_list
            }
            json_data.append(wallet_dict)
            
            # Save to database (with raw numeric values for proper storage)
            db.upsert_smart_wallet({
                "wallet_address": w.wallet_address,
                "score": w.score,
                "appearances": w.appearances,
                "total_pnl": w.total_pnl,
                "avg_pnl": w.avg_pnl,
                "avg_position_size": w.avg_position_size,
                "total_txn_count": w.total_txn_count,
                "win_rate_7d": w.win_rate_7d,
                "realized_pnl_7d": w.realized_pnl_7d,
                "unrealized_pnl_7d": w.unrealized_pnl_7d,
                "avg_holding_time_7d": w.avg_holding_time_7d,
                "win_rate_30d": w.win_rate_30d,
                "realized_pnl_30d": w.realized_pnl_30d,
                "unrealized_pnl_30d": w.unrealized_pnl_30d,
                "avg_holding_time_30d": w.avg_holding_time_30d,
                "tokens_list": w.tokens_list
            })

        # Prepare flat data for CSV/XLSX
        csv_data = []
        for item in json_data:
            flat_item = item.copy()
            # Flatten tokens list to string: "SYMBOL (ADDR...)"
            tokens = []
            for t in item['tokens_list']:
                # Handle both dict and potentially string if something failed
                if isinstance(t, dict):
                    addr_short = t['address'][:4] + '...'
                    tokens.append(f"{t['symbol']} ({addr_short})")
                else:
                    tokens.append(str(t))
            flat_item['tokens_list'] = ", ".join(tokens)
            csv_data.append(flat_item)

        # Save as CSV
        save_to_csv(csv_data, output["smart_wallets_file"])

        # Save as XLSX
        xlsx_file = output["smart_wallets_file"].replace(".csv", ".xlsx")
        save_to_xlsx(csv_data, xlsx_file)
        
        # Export ALL wallets from DB to JSON (not just current run)
        json_file = output["smart_wallets_file"].replace(".csv", ".json")
        db.export_smart_wallets_to_json(json_file)
        
        # Also copy to web dashboard location
        web_json = Path("web/public/data/smart_wallets.json")
        db.export_smart_wallets_to_json(web_json)
        
        logger.info(f"Saved {len(wallets)} smart wallets to:")
        logger.info(f"  - CSV: {output['smart_wallets_file']}")
        logger.info(f"  - XLSX: {xlsx_file}")
        logger.info(f"  - JSON: {json_file}")


async def main() -> None:
    """
    Main pipeline: scrape → analyze → output.
    
    Steps:
    1. Load configuration
    2. Discover trending tokens from DEX Screener
    3. Scrape top traders for each token (with progress bar)
    4. Analyze and score wallets
    5. Output results to console and CSV
    """
    # Parse CLI args
    args = parse_args()
    
    print_header()
    
    # Load config
    config = load_config()
    
    # Override headless mode if requested
    if args.visible:
        config["scraping"]["headless"] = False
        print("👀 Running in VISIBLE mode (non-headless)")
        
    logger.info(f"Configuration loaded (headless={config['scraping'].get('headless')})")
    
    # Track all data
    all_tokens: List[Token] = []
    all_traders: List[Trader] = []
    
    try:
        async with DexScreenerScraper(config) as scraper:
            # Step 1: Discover trending tokens
            print("📊 Discovering trending tokens...")
            tokens = await scraper.get_trending_tokens()
            all_tokens = tokens
            
            if not tokens:
                logger.warning("No tokens found matching criteria")
                print("❌ No trending tokens found. Try adjusting filters in config.json")
                return
            
            print(f"✅ Found {len(tokens)} trending tokens\n")
            
            # Step 2: Scrape top traders for each token (parallel with bounded concurrency)
            print("👛 Scraping top traders...")
            
            MAX_CONCURRENT_TOKENS = 4  # Balance speed vs rate limiting
            token_sem = asyncio.Semaphore(MAX_CONCURRENT_TOKENS)
            
            async def scrape_token_with_semaphore(token, pbar):
                async with token_sem:
                    pbar.set_postfix_str(f"{token.symbol[:10]}")
                    traders = await scraper.get_top_traders(token.address, token.symbol, token.dex_url)
                    pbar.update(1)
                    return traders
            
            pbar = tqdm(total=len(tokens), desc="Scraping tokens", unit="token")
            tasks = [scrape_token_with_semaphore(t, pbar) for t in tokens]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            pbar.close()
            
            # Flatten results, skip exceptions
            for result in results:
                if isinstance(result, list):
                    all_traders.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Token scrape failed: {result}")
                
            print(f"✅ Scraped {len(all_traders)} trader records\n")
    
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        print(f"❌ Scraping error: {e}")
        if all_traders:
            print("   Continuing with partial data...")
        else:
            return
    
    # Step 3: Analyze wallets
    print("🧠 Analyzing wallets...")
    smart_wallets = analyze_traders(all_traders, config)
    print(f"✅ Identified {len(smart_wallets)} smart wallets\n")
    
    # Step 4: Enrich wallets with Birdeye data (parallel with bounded concurrency)
    if smart_wallets:
        print("🦅 Enriching top wallets with Birdeye data...")
        # Enrich top 20 wallets to balance speed/depth
        limit = min(len(smart_wallets), 20)
        to_enrich = smart_wallets[:limit]
        
        MAX_CONCURRENT_BIRDEYE = 3
        birdeye_sem = asyncio.Semaphore(MAX_CONCURRENT_BIRDEYE)
        
        async def enrich_with_semaphore(birdeye, wallet, pbar):
            async with birdeye_sem:
                result = await birdeye.enrich_wallet(wallet)
                pbar.update(1)
                return result
        
        async with BirdeyeScraper(config) as birdeye:
            pbar = tqdm(total=len(to_enrich), desc="Enriching", unit="wallet")
            tasks = [enrich_with_semaphore(birdeye, w, pbar) for w in to_enrich]
            await asyncio.gather(*tasks)
            pbar.close()
        print(f"✅ Enriched {len(to_enrich)} wallets\n")
        
        # Rescore and re-rank with Degen Score
        smart_wallets = rescore_wallets(smart_wallets)
    
    # Step 5: Output results
    top_n = config["output"]["top_wallets_to_display"]
    print_results(smart_wallets, top_n)
    
    # Step 5: Save to CSV
    save_results(all_tokens, all_traders, smart_wallets, config)
    
    print("=" * 60)
    print("  Analysis complete! Results saved to data/")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
