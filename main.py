import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, time, datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
import matplotlib.colors as mcolors
import calendar
import uuid

# --- IMPORTS FROM MODULES ---
import maof_logic as logic
import maof_strategies as strategies
import maof_data as data

# --- Page Config ---
st.set_page_config(layout="wide", page_title="DOR - Derivatives Operation Room")

# --- CSS ---
st.markdown("""
<style>
    .stApp { direction: ltr; text-align: left; }
    
    .block-container {
        max_width: 1400px;
        padding-top: 1rem !important;
        padding-bottom: 20rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    h1, h2, h3, p, div, label, .stMarkdown, .stToast, .stButton, .stTabs, .stRadio, .stMetric, .stSelectbox, .stTextInput { 
        text-align: left !important; 
        direction: ltr !important; 
    }
    .stNumberInput input { text-align: center; }
    
    /* AgGrid Header Centering */
    .ag-header-cell-label {
        justify-content: center;
    }

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
        font-size: 14px !important;
        font-weight: bold !important;
        text-shadow: -1px -1px 0 white, 1px -1px 0 white, -1px 1px 0 white, 1px 1px 0 white !important;
    }
    
    [data-testid="stMetricValue"] { font-size: 22px; color: #0068c9; }
    
    .strategy-card {
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        padding: 8px;
        margin-bottom: 5px;
        background-color: #ffffff;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    .bull-header { color: #2ca02c; font-weight: bold; font-size: 0.95em; text-align: center; margin-bottom: 4px; }
    .bear-header { color: #d62728; font-weight: bold; font-size: 0.95em; text-align: center; margin-bottom: 4px; }
    .neutral-header { color: #1f77b4; font-weight: bold; font-size: 0.95em; text-align: center; margin-bottom: 4px; }
    
    .simulation-box {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 15px;
    }
    
    .streamlit-expanderHeader {
        font-size: 1rem !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

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

# --- PnL Explicit Calculation (Fix for 2D Graph) ---
def calculate_explicit_pnl(df, spot, t, r, vol, mult):
    """Calculates PnL by explicitly subtracting the initial cost from the theoretical value."""
    total_pnl = 0.0
    if df.empty: return 0.0
    
    for _, row in df.iterrows():
        try:
            # Current Theoretical Price
            p, _, _, _, _ = logic.bs_calc_raw(spot, float(row['Strike']), t, r, vol, row['Type'])
            theor_price = p * mult
            
            # Initial Cost (from DataFrame)
            entry_price = float(row['Option Price'])
            qty = float(row['Qty'])
            
            # PnL = (Value - Cost) * Qty
            leg_pnl = (theor_price - entry_price) * qty
            total_pnl += leg_pnl
        except:
            pass
    return total_pnl

# --- Gap Parsing Logic (DD:HH:MM) ---
def parse_gap_string(gap_str):
    try:
        parts = gap_str.split(':')
        if len(parts) == 3:
            d = int(parts[0])
            h = int(parts[1])
            m = int(parts[2])
            return (d * 24.0) + h + (m / 60.0)
        elif len(parts) == 2: 
            h = int(parts[0])
            m = int(parts[1])
            return h + (m / 60.0)
        else:
            return 16.33
    except:
        return 16.33

def format_hours_to_string(total_hours):
    try:
        total_seconds = int(total_hours * 3600)
        days = total_seconds // 86400
        rem = total_seconds % 86400
        hours = rem // 3600
        mins = (rem % 3600) // 60
        return f"{days:02d}:{hours:02d}:{mins:02d}"
    except:
        return "00:16:20"

# --- Session State Defaults ---
DEFAULT_SPOT = 3700.0
DEFAULT_MULT = 50
DEFAULT_INTERVAL = 10
DEFAULT_VOL = 0.14
DEFAULT_RATE = 0.0425 

# PRE-INIT SPOT
if 'spot_price_val' not in st.session_state: 
    st.session_state['spot_price_val'] = DEFAULT_SPOT
elif st.session_state['spot_price_val'] <= 0: 
    st.session_state['spot_price_val'] = DEFAULT_SPOT

if 'mode' not in st.session_state: st.session_state['mode'] = "Standard (Days)"
if 'annual_days' not in st.session_state: st.session_state['annual_days'] = 365 

if 'expiry_date_val' not in st.session_state: st.session_state['expiry_date_val'] = get_default_expiry()
if 'days_to_expiry_val' not in st.session_state:
    delta = st.session_state['expiry_date_val'] - date.today()
    st.session_state['days_to_expiry_val'] = max(0, delta.days)

if 'vol_input' not in st.session_state: st.session_state['vol_input'] = DEFAULT_VOL * 100
if 'rate_input' not in st.session_state: st.session_state['rate_input'] = DEFAULT_RATE * 100

# Intraday State
if 'current_time' not in st.session_state: st.session_state['current_time'] = time(10, 0)
if 'close_time' not in st.session_state: st.session_state['close_time'] = time(17, 40)
if 'gap_str' not in st.session_state: st.session_state['gap_str'] = "00:16:20"

# Calc Helper State
if 'calc_d1' not in st.session_state: st.session_state['calc_d1'] = date.today()
if 'calc_t1' not in st.session_state: st.session_state['calc_t1'] = time(17, 40)
if 'calc_d2' not in st.session_state: st.session_state['calc_d2'] = date.today() + timedelta(days=1)
if 'calc_t2' not in st.session_state: st.session_state['calc_t2'] = time(10, 0)

if 'portfolio_a' not in st.session_state:
    st.session_state['portfolio_a'] = pd.DataFrame(columns=["Type", "Strike", "Qty", "Option Price"])
if 'portfolio_b' not in st.session_state:
    st.session_state['portfolio_b'] = pd.DataFrame(columns=["Type", "Strike", "Qty", "Option Price"])

# --- Callbacks ---
def on_date_change():
    delta = st.session_state['expiry_date_val'] - date.today()
    st.session_state['days_to_expiry_val'] = max(0, delta.days)

def on_days_change():
    st.session_state['expiry_date_val'] = date.today() + timedelta(days=st.session_state['days_to_expiry_val'])

def apply_gap_callback():
    dt1 = datetime.combine(st.session_state['calc_d1'], st.session_state['calc_t1'])
    dt2 = datetime.combine(st.session_state['calc_d2'], st.session_state['calc_t2'])
    diff = dt2 - dt1
    hours_diff = diff.total_seconds() / 3600.0
    if hours_diff < 0: hours_diff = 0
    st.session_state['gap_str'] = format_hours_to_string(hours_diff)

def on_mode_change():
    if st.session_state['mode_radio'] == "Intraday (0DTE)":
        st.session_state['current_time'] = time(10, 0)
        st.session_state['close_time'] = time(17, 40)
        st.session_state['gap_str'] = "00:16:20"
    st.session_state['mode'] = st.session_state['mode_radio']

# --- Top Header & Mode Switch ---
c_title, c_mode = st.columns([3, 1])
with c_title:
    st.title('DOR - Derivatives Operation Room')
with c_mode:
    st.markdown("<br>", unsafe_allow_html=True)
    st.radio("Simulation Mode", ["Standard (Days)", "Intraday (0DTE)"], 
             horizontal=True, 
             label_visibility="collapsed", 
             key='mode_radio', 
             on_change=on_mode_change)

if 'mode_radio' not in st.session_state: st.session_state['mode_radio'] = "Standard (Days)"
st.session_state['mode'] = st.session_state['mode_radio']

# --- Inputs ---
cols = st.columns([1, 1.2, 1, 1, 1, 3], gap="small") 

# 1. Spot
with cols[0]:
    st.markdown("##### 📍 Spot")
    ui_spot = st.number_input("Spot", key='spot_price_val', step=1.0, format="%.2f", label_visibility="collapsed")

# 2. Time Controls
with cols[1]:
    if st.session_state['mode'] == "Standard (Days)":
        st.markdown("##### ⏳ Expiry")
        st.date_input("Date", key='expiry_date_val', min_value=date.today(), on_change=on_date_change, label_visibility="collapsed")
        st.number_input("Days", key='days_to_expiry_val', min_value=0, step=1, on_change=on_days_change, label_visibility="collapsed")
        T_calc = st.session_state['days_to_expiry_val'] / float(st.session_state.get('annual_days', 365))
        
    else: # Intraday Mode
        st.markdown("##### ⏱️ Intraday")
        c_t1, c_t2 = st.columns(2)
        with c_t1: t_now = st.time_input("Now", key='current_time', label_visibility="collapsed")
        with c_t2: t_close = st.time_input("End", key='close_time', label_visibility="collapsed")
        
        with st.expander("🧮 Calc Gap"):
            st.date_input("Trade End", key="calc_d1")
            st.time_input("Time", key="calc_t1")
            st.date_input("Settle", key="calc_d2")
            st.time_input("Time", key="calc_t2")
            st.button("Apply Gap", on_click=apply_gap_callback)

        st.text_input("Gap (DD:HH:MM)", key='gap_str')
        gap_hours = parse_gap_string(st.session_state['gap_str'])

        dt_now = datetime.combine(date.today(), t_now)
        dt_close = datetime.combine(date.today(), t_close)
        if dt_now > dt_close: minutes_remaining = 0
        else: minutes_remaining = (dt_close - dt_now).total_seconds() / 60.0
        
        total_hours = (minutes_remaining / 60.0) + gap_hours
        annual_hours = float(st.session_state.get('annual_days', 365)) * 24.0
        T_calc = total_hours / annual_hours

# 3. Market Data
with cols[2]:
    st.markdown("##### 📊 Market")
    st.number_input("IV (%)", step=0.5, key='vol_input')
    st.number_input("Rate (%)", step=0.1, key='rate_input')

# 4. Model Config
with cols[3]:
    st.markdown("##### 📐 Model")
    st.selectbox("Days/Year", [365, 252], key='annual_days', label_visibility="collapsed")

# 5. Contract Specs
with cols[4]:
    st.markdown("##### ⚙️ Contract")
    multiplier = st.number_input("Mult", value=DEFAULT_MULT, step=10)
    strike_interval = st.number_input("Interval", value=DEFAULT_INTERVAL, step=5)
    num_strikes = st.number_input("Strikes", value=20, step=2)

# --- GLOBAL VARIABLES & SAFETY ENGINE ---
calculation_spot = ui_spot if (ui_spot is not None and ui_spot > 0) else DEFAULT_SPOT

vol = st.session_state['vol_input'] / 100
r = st.session_state['rate_input'] / 100
T = max(0.00001, T_calc)

# --- 1. OPTIONS CHAIN ---
st.divider()
with st.expander("📊 Options Chain", expanded=True):
    center = round(calculation_spot / strike_interval) * strike_interval
    strikes = [center + (i - num_strikes//2)*strike_interval for i in range(num_strikes + 1)]
    chain_rows = []
    
    for K in strikes:
        try:
            c_p, c_d, c_g, c_t, c_v = logic.bs_calc_raw(calculation_spot, K, T, r, vol, 'call')
            p_p, p_d, p_g, p_t, p_v = logic.bs_calc_raw(calculation_spot, K, T, r, vol, 'put')
            
            chain_rows.append({
                'C_Vega': int(c_v * multiplier), 'C_Theta': int(c_t * multiplier), 
                'C_Gamma': round(c_g * 100, 2), 'C_Delta': int(c_d * 100), 'Call_Price': int(c_p * multiplier),
                'Strike': int(K),
                'Put_Price': int(p_p * multiplier), 'P_Delta': int(p_d * 100), 
                'P_Gamma': round(p_g * 100, 2), 'P_Theta': int(p_t * multiplier), 'P_Vega': int(p_v * multiplier)
            })
        except:
            chain_rows.append({'Strike': int(K), 'Call_Price': 0, 'Put_Price': 0})

    df_chain = pd.DataFrame(chain_rows)
    gb = GridOptionsBuilder.from_dataframe(df_chain)
    gb.configure_default_column(resizable=True, filterable=False, sortable=False, suppressMenu=True, headerClass='center-header')
    
    if not df_chain.empty:
        for col in ['C_Vega', 'C_Theta', 'C_Gamma', 'C_Delta', 'Call_Price']: 
            if col in df_chain.columns: gb.configure_column(col, width=90, cellStyle={'background-color': '#e6f2ff', 'text-align': 'center'})
        for col in ['Put_Price', 'P_Delta', 'P_Gamma', 'P_Theta', 'P_Vega']: 
            if col in df_chain.columns: gb.configure_column(col, width=90, cellStyle={'background-color': '#ffe6e6', 'text-align': 'center'})
        if "Strike" in df_chain.columns:
            gb.configure_column("Strike", pinned="right", width=100, cellStyle={'background-color': '#e0e0e0', 'font-weight': 'bold', 'text-align': 'center'})
    
    gridOptions = gb.build()
    gridOptions['rowHeight'] = 30
    gridOptions['headerHeight'] = 35
    gridOptions['enableRtl'] = False 
    
    AgGrid(df_chain, gridOptions=gridOptions, height=300, theme='balham', key='chain_grid_main')

# --- 2. STRATEGY WIZARD ---
st.divider()
with st.expander("🪄 Strategy Wizard", expanded=True):
    c_tgt, _ = st.columns([1, 4])
    with c_tgt:
        target_portfolio = st.radio("Target:", ["A", "B"], horizontal=True)
    
    def render_cell(container, strat_list, key_suffix):
        with container:
            st.markdown(f"<div class='strategy-card'>", unsafe_allow_html=True)
            sel = st.selectbox("", strat_list, key=f"sel_{key_suffix}", label_visibility="collapsed")
            if st.button("Load", key=f"btn_{key_suffix}", use_container_width=True):
                legs = strategies.generate_strategy_legs(sel, calculation_spot, strike_interval)
                rows = []
                for leg in legs:
                    p, _, _, _, _ = logic.bs_calc_raw(calculation_spot, leg['Strike'], T, r, vol, leg['Type'])
                    price = int(p * multiplier)
                    rows.append({"Type": leg['Type'], "Strike": leg['Strike'], "Qty": leg['Qty'], "Option Price": price})
                
                new_df = pd.DataFrame(rows)
                target_key = "portfolio_a" if target_portfolio == "A" else "portfolio_b"
                refresh_key = f"refresh_key_{target_portfolio}"
                st.session_state[target_key] = new_df
                if refresh_key not in st.session_state: st.session_state[refresh_key] = 0
                st.session_state[refresh_key] += 1
                st.toast(f"Loaded '{sel}'", icon="🪄")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="small")
    with c1:
        st.markdown("<div class='bull-header'>🐂 Bullish (Low IV)</div>", unsafe_allow_html=True)
        render_cell(c1, strategies.STRATEGY_MATRIX["Bullish"]["Low IV"], "bull_low")
    with c2:
        st.markdown("<div class='bull-header'>🐂 Bullish (Med IV)</div>", unsafe_allow_html=True)
        render_cell(c2, strategies.STRATEGY_MATRIX["Bullish"]["Medium IV"], "bull_med")
    with c3:
        st.markdown("<div class='bull-header'>🐂 Bullish (High IV)</div>", unsafe_allow_html=True)
        render_cell(c3, strategies.STRATEGY_MATRIX["Bullish"]["High IV"], "bull_high")
        
    c4, c5, c6 = st.columns(3, gap="small")
    with c4:
        st.markdown("<div class='neutral-header'>😐 Neutral (Low IV)</div>", unsafe_allow_html=True)
        render_cell(c4, strategies.STRATEGY_MATRIX["Neutral"]["Low IV"], "neut_low")
    with c5:
        st.markdown("<div class='neutral-header'>😐 Neutral (Med IV)</div>", unsafe_allow_html=True)
        render_cell(c5, strategies.STRATEGY_MATRIX["Neutral"]["Medium IV"], "neut_med")
    with c6:
        st.markdown("<div class='neutral-header'>😐 Neutral (High IV)</div>", unsafe_allow_html=True)
        render_cell(c6, strategies.STRATEGY_MATRIX["Neutral"]["High IV"], "neut_high")

    c7, c8, c9 = st.columns(3, gap="small")
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
    grid_opts['rowHeight'] = 35 
    grid_opts['headerHeight'] = 35
    
    response = AgGrid(display_df, gridOptions=grid_opts, update_mode=GridUpdateMode.MODEL_CHANGED, height=300, theme='balham', key=dynamic_key, fit_columns_on_grid_load=True, allow_unsafe_jscode=True)
    
    res_df = response['data']
    if not res_df.empty:
        res_df['Strike'] = res_df['Strike'].astype(int)
        res_df['Qty'] = res_df['Qty'].astype(int)
        res_df['Option Price'] = res_df['Option Price'].astype(int)
        res_df['Total Cost'] = res_df['Qty'] * res_df['Option Price'] 
        st.session_state[df_key] = res_df.drop(columns=['Total Cost']) if 'Total Cost' in res_df.columns else res_df

    if calc_btn:
        df = st.session_state[df_key]
        if not df.empty:
            for index, row in df.iterrows():
                try:
                    p, _, _, _, _ = logic.bs_calc_raw(calculation_spot, float(row['Strike']), T, r, vol, row['Type'])
                    df.at[index, 'Option Price'] = int(p * multiplier)
                except: pass
            st.session_state[df_key] = df
            st.session_state[f"refresh_key_{key}"] += 1
            st.toast(f"Recalculated", icon="🧮")
            st.rerun()
    
    total_cost = res_df['Total Cost'].sum() if not res_df.empty else 0
    st.metric(f"Total Cost {key}", f"{total_cost:,.0f}")
    return res_df

col_a, col_b = st.columns(2)
with col_a: df_a = render_portfolio_editor("A", "portfolio_a", "#e6f2ff")
with col_b: df_b = render_portfolio_editor("B", "portfolio_b", "#ffe6e6")

# --- 4. RISK SUMMARY ---
if not df_a.empty or not df_b.empty:
    st.divider()
    st.subheader("⚖️ Risk Summary")
    
    greeks_a = logic.calculate_portfolio_greeks(df_a, calculation_spot, T, r, vol, multiplier)
    greeks_b = logic.calculate_portfolio_greeks(df_b, calculation_spot, T, r, vol, multiplier)
    
    def fmt_curr(val):
        if val == float('inf'): return "INF"
        if val == float('-inf'): return "-INF"
        return f"{val:,.0f}"

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
    risk_key = str(uuid.uuid4())
    AgGrid(df_risk, gridOptions=gridOptions_risk, height=300, fit_columns_on_grid_load=True, allow_unsafe_jscode=True, theme='balham', key=risk_key)

    st.divider()
    
    # --- 5. GRAPHS & ANALYSIS ---
    col_main_controls, _ = st.columns([1, 2])
    with col_main_controls:
        st.markdown("##### ⚙️ Graph Settings")
        chart_range_pct = st.number_input("Zoom (+/-%)", min_value=0.5, max_value=15.0, value=5.0, step=0.5, format="%.1f")
        lower_bound = calculation_spot * (1 - chart_range_pct / 100)
        upper_bound = calculation_spot * (1 + chart_range_pct / 100)
        spot_range = np.linspace(lower_bound, upper_bound, 80)
        
    # --- GRAPH 1: TIME ANALYSIS ---
    with st.container():
        st.markdown('<div class="simulation-box">', unsafe_allow_html=True)
        col_g1, col_c1 = st.columns([5, 1], gap="medium")
        with col_c1:
            st.markdown("**⏱️ Time Analysis**")
            num_slices = st.number_input("Time Lines", 1, 10, 5)
            comp_mode_time = st.radio("Mode:", ["Separate", "Diff"], key="mode_time")
            if st.session_state['mode'] == "Standard (Days)":
                st.info("Lines = Days passing")
            else:
                st.info("Lines = Hours remaining today")
            
        with col_g1:
            fig_time = go.Figure()
            time_fractions = np.linspace(0, 1, num_slices)
            blues = get_color_gradient('#87CEFA', '#000080', num_slices)
            reds = get_color_gradient('#FFA07A', '#8B0000', num_slices)
            greens = get_color_gradient('#90EE90', '#006400', num_slices)
            
            for i, frac in enumerate(time_fractions):
                # Logic split based on mode
                if st.session_state['mode'] == "Standard (Days)":
                    total_days = st.session_state['days_to_expiry_val']
                    denom = float(st.session_state.get('annual_days', 365))
                    t_new = (total_days * (1 - frac)) / denom
                    if t_new < 0.00001: t_new = 0.00001
                    d_pass = frac * total_days
                    lbl = f"{d_pass:.1f}d" if frac > 0 else "Now"
                
                else: # Intraday
                    dt_now = datetime.combine(date.today(), st.session_state['current_time'])
                    dt_close = datetime.combine(date.today(), st.session_state['close_time'])
                    if dt_now >= dt_close: mins_total = 0
                    else: mins_total = (dt_close - dt_now).total_seconds() / 60.0
                    
                    mins_remaining = mins_total * (1 - frac)
                    
                    gap_hours = parse_gap_string(st.session_state['gap_str'])
                    t_hours = (mins_remaining / 60.0) + gap_hours
                    annual_hours = float(st.session_state.get('annual_days', 365)) * 24.0
                    t_new = t_hours / annual_hours
                    
                    if frac == 0: lbl = "Now"
                    elif frac == 1: lbl = "Close"
                    else: 
                        mins_passed = mins_total * frac
                        future_dt = dt_now + timedelta(minutes=mins_passed)
                        lbl = future_dt.strftime("%H:%M")

                width = 3 if (frac==0 or frac==1) else 1.5
                dash = 'solid' if (frac==0 or frac==1) else 'dot'
                
                pnl_a = np.array([logic.calculate_portfolio_pnl(df_a, s, t_new, r, vol, multiplier, False) for s in spot_range]) if not df_a.empty else np.zeros_like(spot_range)
                pnl_b = np.array([logic.calculate_portfolio_pnl(df_b, s, t_new, r, vol, multiplier, False) for s in spot_range]) if not df_b.empty else np.zeros_like(spot_range)
                
                if comp_mode_time == "Separate":
                    if not df_a.empty: fig_time.add_trace(go.Scatter(x=spot_range, y=pnl_a, mode='lines', name=f"A: {lbl}", line=dict(color=blues[i], width=width, dash=dash), hovertemplate=f"<b>A: {lbl}</b><br>Spot: %{{x:,.0f}}<br>P&L: %{{y:,.0f}}<extra></extra>"))
                    if not df_b.empty: fig_time.add_trace(go.Scatter(x=spot_range, y=pnl_b, mode='lines', name=f"B: {lbl}", line=dict(color=reds[i], width=width, dash=dash), hovertemplate=f"<b>B: {lbl}</b><br>Spot: %{{x:,.0f}}<br>P&L: %{{y:,.0f}}<extra></extra>"))
                else:
                    fig_time.add_trace(go.Scatter(x=spot_range, y=pnl_a-pnl_b, mode='lines', name=f"Diff: {lbl}", line=dict(color=greens[i], width=width, dash=dash), hovertemplate=f"<b>Diff: {lbl}</b><br>Spot: %{{x:,.0f}}<br>Diff: %{{y:,.0f}}<extra></extra>"))

            fig_time.add_vline(x=calculation_spot, line_dash="dash", line_color="gray")
            fig_time.add_hline(y=0, line_color="black")
            fig_time.update_layout(title="PnL vs Time Decay", margin=dict(l=10, r=10, t=30, b=10), height=350, hovermode="closest", hoverlabel=dict(bgcolor="rgba(255,255,255,0)", bordercolor="rgba(255,255,255,0)"))
            st.plotly_chart(fig_time, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- GRAPH 2: IV SCENARIO ANALYSIS ---
    with st.container():
        st.markdown('<div class="simulation-box">', unsafe_allow_html=True)
        col_g2, col_c2 = st.columns([5, 1], gap="medium")
        with col_c2:
            st.markdown("**⚡ IV Analysis**")
            # Dynamic Slider based on Mode
            if st.session_state['mode'] == "Standard (Days)":
                sim_step = st.slider("Sim Day", 0, st.session_state['days_to_expiry_val'], 0)
                denom = float(st.session_state.get('annual_days', 365))
                t_sim = (st.session_state['days_to_expiry_val'] - sim_step) / denom
            else:
                # Intraday: Slider represents % of trading day passed
                sim_step_pct = st.slider("Day Progress %", 0, 100, 0)
                
                dt_now = datetime.combine(date.today(), st.session_state['current_time'])
                dt_close = datetime.combine(date.today(), st.session_state['close_time'])
                if dt_now >= dt_close: mins_total = 0
                else: mins_total = (dt_close - dt_now).total_seconds() / 60.0
                
                mins_remaining = mins_total * (1 - (sim_step_pct/100.0))
                
                gap_hours = parse_gap_string(st.session_state['gap_str'])
                t_hours = (mins_remaining / 60.0) + gap_hours
                annual_hours = float(st.session_state.get('annual_days', 365)) * 24.0
                t_sim = t_hours / annual_hours

            min_iv_u = st.number_input("Min IV", value=8.0, step=1.0)
            max_iv_u = st.number_input("Max IV", value=40.0, step=1.0)
            iv_n = st.number_input("IV Lines", 8, 30, 10)
            comp_mode_iv = st.radio("Mode:", ["Separate", "Diff"], key="mode_iv")
            st.info("Lines = Different IV levels")

        with col_g2:
            fig_iv = go.Figure()
            if t_sim < 0.00001: t_sim = 0.00001
            
            iv_levels = np.linspace(min_iv_u/100.0, max_iv_u/100.0, iv_n)
            blues_iv = get_color_gradient('#ADD8E6', '#00008B', iv_n) 
            reds_iv = get_color_gradient('#FFA07A', '#8B0000', iv_n)
            greens_iv = get_color_gradient('#90EE90', '#006400', iv_n)
            
            for i, sim_vol in enumerate(iv_levels):
                width = 1.5
                dash = 'dash'
                # Use Explicit PnL function for IV Graph
                pnl_a_iv = np.array([calculate_explicit_pnl(df_a, s, t_sim, r, sim_vol, multiplier) for s in spot_range]) if not df_a.empty else np.zeros_like(spot_range)
                pnl_b_iv = np.array([calculate_explicit_pnl(df_b, s, t_sim, r, sim_vol, multiplier) for s in spot_range]) if not df_b.empty else np.zeros_like(spot_range)
                lbl_vol = f"IV {sim_vol*100:.1f}%"
                
                if comp_mode_iv == "Separate":
                    if not df_a.empty: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_a_iv, mode='lines', name=f"A: {lbl_vol}", line=dict(color=blues_iv[i], width=width, dash=dash), hovertemplate=f"<b>A: {lbl_vol}</b><br>Spot: %{{x:,.0f}}<br>P&L: %{{y:,.0f}}<extra></extra>"))
                    if not df_b.empty: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_b_iv, mode='lines', name=f"B: {lbl_vol}", line=dict(color=reds_iv[i], width=width, dash=dash), hovertemplate=f"<b>B: {lbl_vol}</b><br>Spot: %{{x:,.0f}}<br>P&L: %{{y:,.0f}}<extra></extra>"))
                else:
                    fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_a_iv-pnl_b_iv, mode='lines', name=f"Diff: {lbl_vol}", line=dict(color=greens_iv[i], width=width, dash=dash), hovertemplate=f"<b>Diff: {lbl_vol}</b><br>Spot: %{{x:,.0f}}<br>Diff: %{{y:,.0f}}<extra></extra>"))

            # Current Market IV (Solid) - Using standard func or explicit? Let's use explicit for consistency in this graph
            pnl_a_curr = np.array([calculate_explicit_pnl(df_a, s, t_sim, r, vol, multiplier) for s in spot_range]) if not df_a.empty else np.zeros_like(spot_range)
            pnl_b_curr = np.array([calculate_explicit_pnl(df_b, s, t_sim, r, vol, multiplier) for s in spot_range]) if not df_b.empty else np.zeros_like(spot_range)
            
            if comp_mode_iv == "Separate":
                if not df_a.empty: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_a_curr, mode='lines', name=f"A: Market ({vol*100:.1f}%)", line=dict(color='blue', width=3, dash='solid'), hovertemplate=f"<b>A: Market</b><br>Spot: %{{x:,.0f}}<br>P&L: %{{y:,.0f}}<extra></extra>"))
                if not df_b.empty: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_b_curr, mode='lines', name=f"B: Market ({vol*100:.1f}%)", line=dict(color='red', width=3, dash='solid'), hovertemplate=f"<b>B: Market</b><br>Spot: %{{x:,.0f}}<br>P&L: %{{y:,.0f}}<extra></extra>"))
            else:
                fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_a_curr-pnl_b_curr, mode='lines', name=f"Diff: Market", line=dict(color='green', width=3, dash='solid'), hovertemplate=f"<b>Diff: Market</b><br>Spot: %{{x:,.0f}}<br>Diff: %{{y:,.0f}}<extra></extra>"))

            fig_iv.add_vline(x=calculation_spot, line_dash="dash", line_color="gray")
            fig_iv.add_hline(y=0, line_color="black")
            fig_iv.update_layout(title=f"PnL vs IV Sensitivity", margin=dict(l=10, r=10, t=30, b=10), height=350, hovermode="closest", hoverlabel=dict(bgcolor="rgba(255,255,255,0)", bordercolor="rgba(255,255,255,0)"))
            st.plotly_chart(fig_iv, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- GRAPH 3: 3D SURFACE ---
    with st.container():
        col_3d_title, col_3d_sel = st.columns([2, 1])
        with col_3d_title: st.subheader("🎲 3D Surface")
        with col_3d_sel: 
            surface_type = st.radio("Axis:", ["Spot vs Time", "Spot vs Volatility"], horizontal=True)
            view_mode = st.radio("3D Mode:", ["Diff (A - B)", "Portfolio A", "Portfolio B"], horizontal=True)

        if surface_type == "Spot vs Time":
            y_data = np.linspace(0, st.session_state['days_to_expiry_val'], 25)
            y_title = 'Days Passed'
            y_fmt = '.1f'
            tick_fmt = None
        else:
            y_data = np.linspace(vol * 0.5, vol * 1.5, 25)
            y_title = 'Volatility'
            y_fmt = '.1%' # Hover format
            tick_fmt = '.0%' # Axis tick format

        X, Y = np.meshgrid(spot_range, y_data)
        Z = np.zeros_like(X)
        colorscale = 'RdYlGn'
        z_title = "Diff"
        chart_title = "Advantage A vs B"
        if "Portfolio A" in view_mode: colorscale, z_title, chart_title = 'RdBu', "P&L A", "Portfolio A"
        elif "Portfolio B" in view_mode: colorscale, z_title, chart_title = 'RdBu', "P&L B", "Portfolio B"

        # 3D Calculation Loop - Robust
        denom_3d = float(st.session_state.get('annual_days', 365))
        
        for i in range(len(y_data)):
            if surface_type == "Spot vs Time":
                d_passed = y_data[i]
                v_calc = vol
                if st.session_state['mode'] == "Standard (Days)":
                    t_new = (st.session_state['days_to_expiry_val'] - d_passed) / denom_3d
                else:
                    t_new = ((24 - d_passed) / 24.0) / denom_3d
            else:
                v_calc = y_data[i]
                t_new = T

            if t_new < 0.00001: t_new = 0.00001
            
            for j in range(len(spot_range)):
                s_new = spot_range[j]
                val_a = logic.calculate_portfolio_pnl(df_a, s_new, t_new, r, v_calc, multiplier, False)
                val_b = logic.calculate_portfolio_pnl(df_b, s_new, t_new, r, v_calc, multiplier, False)
                
                res = 0
                if "Diff" in view_mode: res = val_a - val_b
                elif "Portfolio A" in view_mode: res = val_a
                elif "Portfolio B" in view_mode: res = val_b
                
                if np.isnan(res): res = 0
                Z[i, j] = res

        fig_3d = go.Figure(data=[go.Surface(z=Z, x=spot_range, y=y_data, colorscale=colorscale, cmid=0, opacity=0.9, hovertemplate=f"Spot: %{{x:,.0f}}<br>{y_title}: %{{y:{y_fmt}}}<br>{z_title}: %{{z:,.0f}}<extra></extra>", contours_z=dict(show=False), contours_x=dict(highlight=False), contours_y=dict(highlight=False), showscale=True, colorbar=dict(title="PnL"))])
        
        # Dynamic Axis Formatting
        yaxis_dict = dict(showgrid=True, title=y_title)
        if tick_fmt:
            yaxis_dict['tickformat'] = tick_fmt
            
        fig_3d.update_layout(title=chart_title, scene=dict(xaxis_title='Spot', yaxis_title=y_title, zaxis_title='P&L', xaxis=dict(showgrid=True), yaxis=yaxis_dict, zaxis=dict(showgrid=True)), margin=dict(l=0, r=0, b=0, t=30), height=400, hovermode="closest", hoverlabel=dict(bgcolor="rgba(255,255,255,0)", bordercolor="rgba(255,255,255,0)"))
        st.plotly_chart(fig_3d, use_container_width=True)