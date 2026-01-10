import streamlit as st
import numpy as np
import pandas as pd
from scipy.stats import norm
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date

# --- Page Config ---
st.set_page_config(layout="wide", page_title="DOR Path Lab")

# --- CSS ---
st.markdown("""
<style>
    [data-testid="stSidebarNav"] {display: none;}
    .stAlert {padding-top: 1rem; padding-bottom: 1rem;}
</style>
""", unsafe_allow_html=True)

# --- 1. מנוע וקטורי (Locked) ---
def black_scholes_vectorized(S, K, T, r, sigma, option_type='call'):
    T = np.maximum(T, 1e-10)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return price

# --- CLASS: PathSimulator (Insert this BETWEEN black_scholes and fetch_data) ---

class PathSimulator:
    def __init__(self, spot, rate, iv, days, mult=100, n_paths=1000):
        self.spot = spot; self.rate = rate; self.iv = iv; self.days = days
        self.mult = mult 
        self.n_paths = n_paths; self.dt = 1 / 252
        self.sim_paths = None; self.time_grid = None; self.pnl_matrix = None
        self.initial_total_cost = 0; self.legs = []
        
    def generate_gbm_paths(self):
        # Ensure at least 2 steps for visualization even if days < 1 (Intraday fix)
        steps = max(2, int(self.days) + 1)
        Z = np.random.standard_normal((steps, self.n_paths))
        drift = (self.rate - 0.5 * self.iv**2) * self.dt
        diffusion = self.iv * np.sqrt(self.dt) * Z
        drift_matrix = np.full_like(Z, drift); drift_matrix[0] = 0; diffusion[0] = 0
        self.sim_paths = self.spot * np.exp(np.cumsum(drift_matrix + diffusion, axis=0))
        self.time_grid = np.linspace(self.days/252, 0, steps)[:, np.newaxis]

    def calculate_portfolio_pnl(self, legs):
        self.legs = legs
        if self.sim_paths is None: self.generate_gbm_paths()
        steps, paths = self.sim_paths.shape
        total_value_matrix = np.zeros((steps, paths))
        theo_cost = 0
        
        for leg in legs:
            # Valuation over time using vectorized BS
            price_in_points = black_scholes_vectorized(
                self.sim_paths, leg['strike'], self.time_grid, 
                self.rate, self.iv, leg['type']
            )
            val_in_shekels = price_in_points * self.mult * leg['qty']
            total_value_matrix += val_in_shekels
            
            # Cost calculation (Entry Price * Qty)
            if 'price' in leg and leg['price'] is not None:
                 theo_cost += leg['price'] * leg['qty']
            else:
                 theo_cost += price_in_points[0, 0] * self.mult * leg['qty']

        self.initial_total_cost = theo_cost
        # PnL = Current Value - Original Cost
        self.pnl_matrix = total_value_matrix - self.initial_total_cost

    def get_analytics(self, profit_targets, loss_targets):
        max_p = np.max(self.pnl_matrix, axis=0); min_p = np.min(self.pnl_matrix, axis=0)
        return {
            **{f"Touch {t}": np.mean(max_p >= t) for t in profit_targets},
            **{f"Risk {t}": np.mean(min_p <= t) for t in loss_targets},
            "Avg Min PnL": round(np.mean(min_p), 2)
        }

    def plot_results(self, n_display=150):
        subset = self.pnl_matrix[:, :n_display]; days_arr = np.arange(subset.shape[0])
        # For statistics chart: Max PnL reached during the path
        data_for_stats = np.max(self.pnl_matrix, axis=0) 
        sorted_pnl = np.sort(data_for_stats)[::-1]
        probs = (np.arange(1, len(sorted_pnl) + 1) / len(sorted_pnl)) * 100
        
        cost_txt = f"{abs(self.initial_total_cost):,.0f}"
        entry_lbl = "Credit" if self.initial_total_cost < 0 else "Debit"
        
        fig = make_subplots(rows=1, cols=2, column_widths=[0.65, 0.35], subplot_titles=("PnL Paths", "Chance to Touch Profit (Max PnL)"))
        
        # Left Chart: Paths
        for i in range(subset.shape[1]):
            c = 'rgba(0, 255, 100, 0.15)' if subset[-1, i] >= 0 else 'rgba(255, 50, 50, 0.15)'
            fig.add_trace(go.Scatter(x=days_arr, y=subset[:, i], mode='lines', line=dict(width=1, color=c), showlegend=False, hoverinfo='skip'), row=1, col=1)
        fig.add_trace(go.Scatter(x=days_arr, y=np.mean(self.pnl_matrix, axis=1), mode='lines', name='Avg', line=dict(width=3, color='yellow')), row=1, col=1)
        
        # Right Chart: Chance to Touch
        fig.add_trace(go.Scatter(
            x=sorted_pnl, y=probs, mode='lines', name='Touch Prob', 
            line=dict(color='cyan', width=3), 
            hovertemplate="Max PnL: %{x:.0f}<br>Chance to Touch: %{y:.1f}%<extra></extra>"
        ), row=1, col=2)
        
        # --- כאן השינוי: בניית כותרת הדיאגנוסטיקה ---
        scen_details = f"Scenario: Spot {self.spot:,.0f} | IV {self.iv:.1%} | Time {self.days:.1f}d"
        
        fig.add_vline(x=0, line_dash="dash", line_color="white", row=1, col=2)
        
        # עדכון הכותרת הראשית + השורה הצהובה הקטנה מתחתיה
        fig.update_layout(
            template="plotly_dark", 
            height=500, 
            margin=dict(t=80), # הגדלנו מעט את השוליים העליונים
            title=f"Simulation Results (Entry {entry_lbl}: {cost_txt})<br><sup style='color:#ff8080'>{scen_details}</sup>"
        )
        fig.update_xaxes(title_text="Max Profit Reached", row=1, col=2)
        
        return fig
