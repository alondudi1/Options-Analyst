import numpy as np
import pandas as pd
import maof_logic as logic

# --- 1. Scenarios Data Bank (Sorted: Crashes -> Rallies) ---
SCENARIOS = {
    "🦢 THE BLACK SWAN": {
        "spot_move_pct": -0.30,   
        "iv_move_pct": 2.00,      
        "rate_move_pct": 0.50,    
        "desc": "Total failure: Spot -30%, Vol x3."
    },
    "Corona Crash (2020)": {
        "spot_move_pct": -0.15,  
        "iv_move_pct": 1.50,     
        "rate_move_pct": 0.0,
        "desc": "Panic drop -15%, Vol spike."
    },
    "Subprime (2008)": {
        "spot_move_pct": -0.08, 
        "iv_move_pct": 0.60,
        "rate_move_pct": -0.20, 
        "desc": "Grinding drop -8%."
    },
    "Swords of Iron (2023)": {
        "spot_move_pct": -0.06, 
        "iv_move_pct": 0.40,
        "rate_move_pct": 0.0,
        "desc": "Gap down -6%, Local war."
    },
    "Post-Crisis (2009)": {
        "spot_move_pct": 0.04,   
        "iv_move_pct": -0.15,
        "rate_move_pct": 0.0,
        "desc": "Recovery +4%."
    },
    "Vaccine Rally (2020)": {
        "spot_move_pct": 0.08,   
        "iv_move_pct": -0.30,
        "rate_move_pct": 0.0,
        "desc": "Joy rally +8%, Vol crush."
    }
}

# --- 2. Monte Carlo Engine ---
def run_monte_carlo(portfolio_df, current_spot, time_to_expiry, risk_free_rate, current_iv, multiplier, simulations=5000, annual_days=365):
    if portfolio_df.empty:
        return None, None, {}

    dt = max(1e-5, time_to_expiry)
    
    z_scores = np.random.normal(0, 1, simulations)
    drift = (risk_free_rate - 0.5 * current_iv ** 2) * dt
    diffusion = current_iv * np.sqrt(dt) * z_scores
    simulated_spots = current_spot * np.exp(drift + diffusion)
    
    simulated_pnls = []
    
    # Pre-calc structure
    legs = []
    for _, row in portfolio_df.iterrows():
        raw_type = str(row['Type']).strip()
        op_type = raw_type.lower()
        
        # Get entry price (handle column name changes)
        entry_col = 'Entry Price' if 'Entry Price' in row else 'Option Price'
        
        legs.append({
            'type': op_type,
            'strike': float(row['Strike']),
            'qty': float(row['Qty']),
            'entry_price_shekels': float(row[entry_col])
        })
        
    for sim_spot in simulated_spots:
        total_pnl = 0
        for leg in legs:
            if leg['type'] in ['call', 'c']:
                intrinsic_points = max(sim_spot - leg['strike'], 0)
            elif leg['type'] in ['put', 'p']:
                intrinsic_points = max(leg['strike'] - sim_spot, 0)
            else:
                intrinsic_points = 0 
            
            current_value_shekels = intrinsic_points * multiplier
            # PnL = Current Value - Entry Cost
            leg_pnl = (current_value_shekels - leg['entry_price_shekels']) * leg['qty']
            total_pnl += leg_pnl
            
        simulated_pnls.append(total_pnl)
        
    simulated_pnls = np.array(simulated_pnls)
    sorted_pnls = np.sort(simulated_pnls)
    
    var_95_idx = int(simulations * 0.05)
    var_95 = sorted_pnls[var_95_idx]
    cvar_95 = sorted_pnls[:var_95_idx].mean() if var_95_idx > 0 else var_95
    pop = np.sum(simulated_pnls > 0) / simulations
    
    stats = {
        "VaR_95": var_95,
        "CVaR_95": cvar_95,
        "PoP": pop,
        "Mean_PnL": np.mean(simulated_pnls),
        "Max_Loss_Sim": np.min(simulated_pnls),
        "Max_Win_Sim": np.max(simulated_pnls)
    }
    
    return simulated_spots, simulated_pnls, stats

# --- 3. Stress Matrix Engine ---
def calculate_stress_matrix(portfolio_df, current_spot, current_iv, t, r, multiplier, spot_steps=5, iv_steps=5):
    spot_range = np.linspace(current_spot * 0.90, current_spot * 1.10, spot_steps) 
    iv_range = np.linspace(current_iv * 0.8, current_iv * 1.5, iv_steps) 
    
    matrix = []
    
    # Loop IV first (Rows = Y), then Spot (Cols = X)
    for v_sim in iv_range: 
        row_data = []
        for s_sim in spot_range: 
            pnl_sum = 0
            for _, row in portfolio_df.iterrows():
                raw_type = str(row['Type']).strip()
                op_type = raw_type.lower()
                
                p, _, _, _, _ = logic.bs_calc_raw(s_sim, float(row['Strike']), t, r, v_sim, op_type)
                
                if np.isnan(p): p = 0
                
                entry_col = 'Entry Price' if 'Entry Price' in row else 'Option Price'
                entry_price_shekels = float(row[entry_col])
                qty = float(row['Qty'])
                
                pnl_sum += ( (p * multiplier) - entry_price_shekels ) * qty

            row_data.append(pnl_sum)
        matrix.append(row_data)
        
    return spot_range, iv_range, np.array(matrix)

# --- 4. Historical Scenario Calculator ---
def run_historical_scenario(portfolio_df, current_spot, current_iv, t, r, multiplier, scenario_name):
    if scenario_name not in SCENARIOS:
        return 0, current_spot, current_iv
    
    scen = SCENARIOS[scenario_name]
    
    new_spot = current_spot * (1 + scen['spot_move_pct'])
    new_iv = current_iv * (1 + scen['iv_move_pct'])
    rate_shock = scen.get('rate_move_pct', 0.0)
    new_r = r * (1 + rate_shock)
    
    if new_iv < 0.05: new_iv = 0.05
    if new_r < 0.0: new_r = 0.0 
    
    total_pnl = 0
    for _, row in portfolio_df.iterrows():
        raw_type = str(row['Type']).strip()
        op_type = raw_type.lower()
        
        p, _, _, _, _ = logic.bs_calc_raw(new_spot, float(row['Strike']), t, new_r, new_iv, op_type)
        if np.isnan(p): p = 0
        
        current_price_shekels = p * multiplier
        entry_col = 'Entry Price' if 'Entry Price' in row else 'Option Price'
        entry_price_shekels = float(row[entry_col])
        qty = float(row['Qty'])
        
        total_pnl += (current_price_shekels - entry_price_shekels) * qty
            
    return total_pnl, new_spot, new_iv