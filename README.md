# Smart Wallet Tracker

Identify and track "smart money" wallets in the Solana memecoin market.

## Overview

This tool analyzes DEX Screener data to find wallets that consistently appear as top traders
across multiple successful token launches. These "smart wallets" demonstrate:

- High win rates (70-80%+)
- Early entry into successful tokens
- Strong conviction with meaningful position sizes
- Disciplined profit-taking strategies

## Quick Start

```bash
# Activate virtual environment
.\.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Run the tracker
python main.py
```

## Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate it
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Configuration

Edit `config/config.json` to adjust:

- **Scraping**: Delays, timeouts, max tokens per run
- **Filters**: Min volume, min gain %, min appearances
- **Scoring**: Weight for consistency, profitability, win rate, position size

## Output

Results are saved to:
- `data/tokens.csv` - Trending tokens scraped
- `data/traders.csv` - All trader data
- `data/smart_wallets.csv` - Ranked smart wallets

## Project Structure

```
wallet-scraper/
├── src/
│   ├── models.py      # Token, Trader, SmartWallet dataclasses
│   ├── scraper.py     # DEX Screener Playwright scraper
│   ├── analyzer.py    # Wallet scoring and ranking
│   └── utils.py       # Parsing, logging, config
├── data/              # Output CSV files
├── config/            # config.json
├── tests/             # Unit tests
└── main.py            # Entry point
```

## Running Tests

```bash
.\.venv\Scripts\pytest tests/ -v
```
