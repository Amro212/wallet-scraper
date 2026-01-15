"""
Unit tests for utility functions.
"""

import pytest
from src.utils import (
    parse_currency,
    parse_percentage,
    parse_txn_count,
    extract_wallet_from_solscan_url,
    extract_token_from_dexscreener_url,
    format_currency,
    format_percentage
)


class TestParseCurrency:
    """Tests for parse_currency function."""
    
    def test_basic_dollar_amount(self):
        assert parse_currency("$1234.56") == 1234.56
        
    def test_with_commas(self):
        assert parse_currency("$1,234.56") == 1234.56
        assert parse_currency("$1,234,567.89") == 1234567.89
        
    def test_k_suffix(self):
        assert parse_currency("$1.2K") == 1200.0
        assert parse_currency("$1.5k") == 1500.0
        assert parse_currency("$10K") == 10000.0
        
    def test_m_suffix(self):
        assert parse_currency("$1.5M") == 1500000.0
        assert parse_currency("$2.5m") == 2500000.0
        
    def test_b_suffix(self):
        assert parse_currency("$1B") == 1000000000.0
        assert parse_currency("$1.5B") == 1500000000.0
        
    def test_negative_values(self):
        assert parse_currency("-$500") == -500.0
        assert parse_currency("-$1.2K") == -1200.0
        assert parse_currency("(-$500)") == -500.0
        
    def test_zero(self):
        assert parse_currency("$0") == 0.0
        assert parse_currency("$0.00") == 0.0
        
    def test_invalid_input(self):
        assert parse_currency(None) is None
        assert parse_currency("") is None
        assert parse_currency("invalid") is None
        

class TestParsePercentage:
    """Tests for parse_percentage function."""
    
    def test_positive_percentage(self):
        assert parse_percentage("+500%") == 500.0
        assert parse_percentage("+20.5%") == 20.5
        
    def test_negative_percentage(self):
        assert parse_percentage("-20%") == -20.0
        assert parse_percentage("-5.5%") == -5.5
        
    def test_no_sign(self):
        assert parse_percentage("100%") == 100.0
        assert parse_percentage("50.5%") == 50.5
        
    def test_invalid_input(self):
        assert parse_percentage(None) is None
        assert parse_percentage("") is None
        

class TestParseTxnCount:
    """Tests for parse_txn_count function."""
    
    def test_with_txns_suffix(self):
        assert parse_txn_count("15 txns") == 15
        assert parse_txn_count("1 txn") == 1
        
    def test_number_only(self):
        assert parse_txn_count("42") == 42
        
    def test_invalid_input(self):
        assert parse_txn_count(None) is None
        assert parse_txn_count("") is None
        

class TestExtractWalletFromSolscanUrl:
    """Tests for extract_wallet_from_solscan_url function."""
    
    def test_valid_url(self):
        url = "https://solscan.io/account/4zBx9QXXXXXXXXXXXXXXXX"
        assert extract_wallet_from_solscan_url(url) == "4zBx9QXXXXXXXXXXXXXXXX"
        
    def test_invalid_url(self):
        assert extract_wallet_from_solscan_url("https://example.com") is None
        assert extract_wallet_from_solscan_url(None) is None
        

class TestExtractTokenFromDexscreenerUrl:
    """Tests for extract_token_from_dexscreener_url function."""
    
    def test_relative_path(self):
        assert extract_token_from_dexscreener_url("/solana/ABC123") == "ABC123"
        
    def test_full_url(self):
        url = "https://dexscreener.com/solana/ABC123XYZ"
        assert extract_token_from_dexscreener_url(url) == "ABC123XYZ"
        
    def test_invalid_url(self):
        assert extract_token_from_dexscreener_url("/ethereum/ABC") is None
        assert extract_token_from_dexscreener_url(None) is None


class TestFormatCurrency:
    """Tests for format_currency function."""
    
    def test_basic_format(self):
        assert format_currency(1234.56) == "$1,234.56"
        
    def test_millions(self):
        assert format_currency(1500000) == "$1.50M"
        
    def test_billions(self):
        assert format_currency(2500000000) == "$2.50B"
        
    def test_negative(self):
        assert format_currency(-1234.56) == "-$1,234.56"


class TestFormatPercentage:
    """Tests for format_percentage function."""
    
    def test_positive(self):
        assert format_percentage(500) == "+500.0%"
        
    def test_negative(self):
        assert format_percentage(-20.5) == "-20.5%"
        
    def test_zero(self):
        assert format_percentage(0) == "0.0%"
