"""
Standalone test script for Birdeye extraction.
Tests the new global text regex extraction on a known wallet.
"""
import asyncio
from src.birdeye import BirdeyeScraper
from src.models import SmartWallet
from src.utils import load_config

async def test_birdeye_extraction():
    # Load config
    config = load_config()
    
    # Create a test wallet with known Birdeye data
    test_wallet = SmartWallet(
        wallet_address="BWp5WNeY54uGEzdbma8aj2xwwK4hEAomq2BwDZUuMbBM",
        appearances=2,
        total_pnl=1500,
        avg_pnl=750,
        win_rate=0.5,
        avg_position_size=1000,
        total_txn_count=50,
        tokens_list=["test1", "test2"]
    )
    
    print(f"\n=== Testing Birdeye Extraction ===")
    print(f"Wallet: {test_wallet.wallet_address}")
    print(f"Expected: Win Rate 7D ~79%, 30D ~76%")
    print(f"Expected: Realized ~$12-17K, Unrealized ~$4-6K")
    print(f"Expected: Hold Time 7D ~1h, 30D ~8h")
    print("=" * 40)
    
    async with BirdeyeScraper(config) as scraper:
        enriched = await scraper.enrich_wallet(test_wallet)
        
        print(f"\n=== RESULTS ===")
        print(f"win_rate_7d: {enriched.win_rate_7d}")
        print(f"realized_pnl_7d: {enriched.realized_pnl_7d}")
        print(f"unrealized_pnl_7d: {enriched.unrealized_pnl_7d}")
        print(f"avg_holding_time_7d: {enriched.avg_holding_time_7d}")
        print()
        print(f"win_rate_30d: {enriched.win_rate_30d}")
        print(f"realized_pnl_30d: {enriched.realized_pnl_30d}")
        print(f"unrealized_pnl_30d: {enriched.unrealized_pnl_30d}")
        print(f"avg_holding_time_30d: {enriched.avg_holding_time_30d}")
        print("=" * 40)
        
        # Verify we got data
        success = (
            enriched.win_rate_7d is not None and
            enriched.win_rate_30d is not None and
            enriched.realized_pnl_7d is not None
        )
        
        if success:
            print("\n✅ BIRDEYE EXTRACTION SUCCESSFUL!")
        else:
            print("\n❌ BIRDEYE EXTRACTION FAILED - Some fields are None")
        
        return success

if __name__ == "__main__":
    result = asyncio.run(test_birdeye_extraction())
    exit(0 if result else 1)
