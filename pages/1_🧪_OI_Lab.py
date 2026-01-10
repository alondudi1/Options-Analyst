import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import re
import io
import textwrap
import hashlib

# ==========================================
# ⚙️ CONFIG & STYLES
# ==========================================
st.set_page_config(layout="wide", page_title="DOR OI Lab - Master Edition")

st.markdown("""
<style>
    .stApp { direction: rtl; }
    h1, h2, h3, p, div { text-align: right; }
    
    .filter-box {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
        border: 1px solid #dee2e6;
    }
    
    .tase-link {
        text-decoration: none;
        background-color: #007bff;
        color: white !important;
        padding: 8px 15px;
        border-radius: 5px;
        font-size: 0.9em;
        display: inline-block;
        margin-bottom: 10px;
        margin-left: 10px;
        transition: background-color 0.3s;
    }
    .tase-link:hover { background-color: #0056b3; }
    
    .tag-m { color: #856404; background-color: #fff3cd; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.8em; border: 1px solid #ffeeba; }
    .tag-w { color: #0c5460; background-color: #d1ecf1; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.8em; border: 1px solid #bee5eb; }
    
    .res-success { color: #155724; background-color: #d4edda; padding: 2px 5px; border-radius: 4px; font-weight: bold; }
    .res-fail { color: #721c24; background-color: #f8d7da; padding: 2px 5px; border-radius: 4px; font-weight: bold; }
    .res-neutral { color: #818182; background-color: #fefefe; padding: 2px 5px; border-radius: 4px; border: 1px solid #ddd;}

    /* מקרא */
    .legend-box {
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        font-family: sans-serif;
    }
    .legend-title {
        font-weight: bold;
        font-size: 1.1em;
        margin-bottom: 10px;
        color: #333;
        border-bottom: 2px solid #007bff;
        display: inline-block;
        padding-bottom: 3px;
        margin-top: 15px;
    }
    .legend-row { display: flex; align-items: flex-start; margin-bottom: 8px; direction: rtl; }
    .legend-icon-box { font-size: 1.4em; min-width: 35px; text-align: center; margin-left: 10px; }
    .legend-text { color: #555; font-size: 0.95em; line-height: 1.5; margin-top: 3px; }
    
    .report-header { font-size: 1.1em; font-weight: bold; color: #444; margin-top: 12px; margin-bottom: 5px; border-bottom: 1px solid #eee; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 🛠️ DATA LOADERS
# ==========================================
def clean_number(x):
    """Parse numbers that may include commas/spaces/currency symbols.
    Returns np.nan for invalid values."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    # pandas NA
    try:
        if pd.isna(x):
            return np.nan
    except Exception:
        pass

    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)

    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return np.nan

    s = s.replace(',', '')
    # remove anything that isn't digit/dot/minus
    s = re.sub(r"[^\d\.\-]", "", s)
    try:
        return float(s)
    except Exception:
        return np.nan

def extract_date_from_header_or_filename(file_obj):
    try:
        file_obj.seek(0)
        content_head = file_obj.read(1000).decode('cp1255', errors='ignore')
        file_obj.seek(0)
        match = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', content_head)
        if match: return pd.to_datetime(match.group(1).replace('-', '/'), dayfirst=True).date()
        match_name = re.search(r'(\d{2}[/-]\d{2}[/-]\d{4})', file_obj.name)
        if match_name: return pd.to_datetime(match_name.group(1).replace('-', '/'), dayfirst=True).date()
    except: file_obj.seek(0)
    return None

def _infer_col(df, predicates):
    """Return first column name satisfying any predicate (callable) on str(col)."""
    for c in df.columns:
        s = str(c)
        for pred in predicates:
            try:
                if pred(s):
                    return c
            except Exception:
                continue
    return None

def _parse_option_type(name):
    s = str(name).strip().upper()
    # Most TASE option tickers start with C/P
    if s.startswith('C'):
        return 'Call'
    if s.startswith('P'):
        return 'Put'
    # fallback
    return 'Call' if 'C' in s else 'Put'

