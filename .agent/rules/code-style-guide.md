---
trigger: always_on
---

# General Coding Standards

## Code Style

### Rule 1: Follow PEP 8
- 4 spaces for indentation (no tabs)
- Max line length: 88 characters
- snake_case for functions/variables
- PascalCase for classes
- UPPER_CASE for constants

```python
# Good
def calculate_wallet_score(wallet_data):
    MAX_SCORE = 100
    return min(wallet_data.pnl * WEIGHT, MAX_SCORE)

# Bad
def CalculateWalletScore(walletData):
    maxScore = 100
    return min(walletData.pnl * weight, maxScore)
```

### Rule 2: Use Type Hints
```python
from typing import List, Dict, Optional

def aggregate_data(traders: List[Trader]) -> Dict[str, WalletStats]:
    """Aggregate trader data by wallet."""
    pass

def get_token(address: str) -> Optional[Token]:
    """Returns Token or None."""
    pass
```

### Rule 3: Write Docstrings
```python
def calculate_score(wallet: SmartWallet) -> float:
    """
    Calculate composite score for wallet.
    
    Args:
        wallet: SmartWallet with trading statistics
        
    Returns:
        Score between 0-100
        
    Raises:
        ValueError: If wallet has invalid data
    """
    pass
```

---

## Code Organization

### Rule 4: Keep Functions Small
- Max 50 lines (prefer 20-30)
- Single responsibility per function
- Break long functions into smaller ones

```python
# Good - Single responsibility
def extract_wallet_address(row):
    return row.find('span', class_='wallet').text.strip()

def extract_pnl(row):
    pnl_text = row.find('td', class_='pnl').text
    return parse_currency(pnl_text)

# Bad - Too many responsibilities
def extract_all_data(row):
    # 100 lines of extraction...
```

### Rule 5: Use Meaningful Names
```python
# Good
successful_tokens = get_trending_tokens(min_gain=500)
total_pnl = sum(trade.pnl for trade in trades)

# Bad
tokens = get_tokens(500)  # What is 500?
x = sum(t.p for t in trades)  # What are x and p?
```

### Rule 6: Avoid Magic Numbers
```python
# Good
MIN_TOKEN_VOLUME = 100000
MIN_PRICE_GAIN = 500

if token.volume > MIN_TOKEN_VOLUME:
    process_token(token)

# Bad
if token.volume > 100000:  # What is this?
    process_token(token)
```

---

## Error Handling

### Rule 7: Handle Errors Explicitly
```python
# Good
try:
    data = scrape_token(address)
except requests.RequestException as e:
    logger.error(f"Network error: {e}")
    return None
except ValueError as e:
    logger.error(f"Invalid data: {e}")
    return None

# Bad
try:
    data = scrape_token(address)
except:  # Catches everything!
    return None
```

### Rule 8: Validate Inputs Early
```python
def calculate_score(wallet: SmartWallet) -> float:
    if wallet.appearances < 1:
        raise ValueError("No appearances")
    if wallet.total_pnl is None:
        raise ValueError("No PnL data")
    
    return wallet.total_pnl * wallet.appearances
```

### Rule 9: Use Context Managers
```python
# Good
with open('wallets.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerows(data)

# Bad
f = open('wallets.csv', 'w')
writer = csv.writer(f)
writer.writerows(data)
f.close()  # Might not execute if error!
```

---

## Data Structures

### Rule 10: Use Dataclasses
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Token:
    address: str
    name: str
    volume_24h: float
    timestamp: datetime
    
    def is_high_volume(self) -> bool:
        return self.volume_24h > MIN_VOLUME

# Good
token = Token("abc", "PEPE", 150000, datetime.now())

# Bad - unclear structure
token = {"addr": "abc", "name": "PEPE", "vol": 150000}
```

### Rule 11: Choose Right Data Structure
- **List**: Ordered, allows duplicates
- **Set**: Unique items, unordered
- **Dict**: Key-value, fast lookup
- **Tuple**: Immutable, fixed size

```python
# Good
unique_wallets = set(t.wallet for t in traders)
wallet_pnl = {w.address: w.pnl for w in wallets}

# Bad
unique_wallets = list(set([t.wallet for t in traders]))
```

---

## Functions

### Rule 12: Prefer Pure Functions
```python
# Good - No side effects
def calculate_win_rate(trades: List[Trade]) -> float:
    winning = sum(1 for t in trades if t.pnl > 0)
    return winning / len(trades) if trades else 0

# Bad - Modifies global
total_calculated = 0

def calculate_win_rate(trades: List[Trade]) -> float:
    global total_calculated
    total_calculated += 1  # Side effect!
    return winning / len(trades)
```

### Rule 13: Return Early
```python
# Good
def process_wallet(wallet: SmartWallet) -> Optional[float]:
    if not wallet.is_valid():
        return None
    if wallet.appearances < MIN_APPEARANCES:
        return None
    return calculate_score(wallet)

# Bad - deep nesting
def process_wallet(wallet: SmartWallet) -> Optional[float]:
    if wallet.is_valid():
        if wallet.appearances >= MIN_APPEARANCES:
            return calculate_score(wallet)
    return None
