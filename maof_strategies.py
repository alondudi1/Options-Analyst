# --- Strategy Logic Engine ---

def get_atm_strike(spot, interval):
    return round(spot / interval) * interval

def generate_strategy_legs(strategy_name, spot, interval):
    atm = get_atm_strike(spot, interval)
    legs = []
    
    # --- BULLISH ---
    if strategy_name == "Long Call":
        legs.append({"Type": "Call", "Strike": atm, "Qty": 1})
    elif strategy_name == "Bull Call Spread":
        legs.append({"Type": "Call", "Strike": atm, "Qty": 1})
        legs.append({"Type": "Call", "Strike": atm + 2*interval, "Qty": -1})
    elif strategy_name == "Bull Put Spread (ITM)":
        legs.append({"Type": "Put", "Strike": atm, "Qty": 1}) 
        legs.append({"Type": "Put", "Strike": atm + 2*interval, "Qty": -1}) 
    elif strategy_name == "Short Call Butterfly (ITM)":
        center = atm - 2*interval
        legs.append({"Type": "Call", "Strike": center - interval, "Qty": -1})
        legs.append({"Type": "Call", "Strike": center, "Qty": 2})
        legs.append({"Type": "Call", "Strike": center + interval, "Qty": -1})
    elif strategy_name == "Short Put Butterfly (OTM)":
        center = atm - 2*interval
        legs.append({"Type": "Put", "Strike": center - interval, "Qty": -1})
        legs.append({"Type": "Put", "Strike": center, "Qty": 2})
        legs.append({"Type": "Put", "Strike": center + interval, "Qty": -1})
    elif strategy_name == "Ratio Call Spread":
        legs.append({"Type": "Call", "Strike": atm, "Qty": 1})
        legs.append({"Type": "Call", "Strike": atm + 2*interval, "Qty": -2})
    elif strategy_name == "Long Synthetic":
        legs.append({"Type": "Call", "Strike": atm, "Qty": 1})
        legs.append({"Type": "Put", "Strike": atm, "Qty": -1})
    elif strategy_name == "Short Put":
        legs.append({"Type": "Put", "Strike": atm - 2*interval, "Qty": -1})
    elif strategy_name == "Bull Call Spread (ITM)": 
        legs.append({"Type": "Call", "Strike": atm - interval, "Qty": 1})
        legs.append({"Type": "Call", "Strike": atm, "Qty": -1})
    elif strategy_name == "Long Put Butterfly (ITM)": 
        center = atm + 2*interval
        legs.append({"Type": "Put", "Strike": center - interval, "Qty": 1})
        legs.append({"Type": "Put", "Strike": center, "Qty": -2})
        legs.append({"Type": "Put", "Strike": center + interval, "Qty": 1})
    elif strategy_name == "Long Call Butterfly (OTM)": 
        center = atm + 2*interval
        legs.append({"Type": "Call", "Strike": center - interval, "Qty": 1})
        legs.append({"Type": "Call", "Strike": center, "Qty": -2})
        legs.append({"Type": "Call", "Strike": center + interval, "Qty": 1})

    # --- NEUTRAL ---
    elif strategy_name == "Long Straddle":
        legs.append({"Type": "Call", "Strike": atm, "Qty": 1})
        legs.append({"Type": "Put", "Strike": atm, "Qty": 1})
    elif strategy_name == "Long Strangle":
        legs.append({"Type": "Call", "Strike": atm + interval, "Qty": 1})
        legs.append({"Type": "Put", "Strike": atm - interval, "Qty": 1})
    elif strategy_name == "Short Butterfly": 
        legs.append({"Type": "Call", "Strike": atm - interval, "Qty": -1})
        legs.append({"Type": "Call", "Strike": atm, "Qty": 2})
        legs.append({"Type": "Call", "Strike": atm + interval, "Qty": -1})
    elif strategy_name == "Long Butterfly": 
        legs.append({"Type": "Call", "Strike": atm - interval, "Qty": 1})
        legs.append({"Type": "Call", "Strike": atm, "Qty": -2})
        legs.append({"Type": "Call", "Strike": atm + interval, "Qty": 1})
    elif strategy_name == "Iron Butterfly":
        legs.append({"Type": "Put", "Strike": atm, "Qty": -1})
        legs.append({"Type": "Call", "Strike": atm, "Qty": -1})
        legs.append({"Type": "Put", "Strike": atm - 2*interval, "Qty": 1})
        legs.append({"Type": "Call", "Strike": atm + 2*interval, "Qty": 1})
    elif strategy_name == "Iron Condor":
        legs.append({"Type": "Put", "Strike": atm - interval, "Qty": -1})
        legs.append({"Type": "Call", "Strike": atm + interval, "Qty": -1})
        legs.append({"Type": "Put", "Strike": atm - 3*interval, "Qty": 1})
        legs.append({"Type": "Call", "Strike": atm + 3*interval, "Qty": 1})
    elif strategy_name == "Short Straddle":
        legs.append({"Type": "Call", "Strike": atm, "Qty": -1})
        legs.append({"Type": "Put", "Strike": atm, "Qty": -1})
    elif strategy_name == "Short Strangle":
        legs.append({"Type": "Call", "Strike": atm + interval, "Qty": -1})
        legs.append({"Type": "Put", "Strike": atm - interval, "Qty": -1})
    elif strategy_name == "Ratio Vertical Spread":
        legs.append({"Type": "Call", "Strike": atm, "Qty": -1})
        legs.append({"Type": "Call", "Strike": atm + interval, "Qty": 2})
    elif strategy_name == "Long Butterfly (ATM)":
        legs.append({"Type": "Call", "Strike": atm - interval, "Qty": 1})
        legs.append({"Type": "Call", "Strike": atm, "Qty": -2})
        legs.append({"Type": "Call", "Strike": atm + interval, "Qty": 1})

    # --- BEARISH ---
    elif strategy_name == "Long Put":
        legs.append({"Type": "Put", "Strike": atm, "Qty": 1})
    elif strategy_name == "Bear Put Spread":
        legs.append({"Type": "Put", "Strike": atm, "Qty": 1})
        legs.append({"Type": "Put", "Strike": atm - 2*interval, "Qty": -1})
    elif strategy_name == "Bear Call Spread (ITM)":
        legs.append({"Type": "Call", "Strike": atm, "Qty": 1}) 
        legs.append({"Type": "Call", "Strike": atm - 2*interval, "Qty": -1}) 
    elif strategy_name == "Short Call Butterfly (OTM)":
        center = atm + 2*interval
        legs.append({"Type": "Call", "Strike": center - interval, "Qty": -1})
        legs.append({"Type": "Call", "Strike": center, "Qty": 2})
        legs.append({"Type": "Call", "Strike": center + interval, "Qty": -1})
    elif strategy_name == "Short Put Butterfly (ITM)":
        center = atm + 2*interval
        legs.append({"Type": "Put", "Strike": center - interval, "Qty": -1})
        legs.append({"Type": "Put", "Strike": center, "Qty": 2})
        legs.append({"Type": "Put", "Strike": center + interval, "Qty": -1})
    elif strategy_name == "Ratio Put Spread":
        legs.append({"Type": "Put", "Strike": atm, "Qty": 1})
        legs.append({"Type": "Put", "Strike": atm - 2*interval, "Qty": -2})
    elif strategy_name == "Short Synthetic":
        legs.append({"Type": "Call", "Strike": atm, "Qty": -1})
        legs.append({"Type": "Put", "Strike": atm, "Qty": 1})
    elif strategy_name == "Short Call":
        legs.append({"Type": "Call", "Strike": atm + 2*interval, "Qty": -1})
    elif strategy_name == "Bear Put Spread (ITM)": 
        legs.append({"Type": "Put", "Strike": atm + interval, "Qty": 1}) 
        legs.append({"Type": "Put", "Strike": atm, "Qty": -1}) 
    elif strategy_name == "Long Call Butterfly (ITM)": 
        center = atm - 2*interval
        legs.append({"Type": "Call", "Strike": center - interval, "Qty": 1})
        legs.append({"Type": "Call", "Strike": center, "Qty": -2})
        legs.append({"Type": "Call", "Strike": center + interval, "Qty": 1})
    elif strategy_name == "Long Put Butterfly (OTM)": 
        center = atm - 2*interval
        legs.append({"Type": "Put", "Strike": center - interval, "Qty": 1})
        legs.append({"Type": "Put", "Strike": center, "Qty": -2})
        legs.append({"Type": "Put", "Strike": center + interval, "Qty": 1})

    return legs