def process_single_file(uploaded_file):
    """Read a single TASE 'all derivatives' CSV and normalize core columns.
    Returns None when mandatory columns are missing (so caller can skip)."""
    file_date = extract_date_from_header_or_filename(uploaded_file)
    if not file_date:
        return None

    df = None
    for enc in ['cp1255', 'utf-8', 'iso-8859-8']:
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=2, encoding=enc)
            break
        except Exception:
            continue
    if df is None or df.empty:
        return None

    df.columns = [str(c).strip() for c in df.columns]

    # Filter underlying
    if 'נכס הבסיס' in df.columns:
        df = df[df['נכס הבסיס'].astype(str).str.contains("מדד ת''א-35|תא-35", na=False, regex=True)].copy()

    # Infer important columns (robust to variants like 'שער נעילה (₪)')
    expiry_col = _infer_col(df, [lambda s: 'תאריך מימוש' in s, lambda s: 'Expiry' in s])
    strike_col = _infer_col(df, [lambda s: 'מחיר מימוש' in s, lambda s: 'Strike' in s])
    oi_col = _infer_col(df, [lambda s: "פוז" in s and "פתוח" in s, lambda s: 'OpenInterest' in s])
    vol_col = _infer_col(df, [lambda s: 'מחזור ביחידות' in s, lambda s: 'Volume' in s])
    sec_col = _infer_col(df, [lambda s: 'שם נייר' == s, lambda s: 'SecurityName' in s])
    price_col = _infer_col(df, [lambda s: 'שער בסיס' in s, lambda s: 'שער נעילה' in s, lambda s: 'Price' in s])

    if not expiry_col or not strike_col or not sec_col:
        return None

    # If the file doesn't contain OI/Volume, it's not useful for this lab (skip safely)
    if not oi_col or not vol_col:
        return None

    df[expiry_col] = pd.to_datetime(df[expiry_col], dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=[expiry_col])

    # Option type from ticker
    df['Type'] = df[sec_col].apply(_parse_option_type)

    # Numeric fields
    df[strike_col] = pd.to_numeric(df[strike_col], errors='coerce')
    df = df.dropna(subset=[strike_col])
    df = df[df[strike_col] > 500]

    df[oi_col] = df[oi_col].apply(clean_number).fillna(0)
    df[vol_col] = df[vol_col].apply(clean_number).fillna(0)

    if price_col:
        df[price_col] = df[price_col].apply(clean_number).fillna(0)
    else:
        df['__PriceTmp'] = 0
        price_col = '__PriceTmp'

    # Normalize core columns
    col_mapping = {
        oi_col: 'OpenInterest',
        strike_col: 'Strike',
        sec_col: 'SecurityName',
        vol_col: 'Volume',
        expiry_col: 'Expiry',
        price_col: 'Price'
    }
    df = df.rename(columns=col_mapping)
    df['Snapshot_Date'] = file_date

    # Keep only relevant cols + any extras
    return df
def load_tase_csv_history_robust(uploaded_files):
    master = []
    for f in uploaded_files:
        try:
            res = process_single_file(f)
            if res is not None and not res.empty: master.append(res)
        except: continue
    if master: return pd.concat(master, ignore_index=True).sort_values('Snapshot_Date')
    return pd.DataFrame()

def load_spot_data_tase(uploaded_file):
    try:
        df = pd.read_csv(uploaded_file, header=2)
        col_map = {}
        for c in df.columns:
            cl = str(c).lower()
            if 'date' in cl or 'תאריך' in cl: col_map[c] = 'Date'
            elif 'closing' in cl or 'נעילה' in cl: col_map[c] = 'Close'
            elif 'high' in cl: col_map[c] = 'High'
            elif 'low' in cl: col_map[c] = 'Low'
        df.rename(columns=col_map, inplace=True)
        if 'Date' not in df.columns or 'Close' not in df.columns: return pd.DataFrame()
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce').dt.date
        df = df.dropna(subset=['Date']).sort_values('Date')
        for nc in ['Close', 'High', 'Low']:
            if nc in df.columns: df[nc] = df[nc].astype(str).str.replace(',', '').apply(pd.to_numeric, errors='coerce')
        df['Change_Pct'] = df['Close'].pct_change() * 100
        return df
    except: return pd.DataFrame()

def simple_to_markdown(df):
    if df.empty: return ""
    headers = [str(c) for c in df.columns]
    header_row = "| " + " | ".join(headers) + " |"
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_rows = []
    for _, row in df.iterrows():
        data_rows.append("| " + " | ".join([str(val) for val in row]) + " |")
    return "\n" + "\n".join([header_row, separator_row] + data_rows) + "\n"

