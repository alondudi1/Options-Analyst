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
import maof_risk as risk

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

    .risk-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 10px;
    }
    
    .monitor-box {
        background-color: #e8f4f8;
        border: 1px solid #bce0fd;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
        font-size: 0.9em;
        color: #0f5132;
    }
    
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
    
    [data-testid="stMetricValue"] { font-size: 1.2rem; }
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

# --- Gap Parsing Logic (RESTORED) ---
def parse_gap_string(gap_str):
    try:
        parts = gap_str.split(':')
        if len(parts) == 3:
            return (int(parts[0]) * 24.0) + int(parts[1]) + (int(parts[2]) / 60.0)
        elif len(parts) == 2: 
            return int(parts[0]) + (int(parts[1]) / 60.0)
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

# --- PnL Explicit Calculation ---
def calculate_explicit_pnl(df, spot, t, r, vol, mult):
    """
    PnL = (Theoretical_Value_at_Simulated_State) - (Table_Option_Price_Cost)
    """
    total_pnl = 0.0
    if df.empty: return 0.0
    
    for _, row in df.iterrows():
        try:
            raw_type = str(row['Type']).strip()
            op_type = raw_type.lower()
            
            p, _, _, _, _ = logic.bs_calc_raw(spot, float(row['Strike']), t, r, vol, op_type)
            if np.isnan(p): p = 0
            sim_val_shekels = p * mult
            
            entry_cost_shekels = float(row['Option Price']) 
            
            qty = float(row['Qty'])
            leg_pnl = (sim_val_shekels - entry_cost_shekels) * qty
            total_pnl += leg_pnl
        except: 
            pass
            
    return total_pnl

# --- Session State Defaults ---
DEFAULT_SPOT = 3700.0
DEFAULT_MULT = 50

if 'spot_price_val' not in st.session_state: st.session_state['spot_price_val'] = DEFAULT_SPOT
if 'mode' not in st.session_state: st.session_state['mode'] = "Standard (Days)"
if 'annual_days' not in st.session_state: st.session_state['annual_days'] = 365 
if 'expiry_date_val' not in st.session_state: st.session_state['expiry_date_val'] = get_default_expiry()
if 'days_to_expiry_val' not in st.session_state:
    delta = st.session_state['expiry_date_val'] - date.today()
    st.session_state['days_to_expiry_val'] = max(0, delta.days)
if 'vol_input' not in st.session_state: st.session_state['vol_input'] = 14.0
if 'rate_input' not in st.session_state: st.session_state['rate_input'] = 4.25
if 'current_time' not in st.session_state: st.session_state['current_time'] = time(10, 0)
if 'close_time' not in st.session_state: st.session_state['close_time'] = time(17, 40)
if 'gap_str' not in st.session_state: st.session_state['gap_str'] = "00:16:20"

if 'calc_d1' not in st.session_state: st.session_state['calc_d1'] = date.today()
if 'calc_t1' not in st.session_state: st.session_state['calc_t1'] = time(17, 40)
if 'calc_d2' not in st.session_state: st.session_state['calc_d2'] = date.today() + timedelta(days=1)
if 'calc_t2' not in st.session_state: st.session_state['calc_t2'] = time(10, 0)

if 'portfolio_a' not in st.session_state: st.session_state['portfolio_a'] = pd.DataFrame(columns=["Type", "Strike", "Qty", "Option Price"])
if 'portfolio_b' not in st.session_state: st.session_state['portfolio_b'] = pd.DataFrame(columns=["Type", "Strike", "Qty", "Option Price"])

# Revert Migration
for k in ['portfolio_a', 'portfolio_b']:
    if 'Entry Price' in st.session_state[k].columns:
        st.session_state[k].rename(columns={'Entry Price': 'Option Price'}, inplace=True)

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

# --- Layout ---
c_title, c_mode = st.columns([3, 1])
with c_title: st.title('DOR - Derivatives Operation Room')
with c_mode:
    st.markdown("<br>", unsafe_allow_html=True)
    st.radio("Simulation Mode", ["Standard (Days)", "Intraday (0DTE)"], horizontal=True, label_visibility="collapsed", key='mode_radio', on_change=on_mode_change)

st.session_state['mode'] = st.session_state['mode_radio']

cols = st.columns([1, 1.2, 1, 1, 1, 3], gap="small") 
with cols[0]:
    st.markdown("##### 📍 Spot")
    ui_spot = st.number_input("Spot", key='spot_price_val', step=1.0, format="%.2f", label_visibility="collapsed")