# ==========================================
# 2. DATA BRIDGE (Improved Logic)
# ==========================================
def fetch_data_from_main():
    # 1. נסיון שליפה דרך הגשר היציב (DOR BRIDGE)
    if 'dor_bridge' in st.session_state:
        bridge = st.session_state['dor_bridge']
        # שליפת הפוזיציות בנפרד (כי הן נשמרות תמיד)
        legs = []
        df = st.session_state.get('portfolio_a', pd.DataFrame())
        
        if not df.empty:
            col_price = 'Option Price' if 'Option Price' in df.columns else 'Entry Price'
            for _, row in df.iterrows():
                try:
                    s = float(row['Strike'])
                    q = float(row['Qty'])
                    if s <= 0 or q == 0: continue
                    p = float(row.get(col_price, 0))
                    legs.append({'type': str(row['Type']).lower(), 'strike': s, 'qty': int(q), 'price': p})
                except: continue
        
        # מיזוג נתוני הגשר עם הרגליים
        return {
            'source': 'LIVE (Bridge)', 
            'spot': float(bridge['spot']), 
            'rate': float(bridge['rate']), 
            'iv': float(bridge['iv']), 
            'days': float(bridge['days']), 
            'mult': int(bridge['mult']), 
            'legs': legs
        }

    # 2. גיבוי: נסיון שליפה ישנה (למקרה שהגשר טרם נוצר)
    if 'portfolio_a' in st.session_state:
        # ... (כאן יבוא הקוד הישן כגיבוי, אבל הגשר אמור לתפוס תמיד)
        return None # כרגע נחזיר כלום כדי לא ליצור בלאגן, הגשר הוא הפתרון.

    return None

def get_mock_data():
    return {
        'source': 'DEMO', 'spot': 3700.0, 'rate': 0.0425, 'iv': 0.14, 'days': 30.0, 'mult': 50, 
        'legs': [{'type': 'call', 'strike': 3700, 'qty': 1, 'price': 2900}]
    }

def init_lab_state(force_reload=False):
    incoming_data = fetch_data_from_main()
    update_widgets = False
    
    # 1. בדיקה: טעינה ראשונית (אם אין שום מידע)
    if 'sim_context' not in st.session_state:
        if incoming_data:
            st.session_state['sim_context'] = incoming_data
        else:
            st.session_state['sim_context'] = get_mock_data()
        update_widgets = True
        
    # 2. בדיקה: רענון יזום (לחיצה על כפתור)
    elif force_reload and incoming_data:
        st.session_state['sim_context'] = incoming_data
        st.toast("Forced Sync with MAIN", icon="🔄")
        update_widgets = True

    # 3. בדיקה: סנכרון אוטומטי (זיהוי נתונים חדשים)
    elif incoming_data:
        current = st.session_state['sim_context']
        
        # זיהוי אם הרגליים השתנו (כולל מחיר)
        legs_changed = str(current['legs']) != str(incoming_data['legs'])
        
        is_different = (
            abs(current['spot'] - incoming_data['spot']) > 0.01 or
            abs(current['iv'] - incoming_data['iv']) > 0.001 or
            abs(current['days'] - incoming_data['days']) > 0.01 or
            current['mult'] != incoming_data['mult'] or
            legs_changed or 
            current.get('source') == 'DEMO'
        )
        
        # מנגנון בטיחות: אם הווידג'טים תקועים על דמו אבל יש נתוני אמת
        widgets_stuck_on_mock = (
            st.session_state.get('sim_spot') == 3700.0 and 
            st.session_state.get('sim_iv') == 0.14 and
            incoming_data['spot'] != 3700.0
        )

        if is_different or widgets_stuck_on_mock:
             st.session_state['sim_context'] = incoming_data
             if is_different:
                 st.toast("New Data Detected", icon="⚡")
             else:
                 st.toast("Fixed Stuck Widgets", icon="🔧")
             update_widgets = True

    # --- כאן נכנס הקטע ששאלת עליו ---
    # שים לב שהוא מיושר שמאלה לקו של ה-def / if / elif (חזרנו אחורה מה-indentation)
    
    if update_widgets and 'sim_context' in st.session_state:
        ctx = st.session_state['sim_context']
        st.session_state['sim_spot'] = float(ctx['spot'])
        st.session_state['sim_days'] = float(ctx['days'])
        st.session_state['sim_iv'] = float(ctx['iv'])
        st.session_state['sim_mult'] = int(ctx['mult'])
        
        # --- תוספת: כפיית ריענון אם זה לא טעינה ראשונית ---
        # זה יבטיח שהמספרים בתיבות הקלט יתעדכנו ויזואלית מיידית
        if not force_reload: 
             st.rerun()