# ==========================================
# 🧠 RICH REPORT ENGINE (V3) - FIXED
# ==========================================
def generate_rich_daily_report(df_full, df_spot):
    """
    מנוע דוחות עשיר לפי המפרט החדש (7 סעיפים) עם תיקוני שגיאות.
    """
    report = []
    
    # 1. נתונים בסיסיים
    latest_date = df_full['Snapshot_Date'].max()
    df_day = df_full[df_full['Snapshot_Date'] == latest_date].copy()
    
    # חישוב תמורה (Turnover)
    if 'Turnover' not in df_day.columns:
        df_day['Turnover'] = df_day['Volume'] * df_day['Price']
    
    spot_close = 0
    daily_chg = 0
    daily_high = 0
    daily_low = 0
    
    if df_spot is not None and not df_spot.empty:
        # Prefer exact match; otherwise fall back to the latest available spot date <= snapshot date
        spot_row = df_spot[df_spot['Date'] == latest_date]
        if spot_row.empty:
            spot_row = df_spot[df_spot['Date'] <= latest_date].tail(1)

        if not spot_row.empty:
            spot_close = spot_row.iloc[0]['Close']
            daily_chg = spot_row.iloc[0].get('Change_Pct', 0)
            daily_high = spot_row.iloc[0].get('High', 0)
            daily_low = spot_row.iloc[0].get('Low', 0)
    
    if spot_close == 0:
        return "⚠️ שגיאה: חסרים נתוני מדד (Spot) לתאריך העדכני לצורך חישובי Moneyness."

    # חישוב Moneyness ו-Buckets
    df_day['Moneyness_Pct'] = (df_day['Strike'] - spot_close) / spot_close
    conditions = [
        abs(df_day['Moneyness_Pct']) <= 0.005, # ATM (0.5%)
        (abs(df_day['Moneyness_Pct']) > 0.005) & (abs(df_day['Moneyness_Pct']) <= 0.02), # Near (2%)
        (abs(df_day['Moneyness_Pct']) > 0.02) & (abs(df_day['Moneyness_Pct']) <= 0.06), # Wings (6%)
        abs(df_day['Moneyness_Pct']) > 0.06 # Deep
    ]
    choices = ['ATM', 'Near', 'Wings', 'Deep']
    df_day['Bucket'] = np.select(conditions, choices, default='Other')

    # --- 1. תקציר מנהלים ---
    rng_pct = ((daily_high - daily_low) / daily_low * 100) if daily_low > 0 else 0
    report.append(f"**תאריך:** {latest_date}")
    report.append(f"**מדד ת״א-35 סגירה:** {spot_close:,.2f} | **שינוי:** {daily_chg:+.2f}% | **טווח:** {rng_pct:.1f}%")
    
    total_vol_c = df_day[df_day['Type']=='Call']['Volume'].sum()
    total_vol_p = df_day[df_day['Type']=='Put']['Volume'].sum()
    pcr_vol = total_vol_p / total_vol_c if total_vol_c > 0 else 0
    
    top_exp = df_day.groupby('Expiry')['Volume'].sum().idxmax()
    
    headline = "Headline: "
    if pcr_vol > 1.2: headline += "נטייה הגנתית (P/C גבוה)"
    elif pcr_vol < 0.8: headline += "סנטימנט שורי"
    else: headline += "מסחר מאוזן"
    headline += f" + מסחר ער בפקיעת {top_exp}."
    
    report.append(f"> {headline}")
    report.append("---")

    # --- 2. חלוקת פעילות לפי פקיעה ---
    report.append("**2) חלוקת פעילות לפי פקיעה**")
    expiries = sorted(df_day['Expiry'].unique())
    total_mkt_vol = df_day['Volume'].sum()
    total_mkt_oi = df_day['OpenInterest'].sum()
    
    rows_exp = []
    for exp in expiries:
        sub = df_day[df_day['Expiry'] == exp]
        vol = sub['Volume'].sum()
        oi = sub['OpenInterest'].sum()
        turnover = sub['Turnover'].sum()
        
        vc = sub[sub['Type']=='Call']['Volume'].sum()
        vp = sub[sub['Type']=='Put']['Volume'].sum()
        pc_vol = vp/vc if vc > 0 else 0
        
        oc = sub[sub['Type']=='Call']['OpenInterest'].sum()
        op = sub[sub['Type']=='Put']['OpenInterest'].sum()
        pc_oi = op/oc if oc > 0 else 0
        
        share_vol = vol / total_mkt_vol if total_mkt_vol > 0 else 0
        share_oi = oi / total_mkt_oi if total_mkt_oi > 0 else 0
        
        nature = ""
        if share_vol > 0.4 and share_oi < 0.2: nature = "מסחרית (High Vol)"
        elif share_oi > 0.3: nature = "מבנית (High OI)"
        else: nature = "רגילה"
        
        rows_exp.append({
            "Exp": str(exp),
            "Vol": f"{int(vol/1000)}k ({share_vol:.0%})",
            "OI": f"{int(oi/1000)}k ({share_oi:.0%})",
            "Turnover": f"{int(turnover/1e6)}M",
            "P/C Vol": f"{pc_vol:.2f}",
            "P/C OI": f"{pc_oi:.2f}",
            "Nature": nature
        })
    report.append(simple_to_markdown(pd.DataFrame(rows_exp)))
    report.append(" ")

    # --- 3. שכבות מונינס ---
    report.append("**3) שכבות מונינס (סביב הכסף מול כנפיים)**")
    rows_bucket = []
    pc_vol_by_layer = {}
    for b in ['ATM', 'Near', 'Wings', 'Deep']:
        sub = df_day[df_day['Bucket'] == b]
        if sub.empty:
            continue

        vc = sub[sub['Type']=='Call']['Volume'].sum()
        vp = sub[sub['Type']=='Put']['Volume'].sum()
        pc_vol = vp/vc if vc > 0 else 0
        pc_vol_by_layer[b] = pc_vol

        oc = sub[sub['Type']=='Call']['OpenInterest'].sum()
        op = sub[sub['Type']=='Put']['OpenInterest'].sum()
        pc_oi = op/oc if oc > 0 else 0

        top_s = sub.groupby(['Strike', 'Type'])['Volume'].sum().sort_values(ascending=False).head(3)
        top_desc = ", ".join([f"{i[1]}{i[0]}" for i in top_s.index])

        rows_bucket.append({
            "Layer": b,
            "P/C Vol": f"{pc_vol:.2f}",
            "P/C OI": f"{pc_oi:.2f}",
            "Top Active": top_desc
        })
    report.append(simple_to_markdown(pd.DataFrame(rows_bucket)))

    wings_pc = pc_vol_by_layer.get('Wings', 0)
    atm_vol_share = (df_day[df_day['Bucket']=='ATM']['Volume'].sum() / total_mkt_vol) if total_mkt_vol > 0 else 0

    concl = f"מיקוד מסחר: {'ATM' if atm_vol_share > 0.3 else 'מפוזר'}. "
    concl += f"ביקוש להגנות: {'גבוה בכנפיים' if wings_pc > 1.2 else 'נמוך'}."
    report.append(f"> {concl}")
    report.append(" ")

    # --- 4. קירות ורמות מפתח ---
    report.append("**4) קירות (Walls) ורמות מפתח**")
    for exp in expiries[:2]:
        sub = df_day[df_day['Expiry'] == exp]
        if sub.empty: continue
        
        # Safe checking for Walls
        calls_sub = sub[sub['Type']=='Call']
        puts_sub = sub[sub['Type']=='Put']
        
        report.append(f"**פקיעה {exp}:**")
        
        if not calls_sub.empty:
            cw_idx = calls_sub['OpenInterest'].idxmax()
            cw = sub.loc[cw_idx]
            dist_c = (cw['Strike']/spot_close - 1) * 100
            report.append(f"* Call Wall: {int(cw['Strike'])} (OI: {int(cw['OpenInterest']):,}) ⟵ {dist_c:+.1f}%")
        
        if not puts_sub.empty:
            pw_idx = puts_sub['OpenInterest'].idxmax()
            pw = sub.loc[pw_idx]
            dist_p = (pw['Strike']/spot_close - 1) * 100
            report.append(f"* Put Wall: {int(pw['Strike'])} (OI: {int(pw['OpenInterest']):,}) ⟵ {dist_p:+.1f}%")
            
    report.append(" ")

    # --- 5. טווח מתומחר (ATM Straddle) ---
    report.append("**5) טווח מתומחר (Implied Range)**")
    atm_strike = round(spot_close / 10) * 10
    
    if 'Price' in df_day.columns and df_day['Price'].sum() > 0:
        sub_near = df_day[df_day['Expiry'] == expiries[0]]
        atm_call = sub_near[(sub_near['Strike'] == atm_strike) & (sub_near['Type'] == 'Call')]['Price'].mean()
        atm_put = sub_near[(sub_near['Strike'] == atm_strike) & (sub_near['Type'] == 'Put')]['Price'].mean()
        
        if pd.notna(atm_call) and pd.notna(atm_put):
            premium_pts = (atm_call + atm_put) / 100 
            lower = spot_close - premium_pts
            upper = spot_close + premium_pts
            implied_move = (premium_pts / spot_close) * 100
            
            report.append(f"* **ATM Strike:** {atm_strike}")
            report.append(f"* **Straddle Premium:** {premium_pts:.1f} נקודות")
            report.append(f"* **Break-even:** {lower:.0f} - {upper:.0f}")
            report.append(f"* **Range %:** ±{implied_move:.1f}%")
        else:
            report.append("לא נמצאו מחירי אופציות לסטרייק ATM בפקיעה הקרובה.")
    else:
        report.append("חסרים נתוני מחיר (Price) לחישוב סטרדל.")
    report.append(" ")

    # --- 6. איתור מבנים (Synthetics) ---
    report.append("**6) איתור מבנים (Alerts)**")
    alerts = []
    for exp in expiries[:2]:
        sub = df_day[df_day['Expiry'] == exp]
        for k in sub['Strike'].unique():
            s_row = sub[sub['Strike'] == k]
            if len(s_row) < 2: continue
            
            oi_c = s_row[s_row['Type']=='Call']['OpenInterest'].sum()
            oi_p = s_row[s_row['Type']=='Put']['OpenInterest'].sum()
            
            if oi_c > 500 and oi_p > 500:
                diff_ratio = abs(oi_c - oi_p) / max(oi_c, oi_p)
                if diff_ratio <= 0.1:
                    alerts.append(f"- {exp} Strike {int(k)}: OI Call={int(oi_c)} | Put={int(oi_p)} (Sym)")

    if alerts:
        report.append("\n".join(alerts))
        report.append("> מסקנה: יש ריכוז מבני/סינתטי בסטרייקים הנ\"ל.")
    else:
        report.append("> לא התגלו סטרייקים עם OI סימטרי חריג.")
    report.append(" ")

    # --- 7. סיכום ציפיות ---
    report.append("**7) סיכום ציפיות לפי שחקן**")
    bias_short = "דשדוש/יציבות" if abs(daily_chg) < 0.3 else "תנודתיות"
    bias_monthly = "חיובי" if pcr_vol < 0.9 else "שלילי/גידור"
    inst_act = "פעילים בהגנות" if wings_pc > 1.2 else "המתנה"
    writers = "נוח (שחיקה)" if rng_pct < 0.8 else "בלחץ (תנועה)"
    
    summary_table = pd.DataFrame([{
        "טווח קצר (שבועי)": bias_short,
        "טווח חודשי": bias_monthly,
        "מוסדיים/הגנות": inst_act,
        "כותבי פרמיה": writers
    }])
    report.append(simple_to_markdown(summary_table))

    return "\n".join(report)

