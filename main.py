import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
import matplotlib.colors as mcolors
import calendar
import uuid

# --- IMPORTS FROM MODULES ---
import maof_logic as logic
import maof_strategies as strategies
import maof_data as data

# --- Page Config ---
st.set_page_config(layout="wide", page_title="MAOF Professional Simulator")

# --- CSS (Standard Layout - Safe) ---
st.markdown("""
<style>
    .stApp { direction: ltr; text-align: left; }
    h1, h2, h3, p, div, label, .stMarkdown, .stToast, .stButton, .stTabs, .stRadio, .stMetric, .stSelectbox { 
        text-align: left !important; 
        direction: ltr !important; 
    }
    .stNumberInput input { text-align: center; }
    
    /* Plotly Tooltip Fixes */
    .js-plotly-plot .plotly .hoverlayer .hovertext path,
    .js-plotly-plot .plotly .hoverlayer .hovertext rect {
        fill: none !important;
        stroke: none !important;
        opacity: 0 !important;
    }
    .js-plotly-plot .plotly .hoverlayer .hovertext text {
        font-family: 'Segoe UI', sans-serif !important;
        fill: black !important;
        font-size: 15px !important;
        font-weight: bold !important;
        text-shadow: -2px -2px 0 rgba(255,255,255,0.8), 2px -2px 0 rgba(255,255,255,0.8), -2px 2px 0 rgba(255,255,255,0.8), 2px 2px 0 rgba(255,255,255,0.8) !important;
    }
    
    [data-testid="stMetricValue"] { font-size: 24px; color: #0068c9; }
    
    /* Strategy Card Styling */
    .strategy-card {
        border: 1px solid #f0f0f0;
        border-radius: 6px;
        padding: 8px;
        margin-bottom: 10px;
        background-color: #ffffff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    .bull-header { color: #2ca02c; font-weight: bold; font-size: 1em; text-align: center; margin-bottom: 2px; }
    .bear-header { color: #d62728; font-weight: bold; font-size: 1em; text-align: center; margin-bottom: 2px; }
    .neutral-header { color: #1f77b4; font-weight: bold; font-size: 1em; text-align: center; margin-bottom: 2px; }
    
    .simulation-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #d6d6d6;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

st.title('🇮🇱 MAOF Professional Simulator')

# --- Helpers ---
def get_last_friday_of_month(year, month):
    last_day = calendar.monthrange(year, month)[1]
    target_date = date(year, month, last_day)
    while target_date.weekday() != 4: 
        target_date -= timedelta(days=1)
    return target_date

def get_default_expiry():
    today = date.today()
    this_month_expiry = get_last_friday_of_month(today.year, today.month)
    if today > this_month_expiry:
        next_month = today.month + 1 if today.month < 12 else 1
        next_year = today.year if today.month < 12 else today.year + 1
        return get_last_friday_of_month(next_year, next_month)
    return this_month_expiry

def get_color_gradient(c1, c2, n):
    rgb1 = np.array(mcolors.to_rgb(c1))
    rgb2 = np.array(mcolors.to_rgb(c2))
    colors = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0
        rgb = (1 - t) * rgb1 + t * rgb2
        colors.append(mcolors.to_hex(rgb))
    return colors

# --- Session State ---
DEFAULT_SPOT = 3700.0
DEFAULT_MULT = 50
DEFAULT_INTERVAL = 10
DEFAULT_VOL = 0.14
DEFAULT_RATE = 0.045

if 'expiry_date_val' not in st.session_state: st.session_state['expiry_date_val'] = get_default_expiry()
if 'days_to_expiry_val' not in st.session_state:
    delta = st.session_state['expiry_date_val'] - date.today()
    st.session_state['days_to_expiry_val'] = max(0, delta.days)
if 'spot_price_val' not in st.session_state: st.session_state['spot_price_val'] = DEFAULT_SPOT
if 'vol_input' not in st.session_state: st.session_state['vol_input'] = DEFAULT_VOL * 100
if 'rate_input' not in st.session_state: st.session_state['rate_input'] = DEFAULT_RATE * 100

if 'portfolio_a' not in st.session_state:
    st.session_state['portfolio_a'] = pd.DataFrame(columns=["Type", "Strike", "Qty", "Option Price"])
if 'portfolio_b' not in st.session_state:
    st.session_state['portfolio_b'] = pd.DataFrame(columns=["Type", "Strike", "Qty", "Option Price"])

# --- Runtime Events ---
def on_date_change():
    delta = st.session_state['expiry_date_val'] - date.today()
    st.session_state['days_to_expiry_val'] = max(0, delta.days)

def on_days_change():
    st.session_state['expiry_date_val'] = date.today() + timedelta(days=st.session_state['days_to_expiry_val'])

def refresh_market_data():
    price, source = data.get_market_price()
    if price and price > 0:
        st.session_state['spot_price_val'] = float(price)
        st.toast(f"✅ Updated ({source}): {price:,.2f}", icon="📈")
    else:
        st.toast("⚠️ Data fetch failed", icon="❌")

# --- Inputs ---
cols = st.columns([1, 1, 1, 1, 6]) 
with cols[0]:
    st.markdown("##### 📍 Spot")
    st.number_input("Spot", key='spot_price_val', step=1.0, format="%.2f", label_visibility="collapsed")
    if st.button("🔄 Refresh", use_container_width=True): refresh_market_data(), st.rerun()
with cols[1]:
    st.markdown("##### ⏳ Expiry")
    st.date_input("Date", key='expiry_date_val', min_value=date.today(), on_change=on_date_change, label_visibility="collapsed")
    st.number_input("Days", key='days_to_expiry_val', min_value=0, step=1, on_change=on_days_change, label_visibility="collapsed")
with cols[2]:
    st.markdown("##### 📊 Market")
    st.number_input("IV (%)", value=DEFAULT_VOL*100, step=0.5, key='vol_input')
    st.number_input("Rate (%)", value=DEFAULT_RATE*100, step=0.1, key='rate_input')
with cols[3]:
    st.markdown("##### ⚙️ Contract")
    multiplier = st.number_input("Mult", value=DEFAULT_MULT, step=10)
    strike_interval = st.number_input("Interval", value=DEFAULT_INTERVAL, step=5)
    num_strikes = st.number_input("Strikes", value=20, step=2)

# --- Engine Variables ---
spot = st.session_state['spot_price_val']
T = st.session_state['days_to_expiry_val'] / 365.0 
vol = st.session_state['vol_input'] / 100
r = st.session_state['rate_input'] / 100
if T < 0.0001: T = 0.0001 

# --- 1. OPTIONS CHAIN ---
st.divider()
st.subheader("📊 Options Chain")
center = round(spot / strike_interval) * strike_interval
strikes = [center + (i - num_strikes//2)*strike_interval for i in range(num_strikes + 1)]
chain_rows = []
for K in strikes:
    c_p, c_d, c_g, c_t, c_v = logic.bs_calc_raw(spot, K, T, r, vol, 'call')
    p_p, p_d, p_g, p_t, p_v = logic.bs_calc_raw(spot, K, T, r, vol, 'put')
    chain_rows.append({
        'C_Vega': int(c_v * multiplier), 'C_Theta': int(c_t * multiplier), 
        'C_Gamma': round(c_g * 100, 2), 'C_Delta': int(c_d * 100), 'Call_Price': int(c_p * multiplier),
        'Strike': int(K),
        'Put_Price': int(p_p * multiplier), 'P_Delta': int(p_d * 100), 
        'P_Gamma': round(p_g * 100, 2), 'P_Theta': int(p_t * multiplier), 'P_Vega': int(p_v * multiplier)
    })
df_chain = pd.DataFrame(chain_rows)
gb = GridOptionsBuilder.from_dataframe(df_chain)
gb.configure_default_column(resizable=True, filterable=False, sortable=False, suppressMenu=True, headerClass='center-header')
for col in ['C_Vega', 'C_Theta', 'C_Gamma', 'C_Delta', 'Call_Price']: gb.configure_column(col, width=90, cellStyle={'background-color': '#e6f2ff', 'text-align': 'center'})
for col in ['Put_Price', 'P_Delta', 'P_Gamma', 'P_Theta', 'P_Vega']: gb.configure_column(col, width=90, cellStyle={'background-color': '#ffe6e6', 'text-align': 'center'})
gb.configure_column("Strike", pinned="right", width=100, cellStyle={'background-color': '#e0e0e0', 'font-weight': 'bold', 'text-align': 'center'})
gridOptions = gb.build()
gridOptions['enableRtl'] = False 
AgGrid(df_chain, gridOptions=gridOptions, height=350, fit_columns_on_grid_load=True, allow_unsafe_jscode=True, theme='balham')

# --- 2. STRATEGY WIZARD ---
st.divider()
with st.expander("🪄 Strategy Wizard", expanded=True):
    c_tgt, _ = st.columns([1, 4])
    with c_tgt:
        target_portfolio = st.radio("Load Strategy to Portfolio:", ["A", "B"], horizontal=True)
    
    def render_cell(container, strat_list, key_suffix):
        with container:
            st.markdown(f"<div class='strategy-card'>", unsafe_allow_html=True)
            sel = st.selectbox("Select:", strat_list, key=f"sel_{key_suffix}", label_visibility="collapsed")
            if st.button("Load", key=f"btn_{key_suffix}", use_container_width=True):
                legs = strategies.generate_strategy_legs(sel, spot, strike_interval)
                rows = []
                for leg in legs:
                    p, _, _, _, _ = logic.bs_calc_raw(spot, leg['Strike'], T, r, vol, leg['Type'])
                    price = int(p * multiplier)
                    rows.append({"Type": leg['Type'], "Strike": leg['Strike'], "Qty": leg['Qty'], "Option Price": price})
                
                new_df = pd.DataFrame(rows)
                target_key = "portfolio_a" if target_portfolio == "A" else "portfolio_b"
                refresh_key = f"refresh_key_{target_portfolio}"
                
                st.session_state[target_key] = new_df
                if refresh_key not in st.session_state: st.session_state[refresh_key] = 0
                st.session_state[refresh_key] += 1
                
                st.toast(f"Loaded '{sel}' to Portfolio {target_portfolio}", icon="🪄")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # --- Matrix ---
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='bull-header'>🐂 Bullish (Low IV)</div>", unsafe_allow_html=True)
        render_cell(c1, strategies.STRATEGY_MATRIX["Bullish"]["Low IV"], "bull_low")
    with c2:
        st.markdown("<div class='bull-header'>🐂 Bullish (Med IV)</div>", unsafe_allow_html=True)
        render_cell(c2, strategies.STRATEGY_MATRIX["Bullish"]["Medium IV"], "bull_med")
    with c3:
        st.markdown("<div class='bull-header'>🐂 Bullish (High IV)</div>", unsafe_allow_html=True)
        render_cell(c3, strategies.STRATEGY_MATRIX["Bullish"]["High IV"], "bull_high")
        
    st.markdown("---")
    
    c4, c5, c6 = st.columns(3)
    with c4:
        st.markdown("<div class='neutral-header'>😐 Neutral (Low IV)</div>", unsafe_allow_html=True)
        render_cell(c4, strategies.STRATEGY_MATRIX["Neutral"]["Low IV"], "neut_low")
    with c5:
        st.markdown("<div class='neutral-header'>😐 Neutral (Med IV)</div>", unsafe_allow_html=True)
        render_cell(c5, strategies.STRATEGY_MATRIX["Neutral"]["Medium IV"], "neut_med")
    with c6:
        st.markdown("<div class='neutral-header'>😐 Neutral (High IV)</div>", unsafe_allow_html=True)
        render_cell(c6, strategies.STRATEGY_MATRIX["Neutral"]["High IV"], "neut_high")

    st.markdown("---")
    
    c7, c8, c9 = st.columns(3)
    with c7:
        st.markdown("<div class='bear-header'>🐻 Bearish (Low IV)</div>", unsafe_allow_html=True)
        render_cell(c7, strategies.STRATEGY_MATRIX["Bearish"]["Low IV"], "bear_low")
    with c8:
        st.markdown("<div class='bear-header'>🐻 Bearish (Med IV)</div>", unsafe_allow_html=True)
        render_cell(c8, strategies.STRATEGY_MATRIX["Bearish"]["Medium IV"], "bear_med")
    with c9:
        st.markdown("<div class='bear-header'>🐻 Bearish (High IV)</div>", unsafe_allow_html=True)
        render_cell(c9, strategies.STRATEGY_MATRIX["Bearish"]["High IV"], "bear_high")

# --- 3. PORTFOLIO MANAGEMENT ---
st.divider()
st.subheader("💼 Portfolio Management")

js_total_cost_calc = JsCode("""
function(params) {
    if (params.data.Qty && params.data['Option Price']) {
        return params.data.Qty * params.data['Option Price'];
    }
    return 0;
}
""")

def render_portfolio_editor(key, df_key, color_hex):
    if f"refresh_key_{key}" not in st.session_state: st.session_state[f"refresh_key_{key}"] = 0
    if 'Option Price' not in st.session_state[df_key].columns:
         if 'Cost' in st.session_state[df_key].columns: st.session_state[df_key].rename(columns={'Cost': 'Option Price'}, inplace=True)
         else: st.session_state[df_key]['Option Price'] = 0
    
    st.markdown(f"<div style='background-color: {color_hex}; padding: 5px; border-radius: 5px; text-align: center; font-weight: bold;'>Portfolio {key}</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    add_btn = c1.button(f"➕ Add", key=f"add_{key}", use_container_width=True)
    calc_btn = c2.button(f"🧮 Calc BS", key=f"calc_{key}", use_container_width=True)
    clear_btn = c3.button(f"🗑️ Clear", key=f"clr_{key}", use_container_width=True)

    if add_btn:
        # --- FIX: INITIALIZE WITH ZEROS ---
        new_row = pd.DataFrame([{"Type": "Call", "Strike": 0, "Qty": 0, "Option Price": 0}])
        st.session_state[df_key] = pd.concat([st.session_state[df_key], new_row], ignore_index=True)
        st.session_state[f"refresh_key_{key}"] += 1
        st.rerun()
    if clear_btn:
        st.session_state[df_key] = pd.DataFrame(columns=["Type", "Strike", "Qty", "Option Price"])
        st.session_state[f"refresh_key_{key}"] += 1
        st.rerun()

    display_df = st.session_state[df_key].copy()
    if 'Total Cost' not in display_df.columns: display_df['Total Cost'] = display_df['Qty'] * display_df['Option Price']

    gb_p = GridOptionsBuilder.from_dataframe(display_df)
    gb_p.configure_default_column(editable=True, resizable=True, suppressMenu=True)
    gb_p.configure_column("Type", cellEditor='agSelectCellEditor', cellEditorParams={'values': ['Call', 'Put']}, width=80)
    gb_p.configure_column("Strike", type=["numericColumn"], precision=0, width=90)
    gb_p.configure_column("Qty", type=["numericColumn"], precision=0, width=70)
    gb_p.configure_column("Option Price", type=["numericColumn"], precision=0, width=100)
    gb_p.configure_column("Total Cost", valueGetter=js_total_cost_calc, type=["numericColumn"], precision=0, editable=False, width=110, cellStyle={'background-color': '#f0f0f0', 'font-weight': 'bold'})
    
    dynamic_key = f"grid_{key}_{st.session_state[f'refresh_key_{key}']}"
    
    grid_opts = gb_p.build()
    grid_opts['enableRtl'] = False 
    
    response = AgGrid(display_df, gridOptions=grid_opts, update_mode=GridUpdateMode.MODEL_CHANGED, height=400, theme='balham', key=dynamic_key, fit_columns_on_grid_load=True, allow_unsafe_jscode=True)
    
    res_df = response['data']
    if not res_df.empty:
        res_df['Strike'] = res_df['Strike'].astype(int)
        res_df['Qty'] = res_df['Qty'].astype(int)
        res_df['Option Price'] = res_df['Option Price'].astype(int)
        
        # Force Update Cost
        res_df['Total Cost'] = res_df['Qty'] * res_df['Option Price'] 
        save_df = res_df.drop(columns=['Total Cost']) if 'Total Cost' in res_df.columns else res_df
        st.session_state[df_key] = save_df

    if calc_btn:
        df = st.session_state[df_key]
        if not df.empty:
            for index, row in df.iterrows():
                try:
                    p, _, _, _, _ = logic.bs_calc_raw(spot, float(row['Strike']), T, r, vol, row['Type'])
                    df.at[index, 'Option Price'] = int(p * multiplier)
                except: pass
            st.session_state[df_key] = df
            st.session_state[f"refresh_key_{key}"] += 1
            st.toast(f"Recalculated Prices for Portfolio {key}", icon="🧮")
            st.rerun()
    
    total_cost = res_df['Total Cost'].sum() if not res_df.empty else 0
    st.metric(f"Total Cost {key}", f"₪{total_cost:,.0f}")
    return res_df

col_a, col_b = st.columns(2)
with col_a: df_a = render_portfolio_editor("A", "portfolio_a", "#e6f2ff")
with col_b: df_b = render_portfolio_editor("B", "portfolio_b", "#ffe6e6")

# --- 4. RISK & GRAPHS ---
if not df_a.empty or not df_b.empty:
    st.divider()
    st.subheader("⚖️ Risk Summary")
    
    greeks_a = logic.calculate_portfolio_greeks(df_a, spot, T, r, vol, multiplier)
    greeks_b = logic.calculate_portfolio_greeks(df_b, spot, T, r, vol, multiplier)
    
    def fmt_curr(val):
        if val == float('inf'): return "INF"
        if val == float('-inf'): return "-INF"
        return f"₪{val:,.0f}"

    df_risk = pd.DataFrame({
        'Metric': ['Total Cost (Exposure)', 'Total P&L (Current)', 'Max Profit', 'Max Loss', 'Delta', 'Gamma', 'Theta', 'Vega'],
        'Port_A': [
            fmt_curr(greeks_a['Cost']), fmt_curr(greeks_a['PnL']), fmt_curr(greeks_a['MaxProfit']), fmt_curr(greeks_a['MaxLoss']),
            f"{greeks_a['Delta']:,.0f}", f"{greeks_a['Gamma']:,.2f}", fmt_curr(greeks_a['Theta']), fmt_curr(greeks_a['Vega'])
        ],
        'Port_B': [
            fmt_curr(greeks_b['Cost']), fmt_curr(greeks_b['PnL']), fmt_curr(greeks_b['MaxProfit']), fmt_curr(greeks_b['MaxLoss']),
            f"{greeks_b['Delta']:,.0f}", f"{greeks_b['Gamma']:,.2f}", fmt_curr(greeks_b['Theta']), fmt_curr(greeks_b['Vega'])
        ]
    })
    
    gb_risk = GridOptionsBuilder.from_dataframe(df_risk)
    gb_risk.configure_default_column(resizable=False, filterable=False, sortable=False, suppressMenu=True, headerClass='center-header')
    gb_risk.configure_column("Metric", headerName="Metric", width=180, cellStyle={'font-weight': 'bold', 'text-align': 'left', 'background-color': '#f9f9f9'})
    gb_risk.configure_column("Port_A", headerName="🔵 Portfolio A", width=150, cellStyle={'background-color': '#e6f2ff', 'text-align': 'center'})
    gb_risk.configure_column("Port_B", headerName="🔴 Portfolio B", width=150, cellStyle={'background-color': '#ffe6e6', 'text-align': 'center'})
    gridOptions_risk = gb_risk.build()
    gridOptions_risk['enableRtl'] = False 
    
    # Force refresh
    risk_key = str(uuid.uuid4())
    AgGrid(df_risk, gridOptions=gridOptions_risk, height=300, fit_columns_on_grid_load=True, allow_unsafe_jscode=True, theme='balham', key=risk_key)

    st.divider()
    
    with st.container():
        st.markdown('<div class="simulation-box">', unsafe_allow_html=True)
        st.subheader("🧪 Simulation Scenarios")
        st.info("Changes here affect graphs below, not the tables above.")
        
        sim_cols = st.columns([1, 1, 1, 3])
        with sim_cols[0]:
            vol_shock = st.slider("IV Shock (%)", min_value=-20, max_value=20, value=0, step=1)
            sim_vol = max(0.01, vol + (vol_shock / 100.0))
        with sim_cols[1]:
            st.metric("Simulated IV", f"{sim_vol*100:.1f}%", delta=f"{vol_shock:+}%")
        st.markdown('</div>', unsafe_allow_html=True)

    col_graph, col_controls = st.columns([5, 1])
    with col_controls:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("##### ⚙️ Graph Settings")
        num_slices = st.number_input("Time Slices", min_value=1, max_value=10, value=5, step=1)
        st.markdown("---")
        chart_range_pct = st.number_input("X-Axis Range (+/-%)", min_value=0.5, max_value=15.0, value=5.0, step=0.5, format="%.1f")
        st.markdown("---")
        comparison_mode = st.radio("Graph Mode:", ["Separate Lines", "Diff (A - B)"])
        lower_bound = spot * (1 - chart_range_pct / 100)
        upper_bound = spot * (1 + chart_range_pct / 100)
        spot_range = np.linspace(lower_bound, upper_bound, 80)

    # --- 2D Graph ---
    with col_graph:
        st.subheader("📈 2D Analysis")
        fig_2d = go.Figure()
        time_fractions = np.linspace(0, 1, num_slices)
        blues = get_color_gradient('#87CEFA', '#000080', num_slices)
        reds = get_color_gradient('#FFA07A', '#8B0000', num_slices)
        greens = get_color_gradient('#90EE90', '#006400', num_slices)
        total_days = st.session_state['days_to_expiry_val']
        
        for i, frac in enumerate(time_fractions):
            is_expiry = (frac == 1.0)
            t_new = T * (1 - frac)
            if t_new < 0.0001: t_new = 0.00001
            days_passed = frac * total_days
            label_txt = f"{days_passed:.1f} Days"
            if frac == 0: label_txt = "Today (0d)"
            elif frac == 1: label_txt = f"Expiry ({total_days}d)"
            width = 3 if (frac == 0 or frac == 1) else 1.5
            dash = 'solid' if (frac == 0 or frac == 1) else 'dot'
            
            pnl_a = np.array([logic.calculate_portfolio_pnl(df_a, s, t_new, r, sim_vol, multiplier, is_expiry) for s in spot_range]) if not df_a.empty else np.zeros_like(spot_range)
            pnl_b = np.array([logic.calculate_portfolio_pnl(df_b, s, t_new, r, sim_vol, multiplier, is_expiry) for s in spot_range]) if not df_b.empty else np.zeros_like(spot_range)
            
            if comparison_mode == "Separate Lines":
                if not df_a.empty:
                    fig_2d.add_trace(go.Scatter(x=spot_range, y=pnl_a, mode='lines', name=f"A: {label_txt}", line=dict(color=blues[i], width=width, dash=dash), hovertemplate=f"<b>Port A ({label_txt})</b><br>Spot: %{{x:,.0f}}<br>P&L: ₪%{{y:,.0f}}<extra></extra>"))
                if not df_b.empty:
                    fig_2d.add_trace(go.Scatter(x=spot_range, y=pnl_b, mode='lines', name=f"B: {label_txt}", line=dict(color=reds[i], width=width, dash=dash), hovertemplate=f"<b>Port B ({label_txt})</b><br>Spot: %{{x:,.0f}}<br>P&L: ₪%{{y:,.0f}}<extra></extra>"))
            else:
                pnl_diff = pnl_a - pnl_b
                fig_2d.add_trace(go.Scatter(x=spot_range, y=pnl_diff, mode='lines', name=f"Diff: {label_txt}", line=dict(color=greens[i], width=width, dash=dash), hovertemplate=f"<b>Diff A-B ({label_txt})</b><br>Spot: %{{x:,.0f}}<br>Diff: ₪%{{y:,.0f}}<extra></extra>"))

        fig_2d.add_vline(x=spot, line_width=1, line_dash="dash", line_color="gray")
        fig_2d.add_hline(y=0, line_width=1, line_color="black")
        fig_2d.update_layout(title=f"Analysis: {comparison_mode} (IV Shock: {vol_shock}%)", xaxis_title="Spot Price", yaxis_title="P&L (NIS)", hovermode="closest", hoverlabel=dict(bgcolor="rgba(255,255,255,0)", bordercolor="rgba(255,255,255,0)"), height=550)
        st.plotly_chart(fig_2d, use_container_width=True)

    # --- 3D Graph ---
    col_3d_title, col_3d_sel = st.columns([2, 1])
    with col_3d_title: st.subheader("🎲 3D Surface")
    with col_3d_sel: view_mode = st.radio("3D Mode:", ["Diff (A - B)", "Portfolio A", "Portfolio B"], horizontal=True)

    days_range = np.linspace(0, st.session_state['days_to_expiry_val'], 25)
    X, Y = np.meshgrid(spot_range, days_range)
    Z = np.zeros_like(X)
    colorscale = 'RdYlGn'
    z_title = "Diff (A - B)"
    chart_title = "Advantage A vs B"
    if "Portfolio A" in view_mode: colorscale, z_title, chart_title = 'RdBu', "P&L A", "Portfolio A"
    elif "Portfolio B" in view_mode: colorscale, z_title, chart_title = 'RdBu', "P&L B", "Portfolio B"

    for i in range(len(days_range)): 
        d_passed = days_range[i]
        t_new = (st.session_state['days_to_expiry_val'] - d_passed) / 365.0
        is_expiry_3d = (t_new < 0.001)
        if t_new < 0.0001: t_new = 0.00001
        for j in range(len(spot_range)):
            s_new = spot_range[j]
            val_a = logic.calculate_portfolio_pnl(df_a, s_new, t_new, r, sim_vol, multiplier, is_expiry_3d)
            val_b = logic.calculate_portfolio_pnl(df_b, s_new, t_new, r, sim_vol, multiplier, is_expiry_3d)
            if "Diff" in view_mode: Z[i, j] = val_a - val_b
            elif "Portfolio A" in view_mode: Z[i, j] = val_a
            elif "Portfolio B" in view_mode: Z[i, j] = val_b

    fig_3d = go.Figure(data=[go.Surface(z=Z, x=spot_range, y=days_range, colorscale=colorscale, cmid=0, opacity=0.9, hovertemplate=f"Spot: %{{x:,.0f}}<br>Days: %{{y:,.1f}}<br>{z_title}: ₪%{{z:,.0f}}<extra></extra>", contours_z=dict(show=False), contours_x=dict(highlight=False), contours_y=dict(highlight=False), showscale=True, colorbar=dict(title="NIS"))])
    fig_3d.update_layout(title=f"{chart_title} (IV Shock: {vol_shock}%)", scene=dict(xaxis_title='Spot', yaxis_title='Days Passed', zaxis_title='P&L', xaxis=dict(showgrid=True), yaxis=dict(showgrid=True), zaxis=dict(showgrid=True)), margin=dict(l=0, r=0, b=0, t=30), height=600, hovermode="closest", hoverlabel=dict(bgcolor="rgba(255,255,255,0)", bordercolor="rgba(255,255,255,0)"))
    st.plotly_chart(fig_3d, use_container_width=True)