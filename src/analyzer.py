"""
Analysis Engine for Smart Wallet Tracker.

Aggregates trader data by wallet, calculates composite scores,
and ranks wallets to identify "smart money" traders.

Scoring Algorithm:
    Score = (Consistency × 0.40) +      # Appearances in multiple tokens
            (Profitability × 0.25) +     # Total PnL
            (Win_Rate × 0.20) +          # Percentage profitable trades
            (Position_Size × 0.15)       # Average buy amount
"""

from collections import defaultdict
from typing import Dict, List, Optional

from .models import SmartWallet, Trader, WalletStats
from .utils import load_config, setup_logging

# Module logger
logger = setup_logging("analyzer")


def aggregate_wallet_data(traders: List[Trader]) -> Dict[str, WalletStats]:
    """
    Group trader data by wallet address.
    
    Takes a list of Trader objects (potentially from multiple tokens)
    and groups them by wallet address to calculate aggregate statistics.
    
    Args:
        traders: List of Trader objects from scraping
        
    Returns:
        Dict mapping wallet_address to WalletStats
        
    Example:
        >>> traders = [Trader("wallet1", "token1", ...), Trader("wallet1", "token2", ...)]
        >>> stats = aggregate_wallet_data(traders)
        >>> stats["wallet1"].appearances
        2
    """
    logger.info(f"Aggregating data for {len(traders)} trader records")
    
    wallet_map: Dict[str, WalletStats] = defaultdict(
        lambda: WalletStats(wallet_address="")
    )
    
    for trader in traders:
        if not trader.is_valid():
            logger.debug(f"Skipping invalid trader record: {trader.wallet_address}")
            continue
            
        wallet = trader.wallet_address
        
        if wallet_map[wallet].wallet_address == "":
            wallet_map[wallet] = WalletStats(wallet_address=wallet)
            
        wallet_map[wallet].trades.append(trader)
        
    # Filter out empty entries
    result = {k: v for k, v in wallet_map.items() if v.trades}
    
    logger.info(f"Aggregated into {len(result)} unique wallets")
    return result


def calculate_wallet_score(
    wallet_stats: WalletStats,
    config: Optional[dict] = None
) -> float:
    """
    Calculate composite score for a wallet.
    
    Uses weighted algorithm based on:
    - Consistency: Number of tokens appeared in (40%)
    - Profitability: Total PnL in USD (25%)
    - Win Rate: Percentage of profitable trades (20%)
    - Position Size: Average buy amount (15%)
    
    All components are normalized to 0-1 before weighting.
    Final score is scaled to 0-100.
    
    Args:
        wallet_stats: WalletStats object with aggregated data
        config: Optional config dict (loads from file if not provided)
        
    Returns:
        Score between 0 and 100
        
    Example:
        >>> stats = WalletStats("wallet", trades=[...])
        >>> score = calculate_wallet_score(stats)
        >>> 0 <= score <= 100
        True
    """
    if config is None:
        config = load_config()
        
    scoring = config["scoring"]
    
    # Component weights
    w_consistency = scoring["consistency_weight"]
    w_profitability = scoring["profitability_weight"]
    w_win_rate = scoring["win_rate_weight"]
    w_position = scoring["position_size_weight"]
    
    # Normalization caps
    max_appearances = scoring["max_appearances_for_perfect_score"]
    max_pnl = scoring["max_pnl_for_perfect_score"]
    max_position = scoring["max_position_for_perfect_score"]
    
    # 1. Consistency Score (0-1)
    # Higher weight for appearing in multiple tokens
    consistency = min(wallet_stats.appearances / max_appearances, 1.0)
    
    # 2. Profitability Score (0-1)
    # Normalize PnL (negative = 0, positive normalized up to cap)
    total_pnl = max(wallet_stats.total_pnl, 0)  # Floor at 0
    profitability = min(total_pnl / max_pnl, 1.0)
    
    # 3. Win Rate Score (0-1)
    # Already a 0-1 value
    win_rate = wallet_stats.win_rate
    
    # 4. Position Size Score (0-1)
    # Strong conviction = larger positions
    avg_position = wallet_stats.avg_position_size
    position_score = min(avg_position / max_position, 1.0)
    
    # Weighted combination
    score = (
        consistency * w_consistency +
        profitability * w_profitability +
        win_rate * w_win_rate +
        position_score * w_position
    )
    
    # Scale to 0-100
    return round(score * 100, 2)