# --- 3. UI HEADER ---
init_lab_state(force_reload=False)
ctx = st.session_state['sim_context']

c_back, c_title, c_reload = st.columns([1, 4, 1])
with c_back: st.page_link("main.py", label="⬅️ Back to Main", use_container_width=True)
with c_title: st.title("🕹️ DOR Path Lab")
with c_reload:
    if st.button("📥 Pull from MAIN"):
        init_lab_state(force_reload=True); st.rerun()

# תצוגת נתונים (כולל מכפיל)
st.caption(f"📡 Source: **{ctx.get('source')}** | Multiplier: **{ctx['mult']}** | Spot: **{ctx['spot']:,.0f}**")
with st.expander("📋 View Position Details", expanded=True):
    st.dataframe(pd.DataFrame(ctx['legs']), width="stretch", hide_index=True)
st.divider()

# --- הגדרות סימולציה (עריכה מקומית - Local Overrides) ---
# --- הגדרות סימולציה (Simulation Settings) ---
# --- הגדרות סימולציה (Simulation Settings) ---
with st.expander("⚙️ Simulation Settings (Local Overrides)", expanded=True):
    c_s1, c_s2 = st.columns([1, 2])
    with c_s1:
        sim_paths = st.slider("Paths", 500, 5000, 1000, step=500)
        
        # וידוא שהמפתחות אותחלו (למקרה של הרצה ראשונה)
        if 'sim_spot' not in st.session_state: st.session_state['sim_spot'] = float(ctx['spot'])
        if 'sim_days' not in st.session_state: st.session_state['sim_days'] = float(ctx['days'])
        if 'sim_iv' not in st.session_state: st.session_state['sim_iv'] = float(ctx['iv'])
        if 'sim_mult' not in st.session_state: st.session_state['sim_mult'] = int(ctx['mult'])

        # הווידג'טים מחוברים כעת למפתחות בזיכרון
        sim_spot = st.number_input("Simulated Spot", key='sim_spot', step=10.0)
        sim_days = st.number_input("Simulated Days", key='sim_days', step=0.1, format="%.2f") 
        sim_iv = st.number_input("Simulated IV", key='sim_iv', step=0.005, format="%.3f")
        sim_mult = st.number_input("Multiplier", key='sim_mult', step=10)

    with c_s2:
        st.info(f"Changing values here creates a 'What-If' scenario inside the lab.\nOriginal Source: {ctx.get('source')}")

# --- הרצת הסימולציה ---
if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
    with st.spinner(f"Simulating {sim_paths} paths..."):
        
        sim_engine = PathSimulator(
            spot=sim_spot, 
            rate=ctx['rate'], 
            iv=sim_iv, 
            days=sim_days, 
            mult=sim_mult,
            n_paths=sim_paths
        )
        
        sim_engine.calculate_portfolio_pnl(ctx['legs'])
        metrics = sim_engine.get_analytics([0, 500, 1000], [-500, -1000])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Win Probability", f"{metrics.get('Touch 0', 0)*100:.1f}%")
        c2.metric("Chance > 500", f"{metrics.get('Touch 500', 0)*100:.1f}%")
        c3.metric("Risk < -500", f"{metrics.get('Risk -500', 0)*100:.1f}%", delta_color="inverse")
        c4.metric("Avg Worst Case", f"{metrics.get('Avg Min PnL', 0):,.0f}")
        
        st.plotly_chart(sim_engine.plot_results(), use_container_width=True)