```

### Rule 14: Careful with Mutable Defaults
```python
# Good
def aggregate_data(traders: List[Trader], 
                   filters: Optional[Dict] = None) -> Dict:
    if filters is None:
        filters = {}
    # process...

# Bad - shared across calls!
def aggregate_data(traders: List[Trader], 
                   filters: Dict = {}) -> Dict:
    # process...
```

---

## Comments

### Rule 15: Write Self-Documenting Code
```python
# Good - clear without comments
def is_high_value_wallet(wallet: SmartWallet) -> bool:
    return wallet.total_pnl > HIGH_VALUE_THRESHOLD

# Bad - needs comment
def check(w):  # Check if high value
    return w.pnl > 10000
```

### Rule 16: Comment Why, Not What
```python
# Good - explains reasoning
# Exclude wallets with < 2 appearances to avoid lucky one-hit wonders
if wallet.appearances < 2:
    continue

# Bad - restates code
# Check if appearances less than 2
if wallet.appearances < 2:
    continue
```

### Rule 17: Keep Comments Current
- Update comments when code changes
- Delete commented-out code
- Remove resolved TODOs

---

## Testing

### Rule 18: Write Testable Code
```python
# Good - easy to test
def parse_price(text: str) -> float:
    return float(text.replace('$', '').replace(',', ''))

# Test
assert parse_price('$1,234.56') == 1234.56

# Bad - external dependencies
def get_price():
    response = requests.get(GLOBAL_URL)
    return parse(response)
```

### Rule 19: Test Edge Cases
```python
def test_calculate_win_rate():
    trades = [Trade(pnl=100), Trade(pnl=-50)]
    assert calculate_win_rate(trades) == 0.5
    
    # Edge cases
    assert calculate_win_rate([]) == 0
    assert calculate_win_rate([Trade(pnl=0)]) == 0
    assert calculate_win_rate([Trade(pnl=-100)]) == 0
```

---

## Performance

### Rule 20: Optimize When Needed
- Write clear code first
- Measure performance
- Optimize bottlenecks only

### Rule 21: Use Comprehensions Wisely
```python
# Good - simple
addresses = [t.wallet for t in traders]
profitable = [t for t in traders if t.pnl > 0]

# Bad - too complex
result = [{
    'wallet': t.wallet, 
    'score': calc(t)
} for t in traders if t.pnl > 0 and validate(t)]
# Use regular loop instead!
```

---

## Imports

### Rule 22: Organize Imports
```python
# Standard library
import json
import logging
from datetime import datetime

# Third-party
import requests
import pandas as pd

# Local
from .models import Token, Trader
from .utils import parse_currency
```

### Rule 23: No Wildcard Imports
```python
# Good
from typing import List, Dict

# Bad
from typing import *
```

---

## Configuration

### Rule 24: Use Config Files
```python
# Good
with open('config.json') as f:
    config = json.load(f)
MIN_VOLUME = config['filters']['min_volume']

# Bad
MIN_VOLUME = 100000  # Hardcoded
```

### Rule 25: Environment Variables for Secrets
```python
# Good
import os
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY not set")

# Bad
API_KEY = "sk-12345"  # Secret in code!
```

---

## Logging

### Rule 26: Use Appropriate Levels
```python
logger.debug(f"Processing {wallet}")  # Diagnostic
logger.info(f"Found {len(tokens)} tokens")  # Informational
logger.warning(f"Missing data for {wallet}")  # Unexpected
logger.error(f"Failed to scrape {url}")  # Error
logger.critical("Database down")  # Critical failure
```

### Rule 27: Log Context
```python
# Good
logger.error(
    "Failed to process wallet",
    extra={'wallet': address, 'error': str(e)}
)

# Bad
logger.error("Error!")  # No context
```

---

## Git

### Rule 28: Good Commit Messages
```
# Good
feat: Add wallet scoring algorithm

Implements scoring based on consistency, profitability,
win rate, and position sizing.

# Bad
fix stuff
changes
update
```

### Rule 29: Commit Logical Units
- One feature/fix per commit
- Don't mix refactoring with features
- Remove debug statements before commit

---

## Security

### Rule 30: Validate External Input
```python
def process_address(address: str) -> Optional[str]:
    if not address or len(address) < 32:
        return None
    
    address = address.strip()
    
    if not address.isalnum():
        return None
    
    return address
```

### Rule 31: Use HTTPS
```python
# Good
API_BASE = "https://api.solscan.io"

# Bad
API_BASE = "http://api.solscan.io"
```

---

## Final Checklist

Before code is "done":
- [ ] Follows PEP 8
- [ ] Has type hints
- [ ] Has docstrings
- [ ] Has error handling
- [ ] Has logging
- [ ] Is tested
- [ ] No hardcoded values
- [ ] No secrets in code
- [ ] Clear names
- [ ] Small functions
- [ ] Comments explain why
- [ ] Imports organized

**Code is read more than written. Write for humans first.**