with cols[1]:
    if st.session_state['mode'] == "Standard (Days)":
        st.markdown("##### ⏳ Expiry")
        st.date_input("Date", key='expiry_date_val', min_value=date.today(), on_change=on_date_change, label_visibility="collapsed")
        st.number_input("Days", key='days_to_expiry_val', min_value=0, step=1, on_change=on_days_change, label_visibility="collapsed")
        T_calc = st.session_state['days_to_expiry_val'] / float(st.session_state.get('annual_days', 365))
        total_hours = st.session_state['days_to_expiry_val'] * 24.0 
    else:
        # --- INTRADAY ---
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
        
        # Intraday Calc
        gap_hours = parse_gap_string(st.session_state['gap_str'])
        dt_now = datetime.combine(date.today(), t_now)
        dt_close = datetime.combine(date.today(), t_close)
        if dt_now > dt_close: minutes_remaining = 0
        else: minutes_remaining = (dt_close - dt_now).total_seconds() / 60.0
        total_hours = (minutes_remaining / 60.0) + gap_hours
        annual_hours = float(st.session_state.get('annual_days', 365)) * 24.0
        T_calc = total_hours / annual_hours

with cols[2]:
    st.markdown("##### 📊 Market")
    st.number_input("IV (%)", step=0.5, key='vol_input')
    st.number_input("Rate (%)", step=0.1, key='rate_input')
with cols[3]:
    st.markdown("##### 📐 Model")
    st.selectbox("Days/Year", [365, 252], key='annual_days', label_visibility="collapsed")
with cols[4]:
    st.markdown("##### ⚙️ Contract")
    multiplier = st.number_input("Mult", value=DEFAULT_MULT, step=10)
    strike_interval = st.number_input("Interval", value=10, step=5)
    num_strikes = st.number_input("Strikes", value=20, step=2)

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
        except: chain_rows.append({'Strike': int(K), 'Call_Price': 0, 'Put_Price': 0})
    df_chain = pd.DataFrame(chain_rows)
    gb = GridOptionsBuilder.from_dataframe(df_chain)
    gb.configure_default_column(resizable=True, filterable=False, sortable=False, suppressMenu=True, headerClass='center-header')
    if not df_chain.empty:
        for col in ['C_Vega', 'C_Theta', 'C_Gamma', 'C_Delta', 'Call_Price']: 
            if col in df_chain.columns: gb.configure_column(col, width=90, cellStyle={'background-color': '#e6f2ff', 'text-align': 'center'})
        for col in ['Put_Price', 'P_Delta', 'P_Gamma', 'P_Theta', 'P_Vega']: 
            if col in df_chain.columns: gb.configure_column(col, width=90, cellStyle={'background-color': '#ffe6e6', 'text-align': 'center'})
        if "Strike" in df_chain.columns: gb.configure_column("Strike", pinned="right", width=100, cellStyle={'background-color': '#e0e0e0', 'font-weight': 'bold', 'text-align': 'center'})
    gridOptions = gb.build()
    gridOptions['rowHeight'] = 30
    gridOptions['headerHeight'] = 35
    gridOptions['enableRtl'] = False 
    AgGrid(df_chain, gridOptions=gridOptions, height=300, theme='balham', key='chain_grid_main')

# --- 2. STRATEGY WIZARD (LAYOUT FIXED) ---
st.divider()
with st.expander("🪄 Strategy Wizard", expanded=True):
    c_tgt, _ = st.columns([1, 4])
    with c_tgt: target_portfolio = st.radio("Target:", ["A", "B"], horizontal=True)
    
    def render_cell(container, strat_list, key_suffix):
        with container:
            st.markdown(f"<div class='strategy-card'>", unsafe_allow_html=True)
            sel = st.selectbox("", strat_list, key=f"sel_{key_suffix}", label_visibility="collapsed")
            if st.button("Load", key=f"btn_{key_suffix}", use_container_width=True):
                legs = strategies.generate_strategy_legs(sel, calculation_spot, strike_interval)
                rows = []
                for leg in legs:
                    op_type_safe = str(leg['Type']).lower()
                    p, _, _, _, _ = logic.bs_calc_raw(calculation_spot, float(leg['Strike']), T, r, vol, op_type_safe)
                    if np.isnan(p): p = 0
                    price_shekels = int(p * multiplier)
                    rows.append({
                        "Type": leg['Type'], 
                        "Strike": int(leg['Strike']), 
                        "Qty": int(leg['Qty']), 
                        "Option Price": price_shekels 
                    })
                new_df = pd.DataFrame(rows)
                target_key = "portfolio_a" if target_portfolio == "A" else "portfolio_b"
                refresh_key = f"refresh_key_{target_portfolio}"
                st.session_state[target_key] = new_df
                if refresh_key not in st.session_state: st.session_state[refresh_key] = 0
                st.session_state[refresh_key] += 1
                st.toast(f"Loaded '{sel}'", icon="🪄")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # --- ROW 1 ---
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
    
    st.markdown("") 

    # --- ROW 2 ---
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
    
    st.markdown("") 

    # --- ROW 3 ---
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