# ==========================================
# 🧠 CORE LOGIC
# ==========================================
def calculate_max_pain(df_day):
    if df_day is None or df_day.empty:
        return 0

    # aggregate to avoid duplicates per strike/type
    agg = df_day.groupby(['Strike', 'Type'], as_index=False)['OpenInterest'].sum()

    calls = agg[agg['Type'] == 'Call']
    puts = agg[agg['Type'] == 'Put']
    strikes = sorted(agg['Strike'].unique())
    min_loss = float('inf')
    max_pain_strike = 0

    for strike_price in strikes:
        loss_calls = calls.apply(lambda row: max(0, strike_price - row['Strike']) * row['OpenInterest'], axis=1).sum()
        loss_puts = puts.apply(lambda row: max(0, row['Strike'] - strike_price) * row['OpenInterest'], axis=1).sum()
        total_loss = loss_calls + loss_puts
        if total_loss < min_loss:
            min_loss = total_loss
            max_pain_strike = strike_price

    return max_pain_strike

def verify_outcome(event_type, strike, event_date, df_spot, expiry_date):
    if df_spot is None or df_spot.empty: return "אין נתוני מדד"
    future_data = df_spot[(df_spot['Date'] > event_date) & (df_spot['Date'] <= expiry_date)].head(3)
    if future_data.empty: return "ממתין..." 
    base_row = df_spot[df_spot['Date'] == event_date]
    if base_row.empty: return "חסר בסיס"
    base_close = base_row.iloc[0]['Close']
    final_close = future_data.iloc[-1]['Close']
    strike_val = int(re.search(r'\d+', str(strike)).group()) if re.search(r'\d+', str(strike)) else 0
    
    if "איסוף" in event_type:
        if "Call" in strike and final_close > base_close: return "✅ רווח"
        if "Put" in strike and final_close < base_close: return "✅ רווח"
        else: return "❌ הפסד"
    elif "מבצר" in event_type:
        if "Call" in strike:
            if final_close > strike_val: return "💥 נפרץ!"
            else: return "🛡️ נבלם"
        elif "Put" in strike:
            if final_close < strike_val: return "💥 נשבר!"
            else: return "🛡️ נבלם"
    return "⚪"

