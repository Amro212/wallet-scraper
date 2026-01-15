"""
Unit tests for analyzer functions.
"""

import pytest
from src.models import Trader, WalletStats, SmartWallet
from src.analyzer import (
    aggregate_wallet_data,
    calculate_wallet_score,
    create_smart_wallet,
    apply_filters,
    rank_wallets
)


@pytest.fixture
def sample_traders():
    """Create sample trader data for testing."""
    return [
        Trader(
            wallet_address="wallet1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            token_address="token1",
            bought_usd=1000.0,
            sold_usd=2500.0,
            pnl_usd=1500.0,
            txn_count=5
        ),
        Trader(
            wallet_address="wallet1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            token_address="token2",
            bought_usd=2000.0,
            sold_usd=5000.0,
            pnl_usd=3000.0,
            txn_count=8
        ),
        Trader(
            wallet_address="wallet2XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            token_address="token1",
            bought_usd=500.0,
            sold_usd=400.0,
            pnl_usd=-100.0,
            txn_count=2
        ),
        Trader(
            wallet_address="wallet3XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            token_address="token1",
            bought_usd=5000.0,
            sold_usd=25000.0,
            pnl_usd=20000.0,
            txn_count=10
        ),
        Trader(
            wallet_address="wallet3XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            token_address="token2",
            bought_usd=3000.0,
            sold_usd=9000.0,
            pnl_usd=6000.0,
            txn_count=7
        ),
        Trader(
            wallet_address="wallet3XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            token_address="token3",
            bought_usd=4000.0,
            sold_usd=8000.0,
            pnl_usd=4000.0,
            txn_count=6
        ),
    ]


class TestAggregateWalletData:
    """Tests for aggregate_wallet_data function."""
    
    def test_groups_by_wallet(self, sample_traders):
        result = aggregate_wallet_data(sample_traders)
        
        assert len(result) == 3
        assert "wallet1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" in result
        assert "wallet2XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" in result
        assert "wallet3XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" in result
        
    def test_counts_appearances_correctly(self, sample_traders):
        result = aggregate_wallet_data(sample_traders)
        
        # wallet1 appears in 2 tokens
        assert result["wallet1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"].appearances == 2
        
        # wallet2 appears in 1 token
        assert result["wallet2XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"].appearances == 1
        
        # wallet3 appears in 3 tokens
        assert result["wallet3XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"].appearances == 3
        
    def test_calculates_total_pnl(self, sample_traders):
        result = aggregate_wallet_data(sample_traders)
        
        # wallet1: 1500 + 3000 = 4500
        assert result["wallet1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"].total_pnl == 4500.0
        
        # wallet3: 20000 + 6000 + 4000 = 30000
        assert result["wallet3XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"].total_pnl == 30000.0
        
    def test_calculates_win_rate(self, sample_traders):
        result = aggregate_wallet_data(sample_traders)
        
        # wallet1: 2/2 = 100%
        assert result["wallet1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"].win_rate == 1.0
        
        # wallet2: 0/1 = 0%
        assert result["wallet2XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"].win_rate == 0.0
        
        # wallet3: 3/3 = 100%
        assert result["wallet3XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"].win_rate == 1.0


class TestCalculateWalletScore:
    """Tests for calculate_wallet_score function."""
    
    def test_score_range(self, sample_traders):
        result = aggregate_wallet_data(sample_traders)
        
        for wallet_stats in result.values():
            score = calculate_wallet_score(wallet_stats)
            assert 0 <= score <= 100
            
    def test_higher_appearances_higher_score(self, sample_traders):
        result = aggregate_wallet_data(sample_traders)
        
        score_wallet1 = calculate_wallet_score(result["wallet1XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"])
        score_wallet3 = calculate_wallet_score(result["wallet3XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"])
        
        # wallet3 has more appearances and higher PnL, should score higher
        assert score_wallet3 > score_wallet1


class TestApplyFilters:
    """Tests for apply_filters function."""
    
    def test_filters_low_appearances(self):
        wallets = [
            SmartWallet(
                wallet_address="wallet1" + "X" * 32,
                appearances=1,  # Should be filtered
                total_pnl=5000.0,
                avg_pnl=5000.0,
                win_rate=1.0,
                avg_position_size=1000.0,
                total_txn_count=5,
                score=50.0,
                tokens_list=["token1"]
            ),
            SmartWallet(
                wallet_address="wallet2" + "X" * 32,
                appearances=3,  # Should pass
                total_pnl=10000.0,
                avg_pnl=3333.0,
                win_rate=1.0,
                avg_position_size=2000.0,
                total_txn_count=10,
                score=80.0,
                tokens_list=["token1", "token2", "token3"]
            ),
        ]
        
        result = apply_filters(wallets)
        
        assert len(result) == 1
        assert result[0].wallet_address.startswith("wallet2")
        
    def test_filters_negative_pnl(self):
        wallets = [
            SmartWallet(
                wallet_address="wallet1" + "X" * 32,
                appearances=3,
                total_pnl=-500.0,  # Should be filtered
                avg_pnl=-166.0,
                win_rate=0.0,
                avg_position_size=1000.0,
                total_txn_count=6,
                score=20.0,
                tokens_list=["t1", "t2", "t3"]
            ),
        ]
        
        result = apply_filters(wallets)
        assert len(result) == 0


class TestRankWallets:
    """Tests for rank_wallets function."""
    
    def test_sorts_by_score_descending(self):
        wallets = [
            SmartWallet(
                wallet_address="low" + "X" * 35,
                appearances=2,
                total_pnl=1000.0,
                avg_pnl=500.0,
                win_rate=0.5,
                avg_position_size=500.0,
                total_txn_count=4,
                score=30.0,
                tokens_list=["t1", "t2"]
            ),
            SmartWallet(
                wallet_address="high" + "X" * 34,
                appearances=5,
                total_pnl=50000.0,
                avg_pnl=10000.0,
                win_rate=1.0,
                avg_position_size=5000.0,
                total_txn_count=20,
                score=95.0,
                tokens_list=["t1", "t2", "t3", "t4", "t5"]
            ),
            SmartWallet(
                wallet_address="mid" + "X" * 35,
                appearances=3,
                total_pnl=10000.0,
                avg_pnl=3333.0,
                win_rate=0.8,
                avg_position_size=2000.0,
                total_txn_count=10,
                score=60.0,
                tokens_list=["t1", "t2", "t3"]
            ),
        ]
        
        result = rank_wallets(wallets)
        
        assert len(result) == 3
        assert result[0].wallet_address.startswith("high")
        assert result[1].wallet_address.startswith("mid")
        assert result[2].wallet_address.startswith("low")
        
    def test_respects_top_n(self):
        wallets = [
            SmartWallet(
                wallet_address=f"wallet{i}" + "X" * 30,
                appearances=2,
                total_pnl=1000.0 * i,
                avg_pnl=500.0,
                win_rate=0.5,
                avg_position_size=500.0,
                total_txn_count=4,
                score=float(i * 10),
                tokens_list=["t1", "t2"]
            )
            for i in range(10, 0, -1)
        ]
        
        result = rank_wallets(wallets, top_n=3)
        
        assert len(result) == 3
        assert result[0].score == 100.0
        assert result[1].score == 90.0
        assert result[2].score == 80.0
