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
import math
import re
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
    
    Uses weighted algorithm based on configurable weights for:
    - Consistency: Number of tokens appeared in
    - Profitability: Total PnL in USD
    - Win Rate: Percentage of profitable trades
    - Position Size: Average buy amount
    
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
    blacklist = set(filters.get("wallet_blacklist", []))
    
    logger.info(f"Applying filters (min_appearances={min_appearances}, "
                f"min_pnl=${min_pnl}, min_txns={min_txns})")
    if blacklist:
        logger.info(f"Blacklist active: favoring exclusion of {len(blacklist)} wallets")
    
    filtered = []
    
    for wallet in wallets:
        # Check blacklist
        if wallet.wallet_address in blacklist:
            logger.debug(f"Filtered {wallet.get_short_address()}: Blacklisted")
            continue

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


def _parse_hold_time(hold_time_str: Optional[str]) -> Optional[float]:
    """Parse hold time string to minutes (e.g. 18D, 4h, 30m)."""
    if not hold_time_str:
        return None
    
    text = hold_time_str.upper().strip()
    match = re.match(r"([\d\.]+)([A-Z]+)", text)
    if not match:
        return None
        
    val = float(match.group(1))
    unit = match.group(2)
    
    if 'D' in unit:
        return val * 24 * 60
    elif 'H' in unit:
        return val * 60
    elif 'M' in unit:
        return val
    elif 'S' in unit:
        return val / 60
    return None


def _score_hold_time(
    wallet: SmartWallet,
    scoring: dict
) -> float:
    """Score average holding time (0-1), penalizing short holds."""
    hold_time_str = wallet.avg_holding_time_7d or wallet.avg_holding_time_30d
    hold_mins = _parse_hold_time(hold_time_str)
    if hold_mins is None:
        return 0.5
    
    min_hold = scoring["min_hold_time_minutes"]
    if hold_mins <= min_hold:
        return 0.0
    
    # Asymptotic curve: longer hold => higher score with diminishing returns.
    score = 1 - math.exp(-(hold_mins - min_hold) / min_hold)
    return max(min(score, 1.0), 0.0)


def _is_hold_time_bot(wallet: SmartWallet, scoring: dict) -> bool:
    """Return True when 7D or 30D hold time is below the minimum threshold."""
    min_hold = scoring["min_hold_time_minutes"]
    hold_times = [wallet.avg_holding_time_7d, wallet.avg_holding_time_30d]
    for hold_time_str in hold_times:
        hold_mins = _parse_hold_time(hold_time_str)
        if hold_mins is not None and hold_mins < min_hold:
            return True
    return False


def _is_identical_hold_time_bot(wallet: SmartWallet) -> bool:
    """
    Return True if 7D and 30D hold times are identical.
    
    Human traders typically show variance in hold times across different
    timeframes. Identical values suggest automated/bot behavior.
    """
    if not wallet.avg_holding_time_7d or not wallet.avg_holding_time_30d:
        return False
    
    hold_7d = _parse_hold_time(wallet.avg_holding_time_7d)
    hold_30d = _parse_hold_time(wallet.avg_holding_time_30d)
    
    if hold_7d is None or hold_30d is None:
        return False
    
    # Check if times are exactly equal (within 1 minute tolerance)
    return abs(hold_7d - hold_30d) < 1.0


def _get_pnl_concentration(wallet: SmartWallet) -> float:
    """
    Calculate the concentration of PnL from the top-performing token.
    
    Returns:
        Float between 0-1 representing what % of total PnL comes from 
        the single best token. Higher = more concentrated (riskier).
    """
    if not wallet.tokens_list:
        return 0.0
    
    pnls = []
    for t in wallet.tokens_list:
        if isinstance(t, dict) and 'pnl_usd' in t:
            pnls.append(abs(t['pnl_usd']))
    
    if not pnls or sum(pnls) == 0:
        return 0.0
    
    max_pnl = max(pnls)
    total_pnl = sum(pnls)
    return max_pnl / total_pnl


def _calculate_pnl_quality_score(wallet: SmartWallet, scoring: dict) -> float:
    """
    Calculate PnL quality based on average PnL per token.
    
    This metric rewards consistency - wallets that make steady profits
    across multiple tokens rather than one lucky hit.
    
    Returns:
        Float between 0-1
    """
    if wallet.appearances == 0:
        return 0.0
    
    pnl_per_token = wallet.total_pnl / wallet.appearances
    max_pnl_per_token = scoring.get("max_pnl_per_token_for_perfect_score", 5000)
    
    # Only reward positive PnL
    if pnl_per_token <= 0:
        return 0.0
    
    return min(pnl_per_token / max_pnl_per_token, 1.0)