js_total_cost_calc = JsCode("""function(params) {if (params.data.Qty && params.data['Option Price']) {return params.data.Qty * params.data['Option Price'];}return 0;}""")
def render_portfolio_editor(key, df_key, color_hex):
    if f"refresh_key_{key}" not in st.session_state: st.session_state[f"refresh_key_{key}"] = 0
    if 'Option Price' not in st.session_state[df_key].columns:
         st.session_state[df_key]['Option Price'] = 0
         
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
    
    if calc_btn:
        df = st.session_state[df_key]
        if not df.empty:
            for index, row in df.iterrows():
                try:
                    op_type = str(row['Type']).lower()
                    p, _, _, _, _ = logic.bs_calc_raw(calculation_spot, float(row['Strike']), T, r, vol, op_type)
                    df.at[index, 'Option Price'] = int(p * multiplier)
                except: pass
            st.session_state[df_key] = df
            st.session_state[f"refresh_key_{key}"] += 1
            st.toast(f"Updated prices to current BS", icon="🧮")
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
    grid_opts['enableRtl'] = False; grid_opts['rowHeight'] = 35; grid_opts['headerHeight'] = 35
    response = AgGrid(display_df, gridOptions=grid_opts, update_mode=GridUpdateMode.MODEL_CHANGED, height=300, theme='balham', key=dynamic_key, fit_columns_on_grid_load=True, allow_unsafe_jscode=True)
    
    res_df = response['data']
    if not res_df.empty:
        res_df['Strike'] = res_df['Strike'].astype(int)
        res_df['Qty'] = res_df['Qty'].astype(int)
        res_df['Option Price'] = res_df['Option Price'].astype(int)
        save_df = res_df.drop(columns=['Total Cost']) if 'Total Cost' in res_df.columns else res_df
        st.session_state[df_key] = save_df
    
    total_cost = (res_df['Qty'] * res_df['Option Price']).sum() if not res_df.empty else 0
    st.metric(f"Total Cost {key}", f"{total_cost:,.0f}")
    return res_df

col_a, col_b = st.columns(2)
with col_a: df_a = render_portfolio_editor("A", "portfolio_a", "#e6f2ff")
with col_b: df_b = render_portfolio_editor("B", "portfolio_b", "#ffe6e6")

df_a = st.session_state['portfolio_a']
df_b = st.session_state['portfolio_b']