def analyze_relative_sherlock(df_series, df_spot=None):
    events = []
    snapshots = sorted(df_series['Snapshot_Date'].unique())
    spot_map = df_spot.set_index('Date').to_dict('index') if df_spot is not None else {}
    expiry_date = df_series['Expiry'].iloc[0]
    sample_name = df_series['SecurityName'].iloc[0] if not df_series.empty else ""
    is_monthly = 'M' in str(sample_name).upper()
    league_label = "M (חודשי)" if is_monthly else "W (שבועי)"
    
    TH_DOM = 0.04 if is_monthly else 0.15

    for i in range(1, len(snapshots)):
        curr_date = snapshots[i]
        prev_date = snapshots[i-1]
        df_curr = df_series[df_series['Snapshot_Date'] == curr_date]
        df_prev = df_series[df_series['Snapshot_Date'] == prev_date]
        spot = spot_map.get(curr_date, {})
        spot_desc = ""
        if spot: chg = spot.get('Change_Pct', 0); spot_desc = f"{'🟢' if chg>0 else '🔴'} {chg:+.2f}%"

        merged = pd.merge(df_curr.groupby(['Strike', 'Type'])[['OpenInterest', 'Volume']].sum().reset_index(), df_prev.groupby(['Strike', 'Type'])['OpenInterest'].sum().reset_index(), on=['Strike', 'Type'], how='left', suffixes=('', '_prev')).fillna(0)
        merged['Diff'] = merged['OpenInterest'] - merged['OpenInterest_prev']
        total_vol = merged['Volume'].sum()
        if total_vol == 0: continue
        
        # זיהוי אירועים ברמת סטרייק
        for _, row in merged.iterrows():
            strike = int(row['Strike'])
            otype = row['Type']
            diff = row['Diff']
            vol = row['Volume']
            oi = row['OpenInterest']
            prev_oi = row['OpenInterest_prev']
            dominance = vol / total_vol
            vol_to_oi = vol / (oi + 1)
            
            # Fortress
            if dominance > TH_DOM and vol_to_oi > 2.0:
                events.append({"תאריך": curr_date, "סדרה": league_label, "אייקון": "🏰", "אירוע": f"🏰 מבצר", "סטרייק": f"{otype} {strike}", "פרטים": f"Dom: {dominance:.0%} | Vol: {int(vol)}", "מצב שוק": spot_desc, "פרשנות": "בלימה", "מבחן התוצאה (T+3)": verify_outcome("מבצר", f"{otype} {strike}", curr_date, df_spot, expiry_date), "Score": 4})

            # Accumulation
            pct_grow = diff / (prev_oi + 1)
            if pct_grow > 0.25 and diff > 200:
                events.append({"תאריך": curr_date, "סדרה": league_label, "אייקון": "🚜", "אירוע": f"🚜 איסוף", "סטרייק": f"{otype} {strike}", "פרטים": f"+{int(diff)} ({pct_grow:.0%})", "מצב שוק": spot_desc, "פרשנות": "כניסת כסף", "מבחן התוצאה (T+3)": verify_outcome("איסוף", f"{otype} {strike}", curr_date, df_spot, expiry_date), "Score": 3})

            # Capitulation
            if diff < -200 and (abs(diff)/(prev_oi+1)) > 0.15:
                events.append({"תאריך": curr_date, "סדרה": league_label, "אייקון": "🏳️", "אירוע": f"🏳️ כניעה", "סטרייק": f"{otype} {strike}", "פרטים": f"{int(diff)} יציאה", "מצב שוק": spot_desc, "פרשנות": "בריחה", "מבחן התוצאה (T+3)": "⚪", "Score": 2})

        # Straddle
        strikes = merged['Strike'].unique()
        for k in strikes:
            s_row = merged[merged['Strike'] == k]
            if len(s_row) < 2: continue
            vol_c = s_row[s_row['Type']=='Call']['Volume'].sum()
            vol_p = s_row[s_row['Type']=='Put']['Volume'].sum()
            if vol_c > 500 and vol_p > 500:
                 events.append({"תאריך": curr_date, "סדרה": league_label, "אייקון": "⚖️", "אירוע": "⚖️ אוכף", "סטרייק": str(k), "פרטים": f"Vol C:{int(vol_c)} P:{int(vol_p)}", "מצב שוק": spot_desc, "פרשנות": "צפי לתנודה", "מבחן התוצאה (T+3)": "⚪", "Score": 5})

    if not events: return pd.DataFrame()
    return pd.DataFrame(events).sort_values(by=['תאריך', 'Score'], ascending=[False, False])

