import numpy as np
import pandas as pd
from scipy.stats import norm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. Black-Scholes Vectorized Engine ---
def black_scholes_vectorized(S, K, T, r, sigma, option_type='call'):
    """
    מנוע תמחור וקטורי.
    מקבל מטריצות שלמות (S, T) ומחזיר מטריצה של מחירי אופציות.
    """
    T = np.maximum(T, 1e-10) # מניעת חלוקה באפס
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else: # put
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
    return price

# --- 2. Mock Data Generator ---
def get_mock_simulation_data():
    """
    נתונים סינתטיים: אסטרטגיית Iron Butterfly (קרדיט).
    """
    spot_price = 2000
    risk_free_rate = 0.04
    iv = 0.16
    days_to_expiry = 30
    
    portfolio_legs = [
        {'type': 'put',  'strike': 1950, 'qty': 1},  # Long Put (Hedge)
        {'type': 'put',  'strike': 2000, 'qty': -1}, # Short Put (ATM)
        {'type': 'call', 'strike': 2000, 'qty': -1}, # Short Call (ATM)
        {'type': 'call', 'strike': 2050, 'qty': 1}   # Long Call (Hedge)
    ]
    
    return spot_price, risk_free_rate, iv, days_to_expiry, portfolio_legs

# --- 3. The Path Simulator Class ---
class PathSimulator:
    def __init__(self, spot, rate, iv, days, n_paths=1000):
        self.spot = spot
        self.rate = rate
        self.iv = iv
        self.days = days
        self.n_paths = n_paths
        self.dt = 1 / 252
        
        self.sim_paths = None
        self.time_grid = None
        self.pnl_matrix = None
        self.initial_total_cost = 0 
        self.legs = [] # נשמור את הרגליים לחישוב תיאורטי
        
    def generate_gbm_paths(self):
        """ יצירת נתיבי מחיר (מונטה קרלו) """
        steps = self.days + 1
        Z = np.random.standard_normal((steps, self.n_paths))
        drift = (self.rate - 0.5 * self.iv**2) * self.dt
        diffusion = self.iv * np.sqrt(self.dt) * Z
        
        drift_matrix = np.full_like(Z, drift)
        drift_matrix[0] = 0
        diffusion[0] = 0
        
        daily_returns = np.exp(np.cumsum(drift_matrix + diffusion, axis=0))
        self.sim_paths = self.spot * daily_returns
        
        time_remaining = np.linspace(self.days/252, 0, steps)
        self.time_grid = time_remaining[:, np.newaxis]

    # --- השינוי המרכזי נמצא בפונקציה הזו ---
    def calculate_portfolio_pnl(self, legs, override_initial_cost=None):
        """
        חישוב רווח והפסד במספרים מוחלטים.
        :param legs: רשימת הרגליים (dictionaries)
        :param override_initial_cost: (אופציונלי) מחיר השוק האמיתי של הפוזיציה כרגע.
                                      אם לא נשלח, יחושב תיאורטית לפי בלאק-שולס.
        """
        self.legs = legs # שמירת הרגליים לשימוש עתידי
        
        if self.sim_paths is None:
            self.generate_gbm_paths()
            
        steps, paths = self.sim_paths.shape
        total_value_matrix = np.zeros((steps, paths))
        theoretical_initial_cost = 0
        
        # חישוב שווי התיק לאורך הזמן
        for leg in legs:
            leg_prices = black_scholes_vectorized(
                S=self.sim_paths,
                K=leg['strike'],
                T=self.time_grid, 
                r=self.rate,
                sigma=self.iv,
                option_type=leg['type']
            )
            
            total_value_matrix += leg_prices * leg['qty']
            theoretical_initial_cost += leg_prices[0, 0] * leg['qty']

        # לוגיקה לבחירת מחיר הכניסה (האמיתי או התיאורטי)
        if override_initial_cost is not None:
            self.initial_total_cost = override_initial_cost
        else:
            self.initial_total_cost = theoretical_initial_cost

        # חישוב PnL: שווי עתידי פחות העלות שנקבעה
        self.pnl_matrix = total_value_matrix - self.initial_total_cost

    def get_theoretical_bounds(self):
        """
        פונקציית עזר לחישוב גבולות רווח והפסד תיאורטיים (לכותרת).
        """
        if not self.legs:
            return "N/A", "N/A"
            
        # יצירת גריד מחירים רחב מאוד לבדיקת פקיעה (מאפס ועד פי 3 מהסטרייק הגבוה)
        max_strike = max([leg['strike'] for leg in self.legs])
        s_grid = np.linspace(0, max_strike * 3, 5000)
        
        payoff_at_expiry = np.zeros_like(s_grid)
        net_call_qty = 0
        
        for leg in self.legs:
            if leg['type'] == 'call':
                intrinsic = np.maximum(s_grid - leg['strike'], 0)
                net_call_qty += leg['qty']
            else: # put
                intrinsic = np.maximum(leg['strike'] - s_grid, 0)
            
            payoff_at_expiry += intrinsic * leg['qty']
            
        # PnL = Payoff - Initial Cost
        pnl_grid = payoff_at_expiry - self.initial_total_cost
        
        min_pnl = np.min(pnl_grid)
        max_pnl = np.max(pnl_grid)
        
        # בדיקת אינסוף (לפי נטו Calls)
        # אם יש יותר קולים לונג -> רווח אינסופי
        if net_call_qty > 0:
            max_str = "∞"
        else:
            max_str = f"{max_pnl:,.2f}"
            
        # אם יש יותר קולים שורט -> הפסד אינסופי
        if net_call_qty < 0:
            min_str = "-∞"
        else:
            min_str = f"{min_pnl:,.2f}"
            
        return max_str, min_str

    def get_analytics(self, profit_targets=[10, 20, 30], loss_targets=[-10, -20]):
        """ חישוב סטטיסטיקות במספרים מוחלטים """
        max_pnl_per_path = np.max(self.pnl_matrix, axis=0)
        min_pnl_per_path = np.min(self.pnl_matrix, axis=0)
        
        touch_probs = {f"Touch {t}": np.mean(max_pnl_per_path >= t) for t in profit_targets}
        risk_probs = {f"Risk {t}": np.mean(min_pnl_per_path <= t) for t in loss_targets}
        
        pain_index = np.mean(min_pnl_per_path)
        
        peak_days = np.argmax(self.pnl_matrix, axis=0)
        profitable_mask = max_pnl_per_path > 0
        avg_peak_day = np.mean(peak_days[profitable_mask]) if np.any(profitable_mask) else 0

        stats = {
            **touch_probs,
            **risk_probs,
            "Optimal Holding (Days)": round(avg_peak_day, 1),
            "Avg Min PnL": round(pain_index, 2)
        }
        return stats

    def plot_results(self, n_display=150):
        """ ויזואליזציה (ספגטי + הסתברות מצטברת מוחלטת) """
        subset_matrix = self.pnl_matrix[:, :n_display]
        days = np.arange(subset_matrix.shape[0])
        
        # לוגיקה לגרף הסתברות מצטברת
        data_for_stats = self.pnl_matrix[-1, :] 
        sorted_pnl = np.sort(data_for_stats)[::-1]
        n_points = len(sorted_pnl)
        probs = (np.arange(1, n_points + 1) / n_points) * 100

        # --- יצירת הכותרת הדינמית ---
        cost_type = "Credit" if self.initial_total_cost < 0 else "Cost"
        cost_val = abs(self.initial_total_cost)
        
        # חישוב גבולות תיאורטיים
        max_theo, min_theo = self.get_theoretical_bounds()
        
        title_text = (
            f"<b>Simulation Results</b><br>"
            f"<span style='font-size: 14px; color: lightgray;'>"
            f"Entry {cost_type}: {cost_val:.2f} | "
            f"Max Profit: {max_theo} | "
            f"Max Loss: {min_theo}"
            f"</span>"
        )

        fig = make_subplots(
            rows=1, cols=2, 
            column_widths=[0.65, 0.35], 
            subplot_titles=("PnL Paths (Numeric Value)", "Chance to Exceed Profit (Reverse CDF)")
        )

        # גרף נתיבים
        for i in range(subset_matrix.shape[1]):
            end_val = subset_matrix[-1, i]
            line_color = 'rgba(0, 255, 100, 0.15)' if end_val >= 0 else 'rgba(255, 50, 50, 0.15)'
            fig.add_trace(go.Scatter(
                x=days, y=subset_matrix[:, i], mode='lines', 
                line=dict(width=1, color=line_color),
                showlegend=False, hoverinfo='skip'
            ), row=1, col=1)
            
        # ממוצע
        avg_path = np.mean(self.pnl_matrix, axis=1)
        fig.add_trace(go.Scatter(
            x=days, y=avg_path, mode='lines', name='Avg Path',
            line=dict(width=3, color='yellow')
        ), row=1, col=1)

        # גרף הסתברות
        fig.add_trace(go.Scatter(
            x=sorted_pnl, 
            y=probs,
            mode='lines',
            name='Probability',
            line=dict(color='cyan', width=3),
            hovertemplate=(
                "PnL: %{x:.2f}<br>" +
                "Chance to Exceed: %{y:.1f}%<extra></extra>"
            )
        ), row=1, col=2)

        fig.add_vline(x=0, line_width=1, line_dash="dash", line_color="white", row=1, col=2)

        fig.update_layout(
            title={'text': title_text, 'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top'},
            template="plotly_dark",
            showlegend=True,
            hovermode="x unified",
            margin=dict(t=100) # מרווח עליון לכותרת הגדולה
        )
        
        fig.update_xaxes(title_text="Profit / Loss (Currency)", row=1, col=2)
        fig.update_yaxes(title_text="Probability (%)", row=1, col=2)

        return fig

# --- 4. Main Execution Block ---
if __name__ == "__main__":
    spot, rate, iv, days, legs = get_mock_simulation_data()
    
    print(f"--- Running Simulation ---")
    print(f"Spot: {spot}, Days: {days}")
    
    sim = PathSimulator(spot, rate, iv, days, n_paths=2000)
    
    # דוגמה לשימוש בפיצ'ר החדש:
    # נניח שאנחנו יודעים שהפוזיציה הזו נסחרת בשוק בזיכוי של 120 (במקום מה שהמודל יחשב)
    sim.calculate_portfolio_pnl(legs, override_initial_cost=-120)
    
    # עדכון יעדים למספרים
    metrics = sim.get_analytics(profit_targets=[10, 50, 100], loss_targets=[-50, -100])
    
    print("\n--- Statistical Insights ---")
    for k, v in metrics.items():
        print(f"{k}: {v:.2f}") 
        
    fig = sim.plot_results()
    fig.show()