"""
Data models for Smart Wallet Tracker.

Defines dataclasses for Token, Trader, and SmartWallet with type hints
and validation methods.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict


@dataclass
class Token:
    """
    Represents a successful Solana memecoin from DEX Screener.
    
    Attributes:
        address: Token contract address on Solana (base58, case-sensitive)
        pair_address: DEX pair address (from URL, may be lowercase)
        name: Human-readable token name
        symbol: Token ticker symbol
        volume_24h: 24-hour trading volume in USD
        price_change_24h: 24-hour price change percentage
        market_cap: Market capitalization in USD
        dex_url: Full DexScreener URL for this token
        timestamp: When the token data was scraped
    """
    address: str  # The actual token address (from API)
    pair_address: str  # The pair address from URL
    name: str
    symbol: str
    volume_24h: float
    price_change_24h: float
    market_cap: float = 0.0
    dex_url: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_valid(self) -> bool:
        """Check if token has valid, non-empty data."""
        return bool(
            self.address and 
            len(self.address) >= 32 and
            self.volume_24h > 0
        )
    
    def meets_criteria(self, min_volume: float, min_gain: float, min_mcap: float = 0) -> bool:
        """Check if token meets filtering criteria."""
        return (
            self.volume_24h >= min_volume and 
            self.price_change_24h >= min_gain and
            self.market_cap >= min_mcap
        )


@dataclass
class Trader:
    """
    Represents a trader's performance on a specific token.
    
    Scraped from DEX Screener's "Top Traders" tab for each token.
    
    Attributes:
        wallet_address: Solana wallet address
        token_address: Token this trade data relates to
        bought_usd: Total USD value bought
        sold_usd: Total USD value sold
        pnl_usd: Profit/loss in USD
        txn_count: Number of transactions
        timestamp: When the data was scraped
    """
    wallet_address: str
    token_address: str
    token_symbol: str
    bought_usd: float
    sold_usd: float
    pnl_usd: float
    dex_url: str = ""
    txn_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_valid(self) -> bool:
        """Check if trader has valid wallet address and data."""
        return bool(
            self.wallet_address and 
            len(self.wallet_address) >= 32 and
            len(self.wallet_address) >= 32 and
            self.token_address and
            self.token_symbol
        )
    
    def is_profitable(self) -> bool:
        """Check if this trade was profitable."""
        return self.pnl_usd > 0


@dataclass
class SmartWallet:
    """
    Aggregated statistics for a wallet across multiple tokens.
    
    This is the final ranked output showing "smart money" wallets
    that appear in multiple successful token launches.
    
    Attributes:
        wallet_address: Solana wallet address
        appearances: Number of successful tokens this wallet traded
        total_pnl: Total profit/loss across all tokens
        avg_pnl: Average PnL per token
        win_rate: Percentage of profitable trades (0-1)
        avg_position_size: Average buy amount in USD
        total_txn_count: Total transactions across all tokens
        score: Composite score (0-100)
        tokens_list: List of token addresses traded
    """
    wallet_address: str
    appearances: int
    total_pnl: float
    avg_pnl: float
    win_rate: float
    avg_position_size: float
    total_txn_count: int = 0
    score: float = 0.0
    tokens_list: List[Dict[str, str]] = field(default_factory=list)
    
    # Birdeye 7D metrics
    win_rate_7d: Optional[float] = None
    realized_pnl_7d: Optional[float] = None
    unrealized_pnl_7d: Optional[float] = None
    avg_holding_time_7d: Optional[str] = None
    
    # Birdeye 30D metrics
    win_rate_30d: Optional[float] = None
    realized_pnl_30d: Optional[float] = None
    unrealized_pnl_30d: Optional[float] = None
    avg_holding_time_30d: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if smart wallet has valid data."""
        return bool(
            self.wallet_address and 
            len(self.wallet_address) >= 32 and
            self.appearances >= 1
        )
    
    def get_short_address(self, length: int = 8) -> str:
        """Return abbreviated wallet address for display."""
        if len(self.wallet_address) <= length * 2:
            return self.wallet_address
        return f"{self.wallet_address[:length]}...{self.wallet_address[-length:]}"


@dataclass 
class WalletStats:
    """
    Intermediate aggregation of wallet statistics.
    
    Used during analysis before creating final SmartWallet objects.
    """
    wallet_address: str
    trades: List[Trader] = field(default_factory=list)
    
    @property
    def appearances(self) -> int:
        """Number of unique tokens traded."""
        return len(set(t.token_address for t in self.trades))
    
    @property
    def total_pnl(self) -> float:
        """Total profit/loss across all trades."""
        return sum(t.pnl_usd for t in self.trades)
    
    @property
    def avg_pnl(self) -> float:
        """Average PnL per trade."""
        if not self.trades:
            return 0.0
        return self.total_pnl / len(self.trades)
    
    @property
    def win_rate(self) -> float:
        """Percentage of profitable trades."""
        if not self.trades:
            return 0.0
        winning = sum(1 for t in self.trades if t.pnl_usd > 0)
        return winning / len(self.trades)
    
    @property
    def avg_position_size(self) -> float:
        """Average buy amount in USD."""
        if not self.trades:
            return 0.0
        return sum(t.bought_usd for t in self.trades) / len(self.trades)
    
    @property
    def total_txn_count(self) -> int:
        """Total transaction count across all trades."""
        return sum(t.txn_count for t in self.trades)
    
    @property
    def tokens_list(self) -> List[Dict[str, str]]:
        """List of unique tokens traded (symbol, address, dex_url)."""
        # Use a dict to dedupe by token_address, keeping all info
        tokens_map = {}
        for t in self.trades:
            if t.token_address not in tokens_map:
                tokens_map[t.token_address] = {
                    "symbol": t.token_symbol,
                    "address": t.token_address,
                    "dex_url": t.dex_url or f"https://dexscreener.com/solana/{t.token_address}"
                }
        return list(tokens_map.values())