# ==========================================
# 📊 TACTICAL BATTLE MAP GRAPH
# ==========================================
def create_tactical_map(df_full, df_spot):
    latest_date = df_full['Snapshot_Date'].max()
    df_day = df_full[df_full['Snapshot_Date'] == latest_date].copy()
    
    spot_close = 0
    if df_spot is not None and not df_spot.empty:
        spot_row = df_spot[df_spot['Date'] == latest_date]
        if not spot_row.empty: spot_close = spot_row.iloc[0]['Close']
    
    if spot_close == 0: return go.Figure()

    # Filter Range
    min_k = spot_close * 0.94
    max_k = spot_close * 1.06
    df_day = df_day[(df_day['Strike'] >= min_k) & (df_day['Strike'] <= max_k)]
    
    grouped = df_day.groupby(['Strike', 'Type'])['OpenInterest'].sum().unstack(fill_value=0)
    if 'Call' not in grouped.columns: grouped['Call'] = 0
    if 'Put' not in grouped.columns: grouped['Put'] = 0
    
    max_oi_val = max(grouped['Call'].max(), grouped['Put'].max())
    annotations = []
    
    # 1. High Orbit: Walls
    if not grouped.empty:
        if not grouped['Call'].empty and grouped['Call'].max() > 0:
            call_wall_strike = grouped['Call'].idxmax()
            annotations.append(dict(x=call_wall_strike, y=max_oi_val * 1.15, text="🧱 Call Wall", showarrow=True, arrowhead=2, arrowcolor="#d32f2f", bgcolor="rgba(255, 235, 238, 0.9)", bordercolor="#d32f2f", borderwidth=1, font=dict(color="#d32f2f", size=11)))
        
        if not grouped['Put'].empty and grouped['Put'].max() > 0:
            put_wall_strike = grouped['Put'].idxmax()
            annotations.append(dict(x=put_wall_strike, y=max_oi_val * 1.15, text="🛡️ Put Wall", showarrow=True, arrowhead=2, arrowcolor="#1b5e20", bgcolor="rgba(232, 245, 233, 0.9)", bordercolor="#1b5e20", borderwidth=1, font=dict(color="#1b5e20", size=11)))

    # 2. Mid Orbit: Max Pain & Range
    mp_strike = calculate_max_pain(df_day)
    annotations.append(dict(x=mp_strike, y=max_oi_val * 1.08, text="🎯 Max Pain", showarrow=True, arrowhead=2, arrowcolor="#0288d1", bgcolor="rgba(225, 245, 254, 0.9)", bordercolor="#0288d1", borderwidth=1, font=dict(color="#0288d1", size=11)))

    if 'Price' in df_day.columns:
        expiries = sorted(df_day['Expiry'].unique())
        if expiries:
            near_exp = expiries[0]
            sub_near = df_day[df_day['Expiry'] == near_exp]
            atm_strike = round(spot_close / 10) * 10
            atm_call = sub_near[(sub_near['Strike'] == atm_strike) & (sub_near['Type'] == 'Call')]['Price'].mean()
            atm_put = sub_near[(sub_near['Strike'] == atm_strike) & (sub_near['Type'] == 'Put')]['Price'].mean()
            if pd.notna(atm_call) and pd.notna(atm_put):
                premium = (atm_call + atm_put) / 100 
                if premium > 0:
                    lower, upper = spot_close - premium, spot_close + premium
                    annotations.append(dict(x=lower, y=max_oi_val * 1.0, text="📉 Range Low", showarrow=True, arrowhead=1, arrowcolor="gray", bgcolor="white", bordercolor="gray", font=dict(size=10)))
                    annotations.append(dict(x=upper, y=max_oi_val * 1.0, text="📈 Range High", showarrow=True, arrowhead=1, arrowcolor="gray", bgcolor="white", bordercolor="gray", font=dict(size=10)))

    # 3. Low Orbit: Focus & Synthetics
    vol_grouped = df_day.groupby('Strike')['Volume'].sum()
    if not vol_grouped.empty:
        focus_strike = vol_grouped.idxmax()
        annotations.append(dict(x=focus_strike, y=max_oi_val * 0.9, text="🔥 Focus", showarrow=True, arrowhead=1, arrowcolor="orange", bgcolor="rgba(255, 243, 224, 0.9)", bordercolor="orange", font=dict(color="#e65100", size=10)))

    for k in df_day['Strike'].unique():
        if k in grouped.index:
            row = grouped.loc[k]
            if row['Call'] > 1000 and row['Put'] > 1000:
                diff = abs(row['Call'] - row['Put']) / max(row['Call'], row['Put'])
                if diff <= 0.1:
                    annotations.append(dict(x=k, y=max_oi_val * 0.82, text="⚠️ Syn", showarrow=True, arrowhead=1, arrowcolor="#fbc02d", bgcolor="#fffde7", bordercolor="#fbc02d", font=dict(color="#f9a825", size=9)))

    fig = go.Figure()
    fig.add_trace(go.Bar(x=grouped.index, y=grouped['Call'], name='Calls 🟢', marker_color='#2ecc71', opacity=0.8))
    fig.add_trace(go.Bar(x=grouped.index, y=grouped['Put'], name='Puts 🔴', marker_color='#e74c3c', opacity=0.8))
    fig.add_vline(x=spot_close, line_width=2, line_dash="dash", line_color="gold", annotation_text="SPOT", annotation_position="top right")

    fig.update_layout(
        title=f"Tactical Battle Map ({latest_date})", barmode='group', 
        xaxis_title="Strike Price", yaxis_title="Open Interest",
        annotations=annotations, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        height=500, margin=dict(t=80)
    )
    return fig

