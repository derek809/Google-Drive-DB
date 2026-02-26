"""
Investment Tracker - Lane 2 (Investment System)
Monitors BTC, Roth IRA, and portfolio alerts
"""

import os
import json
from datetime import datetime
from typing import Optional

# Portfolio targets from SOUL.md
PORTFOLIO_TARGETS = {
    "emergency_fund": {"target": 15000, "current": None, "account": "Betterment Cash Reserve"},
    "roth_ira": {"target": 7000, "monthly": 583, "account": "Fidelity"},
    "taxable_brokerage": {"target": 50000, "account": "Fidelity"},
    "crypto": {"account": "Coinbase", "rules": {"stop_loss": -0.15, "sell_half": 1.0}}
}

DATA_FILE = "/Users/work/Telgram bot/data/investment_data.json"

def load_data() -> dict:
    """Load investment data from file"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "btc_cost_basis": None,
        "btc_last_price": None,
        "roth_last_contribution": None,
        "emergency_fund_current": 12000,
        "last_check": None
    }

def save_data(data: dict):
    """Save investment data"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

async def check_btc_alerts() -> list:
    """Check BTC for stop-loss or sell-half triggers"""
    from web_search import web_search
    
    # Get current BTC price
    results = await web_search({"query": "Bitcoin BTC price USD now", "count": 1})
    
    if not results or "results" not in results:
        return []
    
    try:
        # Extract price from search results
        price_text = results["results"][0].get("title", "")
        # Basic parsing - in production would use a proper API
        import re
        price_match = re.search(r'\$([0-9,]+)', price_text)
        if price_match:
            current_price = float(price_match.group(1).replace(',', ''))
        else:
            return []
    except:
        return []
    
    data = load_data()
    alerts = []
    
    if data.get("btc_cost_basis"):
        cost = data["btc_cost_basis"]
        change_pct = (current_price - cost) / cost
        
        # Stop-loss: -15%
        if change_pct <= -0.15:
            alerts.append(f"🚨 BTC STOP-LOSS: Down {change_pct:.1%} from ${cost:,} → sell trigger")
        
        # Sell-half: +100%
        elif change_pct >= 1.0:
            alerts.append(f"💰 BTC SELL-HALF: Up {change_pct:.0%} from ${cost:,} → sell 50%")
    
    data["btc_last_price"] = current_price
    data["last_check"] = datetime.now().isoformat()
    save_data(data)
    
    return alerts

def get_portfolio_status() -> str:
    """Get current portfolio status summary"""
    data = load_data()
    
    status = "📊 Portfolio Status\n"
    status += f"• Emergency Fund: ${data.get('emergency_fund_current', 0):,.0f} / $15,000\n"
    status += f"• Roth IRA: ${data.get('roth_last_contribution', 0):,.0f}/mo target\n"
    
    if data.get("btc_last_price"):
        status += f"• BTC: ${data.get('btc_last_price'):,.0f}"
        if data.get("btc_cost_basis"):
            change = (data["btc_last_price"] - data["btc_cost_basis"]) / data["btc_cost_basis"]
            status += f" ({change:+.1%} from cost)"
    
    return status

# Aliases for proactive engine
def check_investment_alerts():
    """Sync wrapper for proactive engine"""
    import asyncio
    return asyncio.run(check_btc_alerts())

if __name__ == "__main__":
    print(get_portfolio_status())