def create_smart_wallet(
    wallet_stats: WalletStats,
    config: Optional[dict] = None
) -> SmartWallet:
    """
    Convert WalletStats to SmartWallet with calculated score.
    
    Args:
        wallet_stats: Aggregated wallet statistics
        config: Optional config dict
        
    Returns:
        SmartWallet object with score calculated
    """
    score = calculate_wallet_score(wallet_stats, config)
    
    return SmartWallet(
        wallet_address=wallet_stats.wallet_address,
        appearances=wallet_stats.appearances,
        total_pnl=round(wallet_stats.total_pnl, 2),
        avg_pnl=round(wallet_stats.avg_pnl, 2),
        win_rate=round(wallet_stats.win_rate, 4),
        avg_position_size=round(wallet_stats.avg_position_size, 2),
        total_txn_count=wallet_stats.total_txn_count,
        score=score,
        tokens_list=wallet_stats.tokens_list
    )


def apply_filters(
    wallets: List[SmartWallet],
    config: Optional[dict] = None
) -> List[SmartWallet]:
    """
    Filter out low-quality or suspicious wallets.
    
    Removes wallets that:
    - Appear in fewer than min_appearances tokens (lucky one-hit wonders)
    - Have negative or zero total PnL (unprofitable overall)
    - Have fewer than min_transactions total (insufficient data)
    
    Args:
        wallets: List of SmartWallet objects
        config: Optional config dict
        
    Returns:
        Filtered list of SmartWallet objects
    """
    if config is None:
        config = load_config()
        
    filters = config["filters"]
    min_appearances = filters["min_appearances"]
    min_pnl = filters["min_total_pnl"]
    min_txns = filters["min_transactions"]
    
    logger.info(f"Applying filters (min_appearances={min_appearances}, "
                f"min_pnl=${min_pnl}, min_txns={min_txns})")
    
    filtered = []
    
    for wallet in wallets:
        # Check minimum appearances
        if wallet.appearances < min_appearances:
            logger.debug(f"Filtered {wallet.get_short_address()}: "
                        f"appearances={wallet.appearances} < {min_appearances}")
            continue
            
        # Check minimum PnL
        if wallet.total_pnl < min_pnl:
            logger.debug(f"Filtered {wallet.get_short_address()}: "
                        f"pnl=${wallet.total_pnl} < ${min_pnl}")
            continue
            
        # Check minimum transactions
        if wallet.total_txn_count < min_txns:
            logger.debug(f"Filtered {wallet.get_short_address()}: "
                        f"txns={wallet.total_txn_count} < {min_txns}")
            continue
            
        filtered.append(wallet)
        
    logger.info(f"Filtered {len(wallets)} → {len(filtered)} wallets")
    return filtered


def rank_wallets(
    wallets: List[SmartWallet],
    top_n: Optional[int] = None
) -> List[SmartWallet]:
    """
    Sort wallets by score and return top N.
    
    Args:
        wallets: List of SmartWallet objects
        top_n: Maximum number to return (None = return all)
        
    Returns:
        Sorted list of SmartWallet objects (highest score first)
    """
    # Primary sort: score (descending)
    # Secondary sort: appearances (descending, for tie-breaking)
    # Tertiary sort: total_pnl (descending, for tie-breaking)
    sorted_wallets = sorted(
        wallets,
        key=lambda w: (w.score, w.appearances, w.total_pnl),
        reverse=True
    )
    
    if top_n:
        sorted_wallets = sorted_wallets[:top_n]
        
    logger.info(f"Ranked wallets: top score = {sorted_wallets[0].score if sorted_wallets else 'N/A'}")
    return sorted_wallets


def analyze_traders(
    traders: List[Trader],
    config: Optional[dict] = None
) -> List[SmartWallet]:
    """
    Full analysis pipeline: aggregate → score → filter → rank.
    
    Convenience function that runs the complete analysis pipeline
    on a list of trader records.
    
    Args:
        traders: List of Trader objects from scraping
        config: Optional config dict
        
    Returns:
        Ranked list of SmartWallet objects
        
    Example:
        >>> traders = scrape_all_tokens()
        >>> smart_wallets = analyze_traders(traders)
        >>> print(smart_wallets[0].score)
        92.5
    """
    if config is None:
        config = load_config()
        
    logger.info("Starting analysis pipeline...")
    
    # Step 1: Aggregate by wallet
    wallet_stats = aggregate_wallet_data(traders)
    
    # Step 2: Create SmartWallet objects with scores
    smart_wallets = [
        create_smart_wallet(stats, config)
        for stats in wallet_stats.values()
    ]
    
    # Step 3: Apply filters
    filtered = apply_filters(smart_wallets, config)
    
    # Step 4: Rank by score
    top_n = config["output"]["top_wallets_to_display"]
    ranked = rank_wallets(filtered, top_n=None)  # Return all, display limits later
    
    logger.info(f"Analysis complete: {len(ranked)} smart wallets identified")
    return ranked
