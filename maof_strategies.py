import pandas as pd

# --- Strategy Definitions (The Full Suite) ---
STRATEGY_MATRIX = {
    "Bullish": {
        "Low IV": ["Long Call", "Bull Call Spread", "Synthetic Long (Stock)"],
        "Medium IV": ["Ratio Call Spread", "Zebra", "Jade Lizard"],
        "High IV": ["Short Put", "Bull Put Spread", "Covered Call (Synthetic)"]
    },
    "Neutral": {
        "Low IV": ["Long Straddle", "Long Strangle", "Reverse Iron Condor"],
        "Medium IV": ["Iron Condor", "Butterfly", "Double Diagonal"],
        "High IV": ["Short Strangle", "Short Straddle", "Iron Butterfly"]
    },
    "Bearish": {
        "Low IV": ["Long Put", "Bear Put Spread", "Synthetic Short"],
        "Medium IV": ["Ratio Put Spread", "Reverse Jade Lizard"],
        "High IV": ["Short Call", "Bear Call Spread", "Protective Put"]
    }
}

def generate_strategy_legs(strategy_name, spot, interval):
    """
    Returns a list of dictionaries. Each dict MUST have:
    - 'Type': 'Call' or 'Put'
    - 'Strike': float
    - 'Qty': int (+ for long, - for short)
    """
    atm = round(spot / interval) * interval
    legs = []

    # --- BULLISH STRATEGIES ---
    if strategy_name == "Long Call":
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 1})

    elif strategy_name == "Bull Call Spread":
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 1})       # Buy ATM
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -1}) # Sell OTM

    elif strategy_name == "Synthetic Long (Stock)":
        # Mimics owning the stock: Long Call + Short Put at same strike
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 1})
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': -1})

    elif strategy_name == "Ratio Call Spread":
        # 1 Long ATM, 2 Short OTM
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 1})
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -2})

    elif strategy_name == "Zebra": 
        # Zero Extrinsic Back Ratio: Simulates stock with less capital
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 2}) 
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -1}) 

    elif strategy_name == "Jade Lizard":
        # Bullish/Neutral: Short Put (Downside) + Short Call Spread (Upside)
        # Goal: Total credit > width of call spread (no upside risk)
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': -1}) # Short Put
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -1}) # Short Call
        legs.append({'Type': 'Call', 'Strike': atm + 2*interval, 'Qty': 1}) # Long Call (Protection)

    elif strategy_name == "Short Put":
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': -1})

    elif strategy_name == "Bull Put Spread":
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': 1}) # Long (Protection)
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': -1})       # Short (Income)

    elif strategy_name == "Covered Call (Synthetic)":
        # Deep ITM Call (Stock replacement) + Short OTM Call
        legs.append({'Type': 'Call', 'Strike': atm - 2*interval, 'Qty': 1}) 
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -1})

    # --- NEUTRAL STRATEGIES ---
    elif strategy_name == "Long Straddle":
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 1})
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': 1})

    elif strategy_name == "Long Strangle":
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': 1})
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': 1})

    elif strategy_name == "Reverse Iron Condor":
        # Buying the wings, Selling the body (Long Volatility)
        legs.append({'Type': 'Put', 'Strike': atm - 2*interval, 'Qty': 1})
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': -1})
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -1})
        legs.append({'Type': 'Call', 'Strike': atm + 2*interval, 'Qty': 1})

    elif strategy_name == "Iron Condor":
        # Selling the body, Buying the wings (Short Volatility)
        legs.append({'Type': 'Put', 'Strike': atm - 2*interval, 'Qty': 1}) # Protection
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': -1}) # Short
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -1}) # Short
        legs.append({'Type': 'Call', 'Strike': atm + 2*interval, 'Qty': 1}) # Protection

    elif strategy_name == "Butterfly":
        # Classic Fly
        legs.append({'Type': 'Call', 'Strike': atm - interval, 'Qty': 1})
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': -2})
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': 1})
        
    elif strategy_name == "Iron Butterfly":
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': 1})
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': -1})
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': -1})
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': 1})

    elif strategy_name == "Short Strangle":
        legs.append({'Type': 'Call', 'Strike': atm + 2*interval, 'Qty': -1})
        legs.append({'Type': 'Put', 'Strike': atm - 2*interval, 'Qty': -1})

    elif strategy_name == "Short Straddle":
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': -1})
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': -1})

    elif strategy_name == "Double Diagonal":
        # Typically involves different expiries, but structurally:
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': -1})
        legs.append({'Type': 'Put', 'Strike': atm - 2*interval, 'Qty': 1})
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -1})
        legs.append({'Type': 'Call', 'Strike': atm + 2*interval, 'Qty': 1})
        # Note: User must manually adjust dates for true diagonal

    elif strategy_name == "Calendar Spread":
        # Long ATM (Far month) + Short ATM (Near month)
        # Note: User must manually adjust dates
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': -1})
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 1}) 

    # --- BEARISH STRATEGIES ---
    elif strategy_name == "Long Put":
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': 1})

    elif strategy_name == "Bear Put Spread":
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': 1})       # Buy ATM
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': -1}) # Sell OTM

    elif strategy_name == "Synthetic Short":
        # Long Put + Short Call
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': 1})
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': -1})

    elif strategy_name == "Ratio Put Spread":
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': 1})
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': -2})

    elif strategy_name == "Reverse Jade Lizard":
        # Bearish/Neutral: Short Call (Upside) + Short Put Spread (Downside)
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': -1})
        legs.append({'Type': 'Put', 'Strike': atm - interval, 'Qty': -1})
        legs.append({'Type': 'Put', 'Strike': atm - 2*interval, 'Qty': 1})

    elif strategy_name == "Short Call":
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': -1})

    elif strategy_name == "Bear Call Spread":
        legs.append({'Type': 'Call', 'Strike': atm + interval, 'Qty': 1}) # Protection
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': -1})       # Income

    elif strategy_name == "Protective Put":
        # Usually implies owning stock + Long Put. 
        # Synthetically: Long Call (Stock) + Long Put
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 1})
        legs.append({'Type': 'Put', 'Strike': atm, 'Qty': 1})
        
    else:
        # Default fallback
        legs.append({'Type': 'Call', 'Strike': atm, 'Qty': 1})

    return legs