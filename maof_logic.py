import numpy as np
from scipy.stats import norm

def bs_calc_raw(S, K, T, r, sigma, otype):
    """
    חישוב בלאק שולס בסיסי לערך בודד
    """
    if T <= 0:
        return max(0, S-K) if otype.lower()=='call' else max(0, K-S), 0, 0, 0, 0
        
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    
    if otype.lower() == 'call':
        price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
        delta = norm.cdf(d1)
    else: 
        price = K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
        delta = -norm.cdf(-d1)
        
    gamma = norm.pdf(d1)/(S*sigma*np.sqrt(T))
    vega = S*norm.pdf(d1)*np.sqrt(T)/100
    theta = (-S*norm.pdf(d1)*sigma/(2*np.sqrt(T)) - r*K*np.exp(-r*T)*norm.cdf(d2 if otype.lower()=='call' else -d2))/365
    
    return price, delta, gamma, theta, vega

def calculate_portfolio_pnl(df_portfolio, s_sim, t_sim, r, vol, multiplier, is_expiry=False, vol_override=None):
    """
    חישוב רווח/הפסד לתיק שלם
    """
    total_pnl = 0
    if df_portfolio.empty: return 0
    
    calc_vol = vol if vol_override is None else vol_override
    
    for _, row in df_portfolio.iterrows():
        try:
            k = float(row['Strike'])
            qty = float(row['Qty'])
            cost = float(row['Option Price'])
            otype = row['Type']
            val_sim = 0
            
            if is_expiry:
                if otype == 'Call': val_sim = max(s_sim - k, 0) * multiplier
                else: val_sim = max(k - s_sim, 0) * multiplier
            else:
                p, _, _, _, _ = bs_calc_raw(s_sim, k, t_sim, r, calc_vol, otype)
                val_sim = p * multiplier
                
            total_pnl += (val_sim - cost) * qty
        except: pass
    return total_pnl

def calculate_portfolio_greeks(df_portfolio, spot, T, r, vol, multiplier):
    """
    חישוב יווניות לתיק
    """
    totals = {'PnL': 0, 'Delta': 0, 'Gamma': 0, 'Theta': 0, 'Vega': 0, 'Cost': 0, 'MaxProfit': 0, 'MaxLoss': 0}
    if df_portfolio.empty: return totals
    
    # 1. Greeks
    for _, row in df_portfolio.iterrows():
        try:
            qty = float(row['Qty'])
            cost = float(row['Option Price'])
            strike = float(row['Strike'])
            otype = row['Type']
            
            p, d, g, t_val, v = bs_calc_raw(spot, strike, T, r, vol, otype)
            current_val = p * multiplier
            
            totals['PnL'] += (current_val - cost) * qty
            totals['Delta'] += d * 100 * qty if otype == 'Call' else d * 100 * qty 
            totals['Gamma'] += g * 100 * qty
            totals['Theta'] += t_val * multiplier * qty
            totals['Vega'] += v * multiplier * qty
            totals['Cost'] += (cost * qty)
        except: pass
        
    # 2. Max PnL Scan
    wide_scan = np.linspace(0.1, spot * 3, 100) 
    pnl_scan = [calculate_portfolio_pnl(df_portfolio, s, 0, r, vol, multiplier, is_expiry=True) for s in wide_scan]
    
    totals['MaxProfit'] = np.max(pnl_scan)
    totals['MaxLoss'] = np.min(pnl_scan)
    
    # Infinity Check
    boundary_threshold = spot * multiplier * 0.5 
    if pnl_scan[-1] > boundary_threshold: totals['MaxProfit'] = float('inf')
    if pnl_scan[-1] < -boundary_threshold: totals['MaxLoss'] = float('-inf')
    if pnl_scan[0] > boundary_threshold: totals['MaxProfit'] = float('inf')
    if pnl_scan[0] < -boundary_threshold: totals['MaxLoss'] = float('-inf')

    return totals