def create_cinematic_graph(df_series, expiry_date):
    snapshots = sorted(df_series['Snapshot_Date'].unique())
    if not snapshots: return go.Figure()
    max_oi = df_series['OpenInterest'].max() * 1.1
    max_vol = df_series['Volume'].max() * 1.1
    frames = []
    
    def calc(curr, prev, ot):
        # aggregate by strike to keep 1 row per strike (prevents accidental many-to-many merges)
        c = curr[curr['Type'] == ot].groupby('Strike', as_index=False)[['OpenInterest', 'Volume']].sum()
        p = prev[prev['Type'] == ot].groupby('Strike', as_index=False)[['OpenInterest', 'Volume']].sum() if prev is not None else pd.DataFrame()

        if c.empty:
            return [], [], [], [], []

        if not p.empty:
            merged = pd.merge(c, p, on='Strike', how='outer', suffixes=('_curr', '_prev')).fillna(0)
        else:
            merged = c.rename(columns={'OpenInterest': 'OpenInterest_curr', 'Volume': 'Volume_curr'})
            merged['OpenInterest_prev'] = 0
            merged['Volume_prev'] = 0

        merged['Base'] = np.minimum(merged['OpenInterest_curr'], merged['OpenInterest_prev'])
        merged['Inflow'] = np.where(merged['OpenInterest_curr'] > merged['OpenInterest_prev'], merged['OpenInterest_curr'] - merged['OpenInterest_prev'], 0)
        merged['Outflow'] = np.where(merged['OpenInterest_prev'] > merged['OpenInterest_curr'], merged['OpenInterest_prev'] - merged['OpenInterest_curr'], 0)
        merged = merged.sort_values('Strike')

        vol_series = merged['Volume_curr'] if 'Volume_curr' in merged.columns else pd.Series(0, index=merged.index)
        return merged['Strike'], merged['Base'], merged['Inflow'], merged['Outflow'], vol_series

    for i, date in enumerate(snapshots):
        df_curr = df_series[df_series['Snapshot_Date'] == date]
        df_prev = df_series[df_series['Snapshot_Date'] == snapshots[i-1]] if i > 0 else None
        mp_strike = calculate_max_pain(df_curr)
        cx, cb, ci, co, cv = calc(df_curr, df_prev, 'Call')
        px, pb, pi, po, pv = calc(df_curr, df_prev, 'Put')
        frames.append(go.Frame(data=[
            go.Bar(x=cx, y=cb, marker_color='#1e4620', offsetgroup=1, name='Calls Base 🟢'), 
            go.Bar(x=cx, y=ci, marker_color='#39ff14', offsetgroup=1, base=cb, name='Calls New 🟢'),
            go.Bar(x=cx, y=co, marker_color='rgba(0,0,0,0)', marker_line_color='red', marker_line_width=1, offsetgroup=1, base=cb, name='Calls Exit'),
            go.Bar(x=px, y=pb, marker_color='#4a0404', offsetgroup=2, name='Puts Base 🔴'), 
            go.Bar(x=px, y=pi, marker_color='#ff4040', offsetgroup=2, base=pb, name='Puts New 🔴'),
            go.Bar(x=px, y=po, marker_color='rgba(0,0,0,0)', marker_line_color='yellow', marker_line_width=1, offsetgroup=2, base=pb, name='Puts Exit'),
            go.Scatter(x=cx, y=cv, marker=dict(color='cyan'), name='Call Vol 🔷', yaxis='y2'), 
            go.Scatter(x=px, y=pv, marker=dict(color='magenta'), name='Put Vol 🔶', yaxis='y2'),
            go.Scatter(x=[mp_strike, mp_strike], y=[0, max_oi], mode='lines', line=dict(color='cyan', width=2, dash='dash'), name='Max Pain', hoverinfo='x')
        ], name=str(date)))

    last_idx = len(snapshots) - 1
    fig = go.Figure(data=frames[last_idx].data, frames=frames)
    fig.update_layout(title=f"Cinema: {expiry_date}", barmode='group', bargap=0.15, bargroupgap=0.05,
        yaxis=dict(title="OI (פוזיציות פתוחות)", range=[0, max_oi], side="left", showgrid=True),
        yaxis2=dict(title="Volume (מחזור מסחר)", overlaying='y', side='right', range=[0, max_vol], showgrid=False, anchor="x"),
        height=550, legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center"),
        updatemenus=[dict(type="buttons", showactive=False, x=0.05, y=1.15, buttons=[dict(label="▶️ Play", method="animate", args=[None, dict(frame=dict(duration=500, redraw=True), fromcurrent=True)]), dict(label="⏸️ Pause", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=True), mode="immediate", transition=dict(duration=0))])])], 
        sliders=[dict(active=last_idx, steps=[dict(method='animate', args=[[str(d)], dict(mode='immediate', frame=dict(duration=0, redraw=True))], label=str(d)) for d in snapshots], currentvalue=dict(prefix="Date: "), pad=dict(t=50))])
    
    names = ['C-Base', 'C-New', 'C-Exit', 'P-Base', 'P-New', 'P-Exit', 'Call Vol 🔷', 'Put Vol 🔶', 'Max Pain']
    for i, trace in enumerate(fig.data):
        trace.name = names[i]
        if 'Vol' in trace.name: trace.yaxis = 'y2'; trace.mode = 'lines+markers'; trace.marker.symbol = 'diamond'; trace.marker.size = 5
        if 'Max Pain' in trace.name: trace.mode = 'lines'
    return fig