def calculate_degen_score(
    wallet: SmartWallet,
    config: Optional[dict] = None
) -> float:
    """
    Calculate overall "Degen Score" with weighted components.
    
    Components:
        - Win Rate (30%): Birdeye 7D win rate
        - Hold Time (25%): Penalizes short holds, rewards diamond hands
        - Consistency (20%): Appearances in multiple tokens
        - Profitability (10%): Total PnL
        - Position Size (10%): Average buy amount
        - PnL Quality (5%): PnL per token (consistency metric)
        
    Penalties:
        - PnL Concentration: -20% if >80% of PnL from single token
    """
    if config is None:
        config = load_config()
        
    scoring = config["scoring"]
    filters = config.get("filters", {})
    
    # Weights
    w_consistency = scoring["consistency_weight"]
    w_profitability = scoring["profitability_weight"]
    w_win_rate = scoring["win_rate_weight"]
    w_hold_time = scoring["hold_time_weight"]
    w_position = scoring["position_size_weight"]
    w_pnl_quality = scoring.get("pnl_quality_weight", 0.05)
    
    # Normalization caps
    max_appearances = scoring["max_appearances_for_perfect_score"]
    max_pnl = scoring["max_pnl_for_perfect_score"]
    max_position = scoring["max_position_for_perfect_score"]
    
    # Penalties
    pnl_concentration_penalty = scoring.get("pnl_concentration_penalty", 0.20)
    
    # Calculate component scores
    win_rate = wallet.win_rate_7d if wallet.win_rate_7d is not None else wallet.win_rate
    hold_score = _score_hold_time(wallet, scoring)
    pnl_quality_score = _calculate_pnl_quality_score(wallet, scoring)
    
    appearances_score = min(wallet.appearances / max_appearances, 1.0)
    total_pnl = max(wallet.total_pnl, 0)
    profitability_score = min(total_pnl / max_pnl, 1.0)
    position_score = min(wallet.avg_position_size / max_position, 1.0)
    
    # Base score calculation
    score = (
        win_rate * w_win_rate +
        hold_score * w_hold_time +
        appearances_score * w_consistency +
        profitability_score * w_profitability +
        position_score * w_position +
        pnl_quality_score * w_pnl_quality
    )
    
    # Apply PnL concentration penalty
    concentration = _get_pnl_concentration(wallet)
    if concentration > 0.80:
        # Additional penalty if low win rate + high concentration
        min_win_rate = filters.get("min_win_rate_7d", 0.50)
        if win_rate < min_win_rate:
            # Double penalty for low win rate + concentrated PnL
            score *= (1 - pnl_concentration_penalty * 1.5)
        else:
            score *= (1 - pnl_concentration_penalty)
    
    return round(score * 100, 2)


def rescore_wallets(
    wallets: List[SmartWallet],
    config: Optional[dict] = None
) -> List[SmartWallet]:
    """
    Re-score and re-rank wallets after Birdeye enrichment.
    
    Applies bot detection filters:
        - Hold time below minimum (90 min default)
        - Identical 7D/30D hold times (bot pattern)
        - Win rate below minimum (50% default)
        
    Then recalculates Degen Score with new metrics.
    """
    logger.info("Rescoring wallets with Degen Score logic...")
    processed = []
    filtered_counts = {
        "hold_time_bot": 0,
        "identical_hold_time": 0,
        "low_win_rate": 0,
        "zero_score": 0
    }
    
    if config is None:
        config = load_config()
    
    scoring = config.get("scoring", {})
    filters = config.get("filters", {})
    min_win_rate = filters.get("min_win_rate_7d", 0.50)
    
    for w in wallets:
        # Bot Detection Filter 1: Hold time below minimum
        if _is_hold_time_bot(w, scoring):
            logger.debug(f"Filtered {w.get_short_address()} (HoldTime<Min)")
            filtered_counts["hold_time_bot"] += 1
            continue
        
        # Bot Detection Filter 2: Identical 7D/30D hold times
        if _is_identical_hold_time_bot(w):
            logger.debug(f"Filtered {w.get_short_address()} (Identical 7D/30D HoldTime)")
            filtered_counts["identical_hold_time"] += 1
            continue
        
        # Bot Detection Filter 3: Win rate below minimum
        win_rate = w.win_rate_7d if w.win_rate_7d is not None else w.win_rate
        if win_rate < min_win_rate:
            logger.debug(f"Filtered {w.get_short_address()} (WinRate={win_rate:.1%} < {min_win_rate:.0%})")
            filtered_counts["low_win_rate"] += 1
            continue
        
        # Recalculate score with new metrics
        new_score = calculate_degen_score(w, config)
        w.score = new_score
        
        # Filter zero scores
        if new_score > 0:
            processed.append(w)
        else:
            logger.debug(f"Filtered {w.get_short_address()} (Score=0)")
            filtered_counts["zero_score"] += 1
    
    # Log summary
    total_filtered = sum(filtered_counts.values())
    logger.info(f"Filtered {total_filtered} wallets: "
                f"hold_time={filtered_counts['hold_time_bot']}, "
                f"identical_hold={filtered_counts['identical_hold_time']}, "
                f"low_win_rate={filtered_counts['low_win_rate']}, "
                f"zero_score={filtered_counts['zero_score']}")
    logger.info(f"Remaining: {len(processed)} wallets")
    
    # Sort by new score
    return sorted(processed, key=lambda w: w.score, reverse=True)