STRATEGY_MATRIX = {
    "Bullish": {
        "Low IV": ["Long Call", "Bull Call Spread", "Bull Put Spread (ITM)", "Short Call Butterfly (ITM)", "Short Put Butterfly (OTM)"],
        "Medium IV": ["Bull Call Spread", "Ratio Call Spread", "Long Synthetic"],
        "High IV": ["Short Put", "Bull Call Spread (ITM)", "Long Put Butterfly (ITM)", "Long Call Butterfly (OTM)"]
    },
    "Neutral": {
        "Low IV": ["Long Straddle", "Long Strangle", "Short Butterfly"],
        "Medium IV": ["Long Butterfly", "Iron Butterfly"],
        "High IV": ["Iron Condor", "Short Straddle", "Short Strangle", "Ratio Vertical Spread", "Long Butterfly (ATM)"]
    },
    "Bearish": {
        "Low IV": ["Long Put", "Bear Put Spread", "Bear Call Spread (ITM)", "Short Call Butterfly (OTM)", "Short Put Butterfly (ITM)"],
        "Medium IV": ["Bear Put Spread", "Ratio Put Spread", "Short Synthetic"],
        "High IV": ["Short Call", "Bear Put Spread (ITM)", "Long Call Butterfly (ITM)", "Long Put Butterfly (OTM)"]
    }
}