# ==========================================
# 🚀 MAIN APP
# ==========================================
def main():
    col_back, col_title = st.columns([1, 5])
    with col_back:
        st.page_link("main.py", label="⬅️ חזרה לחדר ניתוח", use_container_width=True)
    with col_title:
        st.title("🧪 DOR OI Lab: Master Edition")

    st.markdown("""
        <a href="https://market.tase.co.il/en/market_data/index/142/historical_data/eod" target="_blank" class="tase-link">📥 הורד מדד (TASE)</a>
        <a href="https://market.tase.co.il/he/market_data/derivatives/major_data/details" target="_blank" class="tase-link">📥 הורד נתוני נגזרים (OI)</a>
    """, unsafe_allow_html=True)

    with st.expander("📂 טעינת נתונים", expanded=True):
        c1, c2 = st.columns(2)
        files_opt = c1.file_uploader("1. קבצי נגזרים (CSV)", accept_multiple_files=True, type=['csv'])
        file_spot = c2.file_uploader("2. קובץ מדד (CSV)", type=['csv']) 

        if files_opt:
            sig = sorted([(f.name, f.size) for f in files_opt])
            hash_val = hashlib.md5(repr(sig).encode('utf-8')).hexdigest()
            if 'data_hash' not in st.session_state or st.session_state['data_hash'] != hash_val:
                with st.spinner("מעבד..."):
                    st.session_state['oi_data_full'] = load_tase_csv_history_robust(files_opt)
                    st.session_state['data_hash'] = hash_val
                    st.session_state['available_expiries'] = sorted(st.session_state['oi_data_full']['Expiry'].unique())
        
        if file_spot and ('spot_file_name' not in st.session_state or st.session_state['spot_file_name'] != file_spot.name):
            with st.spinner("טוען מדד..."):
                df_spot = load_spot_data_tase(file_spot)
                if not df_spot.empty:
                    st.session_state['spot_data'] = df_spot; st.session_state['spot_file_name'] = file_spot.name

    if 'oi_data_full' in st.session_state:
        df_full = st.session_state['oi_data_full']
        df_spot = st.session_state.get('spot_data', None)
        
        st.markdown("<div class='filter-box'>👇 בחר סדרת אופציות לחקירה</div>", unsafe_allow_html=True)
        sel_expiry = st.selectbox("Expiry:", st.session_state['available_expiries'], label_visibility="collapsed")
        df_series = df_full[df_full['Expiry'] == sel_expiry].copy()

        st.divider(); st.subheader(f"🎬 מצב קולנוע: {sel_expiry}")
        st.plotly_chart(create_cinematic_graph(df_series, sel_expiry), width='stretch')

        st.divider(); st.subheader("🕵️ יומן מודיעין יחסי")
        df_res = analyze_relative_sherlock(df_series, df_spot)
        
        if not df_res.empty:
            st.dataframe(df_res[["תאריך", "סדרה", "אייקון", "אירוע", "סטרייק", "פרטים", "פרשנות", "מבחן התוצאה (T+3)"]], width='stretch', hide_index=True)
        else: st.info("לא זוהו אירועים חריגים.")

        st.divider()
        st.subheader("📑 דוח יומי ומפת קרב")
        
        with st.expander("📄 דוח יומי מסכם (Daily Brief)", expanded=True):
            report_content = generate_rich_daily_report(df_full, df_spot)
            st.markdown(report_content, unsafe_allow_html=True)
        
        st.markdown("##### 🗺️ מפת קרב טקטית (Tactical Map)")
        st.plotly_chart(create_tactical_map(df_series, df_spot), width='stretch')

        with st.expander("📚 מקרא ומדריך"):
            legend_html = textwrap.dedent("""
<div class='legend-box'>
<div class='legend-title'>🔍 סוגי ניתוח</div>
<div class='legend-row'><span class='tag-m'>M</span>: חודשי. <span class='tag-w'>W</span>: שבועי.</div>
<div class='legend-title'>📌 אירועים</div>
<div class='legend-row'><div class='legend-icon-box'>🏰</div><div class='legend-text'><b>מבצר:</b> ווליום גבוה ללא שינוי בפוזיציה.</div></div>
<div class='legend-row'><div class='legend-icon-box'>🚜</div><div class='legend-text'><b>איסוף:</b> כניסת כסף חדש.</div></div>
<div class='legend-row'><div class='legend-icon-box'>🏳️</div><div class='legend-text'><b>כניעה:</b> יציאה מהשוק.</div></div>
<div class='legend-row'><div class='legend-icon-box'>⚖️</div><div class='legend-text'><b>אוכף:</b> פעילות סימטרית.</div></div>
<div class='legend-title'>🎈 מפת קרב</div>
<div class='legend-row'><div class='legend-text'><b>🧱 Call Wall:</b> חסם עליון (התנגדות).</div></div>
<div class='legend-row'><div class='legend-text'><b>🛡️ Put Wall:</b> חסם תחתון (תמיכה).</div></div>
<div class='legend-row'><div class='legend-text'><b>🎯 Max Pain:</b> נקודת איזון מוסדית.</div></div>
<div class='legend-row'><div class='legend-text'><b>🔥 Focus:</b> מוקד מסחר יומי.</div></div>
</div>
""")
            st.markdown(legend_html, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
