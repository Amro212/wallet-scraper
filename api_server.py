import sys
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database import get_database

app = FastAPI(title="Smart Wallet Tracker API")

# Enable CORS for React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/wallets")
async def get_wallets():
    """Get all smart wallets from the database."""
    db = get_database()
    wallets = db.get_all_smart_wallets()
    
    # Process wallets for frontend (mirroring export logic)
    processed_wallets = []
    for i, wallet in enumerate(wallets, 1):
        wallet_data = wallet.copy()
        wallet_data["rank"] = i
        
        # Format percentages
        if wallet_data.get("win_rate_7d") is not None:
             wallet_data["win_rate_7d"] = f"{float(wallet_data['win_rate_7d'])*100:.1f}%"
        else:
             wallet_data["win_rate_7d"] = "-"
             
        if wallet_data.get("win_rate_30d") is not None:
             wallet_data["win_rate_30d"] = f"{float(wallet_data['win_rate_30d'])*100:.1f}%"
        else:
             wallet_data["win_rate_30d"] = "-"

        # Format numbers
        for key in ["realized_pnl_7d", "unrealized_pnl_7d", "realized_pnl_30d", "unrealized_pnl_30d"]:
            val = wallet_data.get(key)
            wallet_data[key] = round(val) if val is not None else "-"
            
        for key in ["avg_holding_time_7d", "avg_holding_time_30d"]:
             if wallet_data.get(key) is None:
                 wallet_data[key] = "-"

        processed_wallets.append(wallet_data)
        
    return processed_wallets

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
