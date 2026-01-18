"""
Database module for Smart Wallet Tracker.

Provides SQLite-based persistence for tokens, traders, and smart wallets.
Prevents data loss between runs and enables historical tracking.
"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger("wallet_tracker")

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "wallet_tracker.db"


class Database:
    """SQLite database for wallet tracker data."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database connection."""
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _init_schema(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tokens table - stores token metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    pair_address TEXT PRIMARY KEY,
                    token_address TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    volume_24h REAL,
                    price_change_24h REAL,
                    market_cap REAL,
                    dex_url TEXT,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Traders table - stores trader activity per token
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS traders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT NOT NULL,
                    token_address TEXT NOT NULL,
                    token_symbol TEXT,
                    bought_usd REAL,
                    sold_usd REAL,
                    pnl_usd REAL,
                    txn_count INTEGER,
                    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(wallet_address, token_address)
                )
            """)
            
            # Smart wallets table - aggregated wallet statistics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS smart_wallets (
                    wallet_address TEXT PRIMARY KEY,
                    score REAL,
                    appearances INTEGER,
                    total_pnl REAL,
                    avg_pnl REAL,
                    avg_position_size REAL,
                    total_txn_count INTEGER,
                    win_rate_7d REAL,
                    realized_pnl_7d REAL,
                    unrealized_pnl_7d REAL,
                    avg_holding_time_7d TEXT,
                    win_rate_30d REAL,
                    realized_pnl_30d REAL,
                    unrealized_pnl_30d REAL,
                    avg_holding_time_30d TEXT,
                    tokens_json TEXT,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_traders_wallet ON traders(wallet_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_traders_token ON traders(token_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_smart_wallets_score ON smart_wallets(score DESC)")
            
            logger.info(f"Database initialized at {self.db_path}")
    
    # ==================== Token Operations ====================
    
    def upsert_token(self, token_data: Dict[str, Any]) -> bool:
        """Insert or update a token record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tokens (
                    pair_address, token_address, symbol, name,
                    volume_24h, price_change_24h, market_cap, dex_url, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pair_address) DO UPDATE SET
                    token_address = excluded.token_address,
                    symbol = excluded.symbol,
                    name = excluded.name,
                    volume_24h = excluded.volume_24h,
                    price_change_24h = excluded.price_change_24h,
                    market_cap = excluded.market_cap,
                    dex_url = excluded.dex_url,
                    last_updated = excluded.last_updated
            """, (
                token_data.get("pair_address"),
                token_data.get("token_address"),
                token_data.get("symbol"),
                token_data.get("name"),
                token_data.get("volume_24h"),
                token_data.get("price_change_24h"),
                token_data.get("market_cap"),
                token_data.get("dex_url"),
                datetime.now().isoformat()
            ))
            return True
    
    def get_token(self, pair_address: str) -> Optional[Dict[str, Any]]:
        """Get token by pair address."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tokens WHERE pair_address = ?", (pair_address,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ==================== Trader Operations ====================
    
    def upsert_trader(self, trader_data: Dict[str, Any]) -> bool:
        """Insert or update a trader record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO traders (
                    wallet_address, token_address, token_symbol,
                    bought_usd, sold_usd, pnl_usd, txn_count, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(wallet_address, token_address) DO UPDATE SET
                    token_symbol = excluded.token_symbol,
                    bought_usd = excluded.bought_usd,
                    sold_usd = excluded.sold_usd,
                    pnl_usd = excluded.pnl_usd,
                    txn_count = excluded.txn_count,
                    scraped_at = excluded.scraped_at
            """, (
                trader_data.get("wallet_address"),
                trader_data.get("token_address"),
                trader_data.get("token_symbol"),
                trader_data.get("bought_usd"),
                trader_data.get("sold_usd"),
                trader_data.get("pnl_usd"),
                trader_data.get("txn_count"),
                datetime.now().isoformat()
            ))
            return True
    
    def bulk_upsert_traders(self, traders: List[Dict[str, Any]]) -> int:
        """Bulk insert/update traders."""
        count = 0
        for trader in traders:
            if self.upsert_trader(trader):
                count += 1
        logger.info(f"Upserted {count} trader records")
        return count
    
    def get_traders_by_wallet(self, wallet_address: str) -> List[Dict[str, Any]]:
        """Get all trader records for a wallet."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM traders WHERE wallet_address = ?",
                (wallet_address,)
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== Smart Wallet Operations ====================
    
    def upsert_smart_wallet(self, wallet_data: Dict[str, Any]) -> bool:
        """Insert or update a smart wallet record."""
        # Serialize tokens list to JSON
        tokens_json = json.dumps(wallet_data.get("tokens_list", []))
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO smart_wallets (
                    wallet_address, score, appearances, total_pnl, avg_pnl,
                    avg_position_size, total_txn_count,
                    win_rate_7d, realized_pnl_7d, unrealized_pnl_7d, avg_holding_time_7d,
                    win_rate_30d, realized_pnl_30d, unrealized_pnl_30d, avg_holding_time_30d,
                    tokens_json, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(wallet_address) DO UPDATE SET
                    score = excluded.score,
                    appearances = excluded.appearances,
                    total_pnl = excluded.total_pnl,
                    avg_pnl = excluded.avg_pnl,
                    avg_position_size = excluded.avg_position_size,
                    total_txn_count = excluded.total_txn_count,
                    win_rate_7d = excluded.win_rate_7d,
                    realized_pnl_7d = excluded.realized_pnl_7d,
                    unrealized_pnl_7d = excluded.unrealized_pnl_7d,
                    avg_holding_time_7d = excluded.avg_holding_time_7d,
                    win_rate_30d = excluded.win_rate_30d,
                    realized_pnl_30d = excluded.realized_pnl_30d,
                    unrealized_pnl_30d = excluded.unrealized_pnl_30d,
                    avg_holding_time_30d = excluded.avg_holding_time_30d,
                    tokens_json = excluded.tokens_json,
                    last_updated = excluded.last_updated
            """, (
                wallet_data.get("wallet_address"),
                wallet_data.get("score"),
                wallet_data.get("appearances"),
                wallet_data.get("total_pnl"),
                wallet_data.get("avg_pnl"),
                wallet_data.get("avg_position_size"),
                wallet_data.get("total_txn_count"),
                wallet_data.get("win_rate_7d"),
                wallet_data.get("realized_pnl_7d"),
                wallet_data.get("unrealized_pnl_7d"),
                wallet_data.get("avg_holding_time_7d"),
                wallet_data.get("win_rate_30d"),
                wallet_data.get("realized_pnl_30d"),
                wallet_data.get("unrealized_pnl_30d"),
                wallet_data.get("avg_holding_time_30d"),
                tokens_json,
                datetime.now().isoformat()
            ))
            return True
    
    def get_all_smart_wallets(self, min_score: float = 0) -> List[Dict[str, Any]]:
        """Get all smart wallets, optionally filtered by minimum score."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM smart_wallets WHERE score >= ? ORDER BY score DESC",
                (min_score,)
            )
            wallets = []
            for row in cursor.fetchall():
                wallet = dict(row)
                # Deserialize tokens JSON
                wallet["tokens_list"] = json.loads(wallet.pop("tokens_json", "[]"))
                wallets.append(wallet)
            return wallets
    
    def get_smart_wallet_count(self) -> int:
        """Get total count of smart wallets in database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM smart_wallets")
            return cursor.fetchone()[0]
    
    # ==================== Export Operations ====================
    
    def export_smart_wallets_to_json(self, filepath: Path, min_score: float = 0) -> bool:
        """Export all smart wallets to JSON file for dashboard."""
        wallets = self.get_all_smart_wallets(min_score)
        
        # Add rank based on position
        for i, wallet in enumerate(wallets, 1):
            wallet["rank"] = i
            # Format percentages for display
            if wallet.get("win_rate_7d") is not None:
                wallet["win_rate_7d"] = f"{wallet['win_rate_7d']*100:.1f}%"
            else:
                wallet["win_rate_7d"] = "-"
            if wallet.get("win_rate_30d") is not None:
                wallet["win_rate_30d"] = f"{wallet['win_rate_30d']*100:.1f}%"
            else:
                wallet["win_rate_30d"] = "-"
            # Handle None values
            for key in ["realized_pnl_7d", "unrealized_pnl_7d", "realized_pnl_30d", "unrealized_pnl_30d"]:
                if wallet.get(key) is None:
                    wallet[key] = "-"
                else:
                    wallet[key] = round(wallet[key])
            for key in ["avg_holding_time_7d", "avg_holding_time_30d"]:
                if wallet.get(key) is None:
                    wallet[key] = "-"
        
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(wallets, f, indent=2, default=str)
            logger.info(f"Exported {len(wallets)} wallets to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")
            return False
    
    # ==================== Utility Operations ====================
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            stats = {}
            cursor.execute("SELECT COUNT(*) FROM tokens")
            stats["tokens"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM traders")
            stats["traders"] = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM smart_wallets")
            stats["smart_wallets"] = cursor.fetchone()[0]
            return stats


# Singleton instance
_db_instance: Optional[Database] = None


def get_database(db_path: Optional[Path] = None) -> Database:
    """Get or create database singleton."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance
