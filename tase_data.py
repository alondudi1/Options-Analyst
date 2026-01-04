from curl_cffi import requests
import pandas as pd
import io
from datetime import datetime, timedelta

# --- פונקציות עזר (Mock Data) ---
def generate_mock_data():
    """נתונים סינתטיים לגיבוי"""
    # ... (אותו קוד כמו קודם) ...
    print("--- מייצר נתונים סינתטיים לגיבוי ---")
    spot = 2000
    strikes = range(1800, 2200, 20)
    expiry = (datetime.now() + timedelta(days=14)).strftime("%d/%m/%Y")
    data = []
    for k in strikes:
        call_p = max(0, spot-k) + 20
        put_p = max(0, k-spot) + 20
        data.append({'Type': 'Call', 'Strike': k, 'ExpirationDate': expiry, 'LastPrice': call_p})
        data.append({'Type': 'Put', 'Strike': k, 'ExpirationDate': expiry, 'LastPrice': put_p})
    return pd.DataFrame(data)

# --- Investing.com Scraper ---
def get_investing_data():
    print("--- מנסה למשוך נתונים מ-Investing.com ---")
    url = "https://il.investing.com/indices/ta25-options"
    
    try:
        # Investing דורש User-Agent מאוד ספציפי כדי לא לחסום
        response = requests.get(url, impersonate="chrome", timeout=15)
        
        if response.status_code != 200:
            print(f"Investing חסם אותנו או שגיאה: {response.status_code}")
            return None

        # קריאת הטבלאות מה-HTML
        # ב-Investing הטבלה מפוצלת לפעמים או שיש טבלה אחת גדולה
        tables = pd.read_html(io.StringIO(response.text))
        
        df = pd.DataFrame()
        for table in tables:
            # מחפשים טבלה שיש בה 'סטרייק' או 'Strike' וגם מחיר
            headers = str(table.columns)
            if 'מימוש' in headers or 'Strike' in headers:
                df = table
                break
        
        if df.empty:
            print("לא נמצאה טבלת אופציות ב-Investing.")
            return None

        print("--- נמצאה טבלה ב-Investing! ---")
        # בדרך כלל ב-Investing המבנה הוא: Call Bid | Call Ask | Strike | Put Bid | Put Ask
        # נצטרך לראות את הפלט כדי למפות, אבל נחזיר את מה שיש
        return df

    except Exception as e:
        print(f"Investing Error: {e}")
        return None

# --- פונקציה ראשית ---
def get_tase_options_chain():
    # 1. עדיפות ראשונה: Investing.com
    df = get_investing_data()
    if df is not None and not df.empty:
        return df

    # 2. כאן היה הקוד של גלובס (אפשר להשאיר או להסיר)
    
    # 3. אם הכל נכשל - נתוני דמה
    return generate_mock_data()