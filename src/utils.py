"""
Utility functions for Smart Wallet Tracker.

Provides helpers for parsing, logging, configuration, and data persistence.
"""

import csv
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.json"
DATA_DIR = PROJECT_ROOT / "data"
DEBUG_HTML_DIR = PROJECT_ROOT / "debug_html"


def setup_logging(
    name: str = "wallet_tracker",
    level: int = logging.INFO,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure and return a logger with console and optional file output.
    
    Args:
        name: Logger name
        level: Logging level (default INFO)
        log_file: Optional path to log file
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from JSON file with defaults.
    
    Args:
        config_path: Path to config file (defaults to config/config.json)
        
    Returns:
        Configuration dictionary
    """
    path = config_path or CONFIG_PATH
    
    defaults = {
        "scraping": {
            "delay_min_seconds": 2.0,
            "delay_max_seconds": 4.0,
            "max_tokens_per_run": 20,
            "top_traders_limit": 50,
            "page_load_timeout_ms": 30000,
            "retry_attempts": 3,
            "retry_delay_seconds": 5
        },
        "filters": {
            "min_token_volume": 100000,
            "min_price_gain_pct": 500,
            "min_appearances": 2,
            "min_total_pnl": 1000,
            "min_transactions": 3,
            "wallet_blacklist": []
        },
        "scoring": {
            "consistency_weight": 0.40,
            "profitability_weight": 0.25,
            "win_rate_weight": 0.20,
            "position_size_weight": 0.15,
            "max_appearances_for_perfect_score": 10,
            "max_pnl_for_perfect_score": 50000,
            "max_position_for_perfect_score": 5000
        },
        "output": {
            "top_wallets_to_display": 10,
            "tokens_file": "data/tokens.csv",
            "traders_file": "data/traders.csv",
            "smart_wallets_file": "data/smart_wallets.csv"
        }
    }
    
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            # Merge with defaults (loaded values take precedence)
            for key in defaults:
                if key in loaded:
                    defaults[key].update(loaded[key])
                    
    return defaults


def parse_currency(text: str) -> Optional[float]:
    """
    Parse currency strings to float values.
    
    Handles formats:
        - "$1,234.56" -> 1234.56
        - "$1.2K" -> 1200.0
        - "$1.5M" -> 1500000.0
        - "-$500" -> -500.0
        - "$0" -> 0.0
        
    Args:
        text: Currency string to parse
        
    Returns:
        Float value or None if parsing fails
    """
    if not text or not isinstance(text, str):
        return None
    
    text = text.strip()
    
    # Handle negative values
    is_negative = text.startswith("-") or text.startswith("(-")
    
    # Remove currency symbols and parentheses
    cleaned = re.sub(r"[$,()−]", "", text)
    cleaned = cleaned.replace("−", "-")  # Unicode minus
    
    # Handle suffixes
    multiplier = 1.0
    if cleaned.upper().endswith("K"):
        multiplier = 1_000
        cleaned = cleaned[:-1]
    elif cleaned.upper().endswith("M"):
        multiplier = 1_000_000
        cleaned = cleaned[:-1]
    elif cleaned.upper().endswith("B"):
        multiplier = 1_000_000_000
        cleaned = cleaned[:-1]
    
    try:
        value = float(cleaned) * multiplier
        return -abs(value) if is_negative else value
    except (ValueError, TypeError):
        return None


def parse_percentage(text: str) -> Optional[float]:
    """
    Parse percentage strings to float values.
    
    Handles formats:
        - "+500%" -> 500.0
        - "-20.5%" -> -20.5
        - "100%" -> 100.0
        
    Args:
        text: Percentage string to parse
        
    Returns:
        Float percentage value or None if parsing fails
    """
    if not text or not isinstance(text, str):
        return None
    
    text = text.strip()
    
    # Remove percentage sign and handle special chars
    cleaned = re.sub(r"[%+]", "", text)
    cleaned = cleaned.replace("−", "-")  # Unicode minus
    
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def parse_txn_count(text: str) -> Optional[int]:
    """
    Parse transaction count strings.
    
    Handles formats:
        - "15 txns" -> 15
        - "3" -> 3
        - "1 txn" -> 1
        
    Args:
        text: Transaction count string
        
    Returns:
        Integer count or None if parsing fails
    """
    if not text or not isinstance(text, str):
        return None
    
    # Extract first number
    match = re.search(r"(\d+)", text.strip())
    if match:
        return int(match.group(1))
    return None


def save_to_csv(
    data: List[Dict[str, Any]], 
    filepath: Union[str, Path],
    fieldnames: Optional[List[str]] = None
) -> bool:
    """
    Save list of dictionaries to CSV file.
    
    Args:
        data: List of dictionaries to save
        filepath: Output file path
        fieldnames: Optional list of column names (inferred from data if not provided)
        
    Returns:
        True if successful, False otherwise
    """
    if not data:
        return False
    
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    if fieldnames is None:
        fieldnames = list(data[0].keys())
    
    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        return True
    except (IOError, OSError) as e:
        logger = logging.getLogger("wallet_tracker")
        logger.error(f"Failed to save CSV to {filepath}: {e}")
        return False


def save_to_xlsx(
    data: List[Dict[str, Any]],
    filepath: Union[str, Path]
) -> bool:
    """
    Save list of dictionaries to XLSX file using pandas with formatting.
    """
    if not data:
        logger = logging.getLogger("wallet_tracker")
        logger.warning(f"No data to save to {filepath}")
        return False
        
    filepath = Path(filepath)
    # Ensure directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        df = pd.DataFrame(data)
        
        # Use ExcelWriter with openpyxl engine for styling
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Smart Wallets')
            
            # Access the worksheet to apply styles
            worksheet = writer.sheets['Smart Wallets']
            
            # Auto-filter
            worksheet.auto_filter.ref = worksheet.dimensions
            
            # Adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                # Set width (with padding, cap at 60)
                adjusted_width = min(max_length + 2, 60)
                worksheet.column_dimensions[column_letter].width = adjusted_width
                
        return True
    except Exception as e:
        logger = logging.getLogger("wallet_tracker")
        logger.error(f"Failed to save XLSX to {filepath}: {e}")
        return False


def load_from_csv(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Load data from CSV file.
    
    Args:
        filepath: Path to CSV file
        
    Returns:
        List of dictionaries (empty list if file doesn't exist or error)
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        return []
    
    try:
        with open(filepath, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except (IOError, OSError) as e:
        logger = logging.getLogger("wallet_tracker")
        logger.error(f"Failed to load CSV from {filepath}: {e}")
        return []


def save_debug_html(
    html_content: str,
    identifier: str,
    subdir: Optional[str] = None
) -> Path:
    """
    Save HTML content for debugging purposes.
    
    Args:
        html_content: HTML string to save
        identifier: Unique identifier (e.g., token address)
        subdir: Optional subdirectory
        
    Returns:
        Path to saved file
    """
    base_dir = DEBUG_HTML_DIR
    if subdir:
        base_dir = base_dir / subdir
    base_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{identifier}_{timestamp}.html"
    filepath = base_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return filepath


def extract_wallet_from_solscan_url(url: str) -> Optional[str]:
    """
    Extract wallet address from Solscan URL.
    
    Args:
        url: Solscan account URL
        
    Returns:
        Wallet address or None
        
    Example:
        "https://solscan.io/account/ABC123..." -> "ABC123..."
    """
    if not url or "solscan.io/account/" not in url:
        return None
    
    match = re.search(r"solscan\.io/account/([A-Za-z0-9]+)", url)
    if match:
        return match.group(1)
    return None


def extract_token_from_dexscreener_url(url: str) -> Optional[str]:
    """
    Extract token address from DEX Screener URL.
    
    Args:
        url: DEX Screener token URL
        
    Returns:
        Token address or None
        
    Example:
        "/solana/ABC123..." -> "ABC123..."
    """
    if not url:
        return None
    
    # Handle both full URLs and relative paths
    match = re.search(r"/solana/([A-Za-z0-9]+)", url)
    if match:
        return match.group(1)
    return None


def format_currency(value: float, precision: int = 2) -> str:
    """
    Format a number as currency string.
    
    Args:
        value: Numeric value
        precision: Decimal places
        
    Returns:
        Formatted string (e.g., "$1,234.56", "$1.5M")
    """
    abs_value = abs(value)
    prefix = "-" if value < 0 else ""
    
    if abs_value >= 1_000_000_000:
        return f"{prefix}${abs_value / 1_000_000_000:.{precision}f}B"
    elif abs_value >= 1_000_000:
        return f"{prefix}${abs_value / 1_000_000:.{precision}f}M"
    elif abs_value >= 1_000:
        return f"{prefix}${abs_value:,.{precision}f}"
    else:
        return f"{prefix}${abs_value:.{precision}f}"


def format_percentage(value: float, precision: int = 1) -> str:
    """
    Format a number as percentage string.
    
    Args:
        value: Percentage value
        precision: Decimal places
        
    Returns:
        Formatted string (e.g., "+500.0%", "-20.5%")
    """
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.{precision}f}%"