if not df_a.empty or not df_b.empty:
    st.divider()
    st.subheader("⚖️ Risk Summary")
    # Greeks calcs
    greeks_a = logic.calculate_portfolio_greeks(df_a, calculation_spot, T, r, vol, multiplier)
    greeks_b = logic.calculate_portfolio_greeks(df_b, calculation_spot, T, r, vol, multiplier)
    def fmt_curr(val): return "INF" if val == float('inf') else "-INF" if val == float('-inf') else f"{val:,.0f}"
    df_risk = pd.DataFrame({
        'Metric': ['Total Cost (Exposure)', 'Total P&L (Current)', 'Max Profit', 'Max Loss', 'Delta', 'Gamma', 'Theta', 'Vega'],
        'Port_A': [fmt_curr(greeks_a['Cost']), fmt_curr(greeks_a['PnL']), fmt_curr(greeks_a['MaxProfit']), fmt_curr(greeks_a['MaxLoss']), f"{greeks_a['Delta']:,.0f}", f"{greeks_a['Gamma']:,.2f}", fmt_curr(greeks_a['Theta']), fmt_curr(greeks_a['Vega'])],
        'Port_B': [fmt_curr(greeks_b['Cost']), fmt_curr(greeks_b['PnL']), fmt_curr(greeks_b['MaxProfit']), fmt_curr(greeks_b['MaxLoss']), f"{greeks_b['Delta']:,.0f}", f"{greeks_b['Gamma']:,.2f}", fmt_curr(greeks_b['Theta']), fmt_curr(greeks_b['Vega'])]
    })
    gb_risk = GridOptionsBuilder.from_dataframe(df_risk)
    gb_risk.configure_default_column(resizable=False, filterable=False, sortable=False, suppressMenu=True, headerClass='center-header')
    gb_risk.configure_column("Metric", headerName="Metric", width=180, cellStyle={'font-weight': 'bold', 'text-align': 'left', 'background-color': '#f9f9f9'})
    gb_risk.configure_column("Port_A", headerName="🔵 Portfolio A", width=150, cellStyle={'background-color': '#e6f2ff', 'text-align': 'center'})
    gb_risk.configure_column("Port_B", headerName="🔴 Portfolio B", width=150, cellStyle={'background-color': '#ffe6e6', 'text-align': 'center'})
    gridOptions_risk = gb_risk.build()
    gridOptions_risk['enableRtl'] = False 
    AgGrid(df_risk, gridOptions=gridOptions_risk, height=300, fit_columns_on_grid_load=True, allow_unsafe_jscode=True, theme='balham', key=str(uuid.uuid4()))
    
    st.divider()
    col_main_controls, _ = st.columns([1, 2])
    with col_main_controls:
        st.markdown("##### ⚙️ Graph Settings")
        chart_range_pct = st.number_input("Zoom (+/-%)", min_value=0.5, max_value=15.0, value=5.0, step=0.5, format="%.1f")
        lower_bound = calculation_spot * (1 - chart_range_pct / 100)
        upper_bound = calculation_spot * (1 + chart_range_pct / 100)
        spot_range = np.linspace(lower_bound, upper_bound, 80)
        
    # --- GRAPH 1: TIME ---
    with st.container():
        st.markdown('<div class="simulation-box">', unsafe_allow_html=True)
        col_g1, col_c1 = st.columns([5, 1], gap="medium")
        with col_c1:
            st.markdown("**⏱️ Time Analysis**")
            num_slices = st.number_input("Time Lines", 1, 10, 5)
            # Slider capped at 100% per user request
            sim_vol_time = st.slider("Simulate IV (%)", min_value=5.0, max_value=100.0, value=min(100.0, vol*100), step=1.0, help="Simulate IV changes") / 100.0
            comp_mode_time = st.radio("Mode:", ["Separate", "Diff"], key="mode_time")
        with col_g1:
            fig_time = go.Figure()
            time_fractions = np.linspace(0, 1, num_slices)
            blues = get_color_gradient('#87CEFA', '#000080', num_slices)
            reds = get_color_gradient('#FFA07A', '#8B0000', num_slices)
            greens = get_color_gradient('#90EE90', '#006400', num_slices)
            
            # Hover Template (Rich HTML)
            custom_hover = "<b>%{text}</b><br>Spot: %{x:,.0f}<br>PnL: %{y:,.0f}₪<extra></extra>"

            for i, frac in enumerate(time_fractions):
                denom = float(st.session_state.get('annual_days', 365))
                
                if st.session_state['mode'] == "Intraday (0DTE)":
                    dt_current = datetime.combine(date.today(), st.session_state['current_time'])
                    dt_end = datetime.combine(date.today(), st.session_state['close_time'])
                    
                    if dt_current < dt_end:
                        total_mins_market = (dt_end - dt_current).total_seconds() / 60
                        mins_passed = total_mins_market * frac
                        curr_time_step = dt_current + timedelta(minutes=mins_passed)
                        lbl = curr_time_step.strftime("%H:%M")
                    else:
                        lbl = f"{frac*100:.0f}% Done"
                    
                    t_new = T * (1-frac)
                else:
                    t_new = (st.session_state['days_to_expiry_val'] * (1 - frac)) / denom
                    lbl = f"{frac*st.session_state['days_to_expiry_val']:.1f}d passed"

                if t_new < 0.00001: t_new = 0.00001
                
                width = 3 if (frac==0 or frac==1) else 1.5
                dash = 'solid' if (frac==0 or frac==1) else 'dot'
                pnl_a = np.array([calculate_explicit_pnl(df_a, s, t_new, r, sim_vol_time, multiplier) for s in spot_range]) if not df_a.empty else np.zeros_like(spot_range)
                pnl_b = np.array([calculate_explicit_pnl(df_b, s, t_new, r, sim_vol_time, multiplier) for s in spot_range]) if not df_b.empty else np.zeros_like(spot_range)
                
                if comp_mode_time == "Separate":
                    if not df_a.empty: fig_time.add_trace(go.Scatter(x=spot_range, y=pnl_a, mode='lines', name=f"A: {lbl}", text=[f"A: {lbl}"]*len(spot_range), hovertemplate=custom_hover, line=dict(color=blues[i], width=width, dash=dash)))
                    if not df_b.empty: fig_time.add_trace(go.Scatter(x=spot_range, y=pnl_b, mode='lines', name=f"B: {lbl}", text=[f"B: {lbl}"]*len(spot_range), hovertemplate=custom_hover, line=dict(color=reds[i], width=width, dash=dash)))
                else: fig_time.add_trace(go.Scatter(x=spot_range, y=pnl_a-pnl_b, mode='lines', name=f"Diff: {lbl}", text=[f"Diff: {lbl}"]*len(spot_range), hovertemplate=custom_hover, line=dict(color=greens[i], width=width, dash=dash)))
            
            fig_time.add_vline(x=calculation_spot, line_dash="dash", line_color="gray")
            fig_time.add_hline(y=0, line_color="black")
            fig_time.update_layout(title="PnL vs Time Decay", margin=dict(l=10, r=10, t=30, b=10), height=350, hovermode="closest")
            st.plotly_chart(fig_time, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- GRAPH 2: IV ---
    with st.container():
        st.markdown('<div class="simulation-box">', unsafe_allow_html=True)
        col_g2, col_c2 = st.columns([5, 1], gap="medium")
        with col_c2:
            st.markdown("**⚡ IV Analysis**")
            min_iv_u = st.number_input("Min IV", value=8.0, step=1.0)
            max_iv_u = st.number_input("Max IV", value=40.0, step=1.0)
            iv_n = st.number_input("IV Lines", 8, 30, 10)
            sim_days_passed = st.slider("Days Passed", 0, max(1, int(st.session_state['days_to_expiry_val'])), 0, help="Simulate Time passage")
            comp_mode_iv = st.radio("Mode:", ["Separate", "Diff"], key="mode_iv")
            
            denom = float(st.session_state.get('annual_days', 365))
            if st.session_state['mode'] == "Standard (Days)":
                t_sim = max(0.00001, (st.session_state['days_to_expiry_val'] - sim_days_passed) / denom)
            else: 
                t_sim = T 

        with col_g2:
            fig_iv = go.Figure()
            iv_levels = np.linspace(min_iv_u/100.0, max_iv_u/100.0, iv_n)
            blues_iv = get_color_gradient('#ADD8E6', '#00008B', iv_n) 
            reds_iv = get_color_gradient('#FFA07A', '#8B0000', iv_n)
            greens_iv = get_color_gradient('#90EE90', '#006400', iv_n)
            
            custom_hover_iv = "<b>%{text}</b><br>Spot: %{x:,.0f}<br>PnL: %{y:,.0f}₪<extra></extra>"

            for i, sim_vol in enumerate(iv_levels):
                width = 1.5; dash = 'dash'
                pnl_a_iv = np.array([calculate_explicit_pnl(df_a, s, t_sim, r, sim_vol, multiplier) for s in spot_range]) if not df_a.empty else np.zeros_like(spot_range)
                pnl_b_iv = np.array([calculate_explicit_pnl(df_b, s, t_sim, r, sim_vol, multiplier) for s in spot_range]) if not df_b.empty else np.zeros_like(spot_range)
                lbl_vol = f"IV {sim_vol*100:.1f}%"
                if comp_mode_iv == "Separate":
                    if not df_a.empty: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_a_iv, mode='lines', name=f"A: {lbl_vol}", text=[f"A: {lbl_vol}"]*len(spot_range), hovertemplate=custom_hover_iv, line=dict(color=blues_iv[i], width=width, dash=dash)))
                    if not df_b.empty: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_b_iv, mode='lines', name=f"B: {lbl_vol}", text=[f"B: {lbl_vol}"]*len(spot_range), hovertemplate=custom_hover_iv, line=dict(color=reds[i], width=width, dash=dash)))
                else: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_a_iv-pnl_b_iv, mode='lines', name=f"Diff: {lbl_vol}", text=[f"Diff: {lbl_vol}"]*len(spot_range), hovertemplate=custom_hover_iv, line=dict(color=greens_iv[i], width=width, dash=dash)))
            
            pnl_a_curr = np.array([calculate_explicit_pnl(df_a, s, t_sim, r, vol, multiplier) for s in spot_range]) if not df_a.empty else np.zeros_like(spot_range)
            pnl_b_curr = np.array([calculate_explicit_pnl(df_b, s, t_sim, r, vol, multiplier) for s in spot_range]) if not df_b.empty else np.zeros_like(spot_range)
            
            if comp_mode_iv == "Separate":
                if not df_a.empty: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_a_curr, mode='lines', name=f"A: Market", text=["A: Market"]*len(spot_range), hovertemplate=custom_hover_iv, line=dict(color='blue', width=3, dash='solid')))
                if not df_b.empty: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_b_curr, mode='lines', name=f"B: Market", text=["B: Market"]*len(spot_range), hovertemplate=custom_hover_iv, line=dict(color='red', width=3, dash='solid')))
            else: fig_iv.add_trace(go.Scatter(x=spot_range, y=pnl_a_curr-pnl_b_curr, mode='lines', name=f"Diff: Market", text=["Diff: Market"]*len(spot_range), hovertemplate=custom_hover_iv, line=dict(color='green', width=3, dash='solid')))
            
            fig_iv.add_vline(x=calculation_spot, line_dash="dash", line_color="gray")
            fig_iv.add_hline(y=0, line_color="black")
            fig_iv.update_layout(title=f"PnL vs IV Sensitivity (Simulated T-{sim_days_passed}d)", margin=dict(l=10, r=10, t=30, b=10), height=350, hovermode="closest")
            st.plotly_chart(fig_iv, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 3D Surface
    with st.container():
        col_3d_title, col_3d_sel = st.columns([2, 1])
        with col_3d_title: st.subheader("🎲 3D Surface")
        with col_3d_sel: 
            surface_type = st.radio("Axis:", ["Spot vs Time", "Spot vs Volatility"], horizontal=True)
            view_mode = st.radio("3D Mode:", ["Diff (A - B)", "Portfolio A", "Portfolio B"], horizontal=True)
        
        # 3D Logic Adjustment for Intraday
        if surface_type == "Spot vs Time":
            if st.session_state['mode'] == "Intraday (0DTE)":
                # Show HOURS on axis (0 to Total Hours)
                y_data = np.linspace(0, total_hours, 25) 
                y_title = 'Time Passed (Hours)'
                y_fmt = '.1f'
            else:
                y_data = np.linspace(0, st.session_state['days_to_expiry_val'], 25)
                y_title = 'Time Passed (Days)'
                y_fmt = '.1f'
            tick_fmt = None
        else:
            y_data = np.linspace(vol * 0.5, vol * 1.5, 25); y_title = 'Volatility'; y_fmt = '.1%'; tick_fmt = '.0%'
        
        X, Y = np.meshgrid(spot_range, y_data); Z = np.zeros_like(X)
        colorscale = 'RdYlGn'; z_title = "Diff"; chart_title = "Advantage A vs B"
        if "Portfolio A" in view_mode: colorscale='RdBu'; z_title="P&L A"; chart_title="Portfolio A"
        elif "Portfolio B" in view_mode: colorscale='RdBu'; z_title="P&L B"; chart_title="Portfolio B"
        denom_3d = float(st.session_state.get('annual_days', 365))
        
        for i in range(len(y_data)):
            if surface_type == "Spot vs Time":
                # Calc logic: T_new goes from Full Time -> 0 as Y goes 0 -> Max
                if st.session_state['mode'] == "Intraday (0DTE)":
                    h_passed = y_data[i]
                    # Calculate remaining portion
                    pct_left = 1.0 - (h_passed / total_hours)
                    if pct_left < 0: pct_left = 0
                    t_new = T * pct_left
                    v_calc = vol
                else:
                    d_passed = y_data[i]
                    v_calc = vol
                    t_new = (st.session_state['days_to_expiry_val'] - d_passed) / denom_3d
            else: v_calc = y_data[i]; t_new = T
            
            if t_new < 0.00001: t_new = 0.00001
            for j in range(len(spot_range)):
                s_new = spot_range[j]
                val_a = calculate_explicit_pnl(df_a, s_new, t_new, r, v_calc, multiplier)
                val_b = calculate_explicit_pnl(df_b, s_new, t_new, r, v_calc, multiplier)
                res = 0
                if "Diff" in view_mode: res = val_a - val_b
                elif "Portfolio A" in view_mode: res = val_a
                elif "Portfolio B" in view_mode: res = val_b
                if np.isnan(res): res = 0
                Z[i, j] = res
        fig_3d = go.Figure(data=[go.Surface(z=Z, x=spot_range, y=y_data, colorscale=colorscale, cmid=0, opacity=0.9, hovertemplate=f"Spot: %{{x:,.0f}}<br>{y_title}: %{{y:{y_fmt}}}<br>{z_title}: %{{z:,.0f}}<extra></extra>", contours_z=dict(show=False), contours_x=dict(highlight=False), contours_y=dict(highlight=False), showscale=True, colorbar=dict(title="PnL"))])
        yaxis_dict = dict(showgrid=True, title=y_title)
        if tick_fmt: yaxis_dict['tickformat'] = tick_fmt
        fig_3d.update_layout(title=chart_title, scene=dict(xaxis_title='Spot', yaxis_title=y_title, zaxis_title='P&L', xaxis=dict(showgrid=True), yaxis=yaxis_dict, zaxis=dict(showgrid=True)), margin=dict(l=0, r=0, b=0, t=30), height=400, hovermode="closest")
        st.plotly_chart(fig_3d, use_container_width=True)

    # ================= RISK LAB SECTION (VERSION 79.0 - NUMERIC AXES) =================
    st.divider()
    st.markdown("### 🔬 Risk Analysis Lab (A vs B)")
    
    annual_d = float(st.session_state.get('annual_days', 365))
    if st.session_state['mode'] == "Standard (Days)":
        time_str = f"{T * annual_d:.1f} Days"
    else:
        time_str = f"{T * annual_d * 24:.1f} Hours"

    # DEBUG MONITOR
    st.markdown(f"""
    <div class="monitor-box">
        <b>Engine Status:</b> Time: <b>{time_str}</b> (T={T:.5f}) | Spot={calculation_spot} | Vol={vol*100:.1f}%
    </div>
    """, unsafe_allow_html=True)
    
    # Risk Deck Controls
    risk_mode = st.radio("Analysis Mode:", ["🎲 Monte Carlo", "🔥 Stress Matrix", "📜 Historical"], horizontal=True, label_visibility="collapsed")
    
    # Check Data Availability
    has_a = not df_a.empty
    has_b = not df_b.empty
    
    if not has_a and not has_b:
        st.warning("⚠️ Both portfolios are empty. Please add positions.")
    else:
        # --- 1. MONTE CARLO (OVERLAY) ---
        if risk_mode == "🎲 Monte Carlo":
            with st.expander("🎓 Explanation: Monte Carlo Analysis & Risk Comparison", expanded=False):
                st.markdown("""
                **What are we seeing here?**
                We run 5,000 future simulations for each portfolio. The overlapping histograms show the "risk shape" of each strategy.
                
                **Key Metrics:**
                * **PoP (Prob of Profit):** In what % of simulations did the portfolio end positive? (Higher = Better probability).
                * **VaR 95% (Value at Risk):** The "Red Line". In 95% of cases, you won't lose more than this amount.
                * **CVaR (Tail Risk):** The "Black Hole". The average loss of the worst 5% scenarios (Total Collapse).
                * **Advantage:** The system highlights which portfolio is safer (Better VaR) and which has higher win probability.
                """)

            # Run Simulations
            sim_spots, pnls_a, stats_a = (None, None, None)
            sim_spots_b, pnls_b, stats_b = (None, None, None)
            
            if has_a:
                sim_spots, pnls_a, stats_a = risk.run_monte_carlo(df_a, calculation_spot, T, r, vol, multiplier, simulations=5000, annual_days=annual_d)
            if has_b:
                sim_spots_b, pnls_b, stats_b = risk.run_monte_carlo(df_b, calculation_spot, T, r, vol, multiplier, simulations=5000, annual_days=annual_d)
            
            # Metrics Comparison
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown("**Metric**")
            c1.markdown("Win Prob (PoP)")
            c1.markdown("VaR (95%)")
            c1.markdown("CVaR (Tail)")
            
            c2.markdown("**🔵 Portfolio A**")
            c2.markdown(f"{stats_a['PoP']*100:.1f}%" if has_a else "-")
            c2.markdown(f"{stats_a['VaR_95']:,.0f}" if has_a else "-")
            c2.markdown(f"{stats_a['CVaR_95']:,.0f}" if has_a else "-")
            
            c3.markdown("**🔴 Portfolio B**")
            c3.markdown(f"{stats_b['PoP']*100:.1f}%" if has_b else "-")
            c3.markdown(f"{stats_b['VaR_95']:,.0f}" if has_b else "-")
            c3.markdown(f"{stats_b['CVaR_95']:,.0f}" if has_b else "-")

            # Determine winner
            c4.markdown("**Advantage**")
            if has_a and has_b:
                pop_diff = stats_a['PoP'] - stats_b['PoP']
                var_diff = stats_a['VaR_95'] - stats_b['VaR_95'] 
                c4.markdown(f"{'🔵 A' if pop_diff > 0 else '🔴 B'} (+{abs(pop_diff)*100:.1f}%)")
                c4.markdown(f"{'🔵 A' if var_diff > 0 else '🔴 B'} ({abs(var_diff):,.0f})")
            else:
                c4.markdown("-")
                c4.markdown("-")

            # Overlay Graph
            fig_mc = go.Figure()
            if has_a:
                fig_mc.add_trace(go.Histogram(x=pnls_a, name='Port A', marker_color='#3366CC', opacity=0.6))
                fig_mc.add_vline(x=stats_a['VaR_95'], line_dash="dash", line_color="#3366CC", annotation_text="VaR A")
            if has_b:
                fig_mc.add_trace(go.Histogram(x=pnls_b, name='Port B', marker_color='#DC3912', opacity=0.6))
                fig_mc.add_vline(x=stats_b['VaR_95'], line_dash="dash", line_color="#DC3912", annotation_text="VaR B")

            fig_mc.update_layout(barmode='overlay', title="PnL Distribution Overlay", xaxis_title="PnL", height=350)
            st.plotly_chart(fig_mc, use_container_width=True)

        # --- 2. STRESS MATRIX (NUMERIC AXES FIX) ---
        elif risk_mode == "🔥 Stress Matrix":
            with st.expander("🎓 Explanation: Stress Matrix & Strategy Comparison", expanded=False):
                st.markdown("""
                **How to read the Heatmap?**
                This matrix tests what happens when two variables change simultaneously: Asset Price (Spot) and Volatility (IV).
                
                **View Modes:**
                * **Diff (A - B):** The most critical view.
                    * 🟦 **Blue/Green:** Portfolio A wins (Earned more or lost less than B).
                    * 🟥 **Red:** Portfolio B wins.
                * This allows you to instantly identify which portfolio is more resilient to crashes (Bottom-Left area) and which is better in a rising market.
                """)

            c_view, _ = st.columns([1, 2])
            with c_view:
                stress_view = st.radio("View:", ["Diff (A - B)", "Portfolio A", "Portfolio B"], horizontal=True)

            # Ensure valid ranges are always calculated
            s_rng, v_rng, mat_a = risk.calculate_stress_matrix(df_a, calculation_spot, vol, T, r, multiplier)
            _, _, mat_b = risk.calculate_stress_matrix(df_b, calculation_spot, vol, T, r, multiplier)
            
            # Prepare numeric axes (Percentage Change)
            x_pct = [(s / calculation_spot - 1) for s in s_rng]
            y_pct = [(v / vol - 1) for v in v_rng]
            
            # Decide what to show
            if stress_view == "Diff (A - B)":
                if not has_a or not has_b:
                    st.warning("Need both portfolios for Diff view.")
                    z_data = np.zeros_like(mat_a)
                else:
                    z_data = mat_a - mat_b
                colorscale = 'RdBu' # Blue = A wins, Red = B wins
                title = "Advantage Map (Blue = A wins, Red = B wins)"
            elif stress_view == "Portfolio A":
                z_data = mat_a
                colorscale = 'RdYlGn'
                title = "Portfolio A Stress Test"
            else:
                z_data = mat_b
                colorscale = 'RdYlGn'
                title = "Portfolio B Stress Test"
                
            fig_stress = go.Figure(data=go.Heatmap(
                z=z_data,
                x=x_pct, # Passing actual floats
                y=y_pct, # Passing actual floats
                colorscale=colorscale, zmid=0,
                hovertemplate="Spot: %{x:.1%}<br>IV: %{y:.0%}<br>Val: %{z:,.0f}<extra></extra>"
            ))
            
            # Force axes to display as percentages
            fig_stress.update_layout(
                title=title,
                xaxis=dict(title="Spot Change", tickformat=".0%"), 
                yaxis=dict(title="IV Change", tickformat=".0%"),
                height=400
            )
            st.plotly_chart(fig_stress, use_container_width=True)

        # --- 3. HISTORICAL SCENARIOS (GROUPED BAR) ---
        elif risk_mode == "📜 Historical":
            with st.expander("🎓 Explanation: Historical Stress Tests", expanded=False):
                st.markdown("""
                **Not a Time Machine, but a Crash Test.**
                We take your **current** portfolio (with its remaining time to expiry), and subject it to the same shock that the market experienced in famous crises.
                
                * **What does it check?** Is your portfolio fragile to different types of shocks (Flash Crash, Slow Bleed, Volatility Spike).
                * **Grouped Bars:** The side-by-side comparison lets you see which portfolio would have "survived" the 2008 Crisis or Corona better.
                """)

            scenarios = risk.SCENARIOS
            names = list(scenarios.keys())
            res_a = []
            res_b = []
            
            for name in names:
                val_a, _, _ = risk.run_historical_scenario(df_a, calculation_spot, vol, T, r, multiplier, name) if has_a else (0,0,0)
                val_b, _, _ = risk.run_historical_scenario(df_b, calculation_spot, vol, T, r, multiplier, name) if has_b else (0,0,0)
                res_a.append(val_a)
                res_b.append(val_b)
            
            fig_hist = go.Figure()
            if has_a:
                fig_hist.add_trace(go.Bar(
                    name='Port A', x=names, y=res_a, marker_color='#3366CC',
                    text=[f"{x:,.0f}" for x in res_a], textposition='outside', textfont=dict(color='black')
                ))
            if has_b:
                fig_hist.add_trace(go.Bar(
                    name='Port B', x=names, y=res_b, marker_color='#DC3912',
                    text=[f"{x:,.0f}" for x in res_b], textposition='outside', textfont=dict(color='black')
                ))
                
            # Dynamic Y-Axis Range Fix
            all_res = (res_a if has_a else []) + (res_b if has_b else [])
            if all_res:
                y_max = max(all_res); y_min = min(all_res)
                margin = 0.15
                fig_hist.update_layout(yaxis=dict(range=[y_min*(1+margin), y_max*(1+margin)]))

            fig_hist.update_layout(barmode='group', title="Historical Crisis Comparison", height=400)
            st.plotly_chart(fig_hist, use_container_width=True)
            
            # --- SCENARIO INSPECTOR (ENGLISH) ---
            st.markdown("#### 🔎 Scenario Inspector")
            selected_scenario = st.selectbox("Dive into Scenario:", names)
            
            if selected_scenario:
                s_data = scenarios[selected_scenario]
                
                # Show cards
                c_desc, c_params = st.columns([3, 1])
                with c_desc:
                    st.markdown(f"**Event:** {selected_scenario}")
                    st.caption(s_data['desc'])
                with c_params:
                    st.markdown("**Market Shock:**")
                    st.markdown(f"📉 Spot: `{s_data['spot_move_pct']*100:+.1f}%`")
                    st.markdown(f"⚡ Vol: `{s_data['iv_move_pct']*100:+.0f}%`")
                    if s_data.get('rate_move_pct', 0) != 0:
                        st.markdown(f"🏦 Rate: `{s_data['rate_move_pct']*100:+.0f}%`")

    st.markdown('</div>', unsafe_allow_html=True)