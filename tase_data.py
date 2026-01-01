from curl_cffi import requests
import pandas as pd
import numpy as np # ודא שיש לך את זה, אם לא - pip install numpy
from datetime import datetime, timedelta

def get_real_bizportal_data():
    """מנסה למשוך נתונים אמיתיים מביזפורטל עם ניהול Session"""
    print("--- מנסה למשוך נתונים מביזפורטל (עם Session) ---")
    
    session = requests.Session() # Session שומר עוגיות בין בקשות
    
    # שלב 1: ביקור בדף הראשי כדי לקבל 'אישור כניסה' (Cookies/Tokens)
    main_url = "https://www.bizportal.co.il/capitalmarket/indices/derivatives/333"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://www.bizportal.co.il/"
    }
    
    try:
        # בקשה ראשונה - רק בשביל העוגיות
        session.get(main_url, headers=headers, impersonate="chrome", timeout=10)
        
        # שלב 2: פנייה ל-API עם העוגיות שאספנו
        api_url = "https://www.bizportal.co.il/forex/quote/ajaxrequests/paperdataderivatives"
        payload = {"paperId": "333"}
        
        # עדכון כותרות לבקשת ה-AJAX
        headers.update({
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": main_url,
            "Origin": "https://www.bizportal.co.il"
        })
        
        response = session.post(api_url, json=payload, headers=headers, impersonate="chrome", timeout=10)
        
        if response.status_code != 200:
            return None

        data = response.json()
        raw_list = data.get('derivativesList', [])
        
        if not raw_list:
            return None
            
        options_list = []
        for item in raw_list:
            strike = item.get('exercisePrice')
            expiry = item.get('futureDate') 
            
            # עיבוד Call
            if item.get('cPeriod'):
                options_list.append({
                    'Type': 'Call', 'Strike': strike, 'ExpirationDate': expiry,
                    'LastPrice': item.get('cLastPrice', 0),
                    'Bid': item.get('cBid', 0), 'Ask': item.get('cAsk', 0)
                })
            # עיבוד Put
            if item.get('pPeriod'):
                options_list.append({
                    'Type': 'Put', 'Strike': strike, 'ExpirationDate': expiry,
                    'LastPrice': item.get('pLastPrice', 0),
                    'Bid': item.get('pBid', 0), 'Ask': item.get('pAsk', 0)
                })
                
        return pd.DataFrame(options_list)

    except Exception as e:
        print(f"Scraping Error: {e}")
        return None

def generate_mock_data():
    """מייצר נתונים סינתטיים של תא-35 כדי שהפיתוח לא ייעצר"""
    print("--- מייצר נתונים סינתטיים (Mock Data) לפיתוח ---")
    spot_price = 2000 # מדד ת"א 35 בערך
    strikes = range(1800, 2200, 20) # סטרייקים בקפיצות של 20
    
    # תאריך פקיעה לעוד שבועיים
    expiry_date = (datetime.now() + timedelta(days=14)).strftime("%d/%m/%Y")
    
    data = []
    for k in strikes:
        # סימולציה פשוטה של מחירים (רק כדי שיהיה מה לצייר)
        # Call גס: מקסימום בין 0 ל-(מדד פחות סטרייק)
        intrinsic_call = max(0, spot_price - k)
        call_price = intrinsic_call + 20 # מוסיפים קצת "ערך זמן"
        
        intrinsic_put = max(0, k - spot_price)
        put_price = intrinsic_put + 20
        
        data.append({'Type': 'Call', 'Strike': k, 'ExpirationDate': expiry_date, 'LastPrice': call_price, 'Bid': call_price-5, 'Ask': call_price+5})
        data.append({'Type': 'Put', 'Strike': k, 'ExpirationDate': expiry_date, 'LastPrice': put_price, 'Bid': put_price-5, 'Ask': put_price+5})
        
    return pd.DataFrame(data)

def get_tase_options_chain():
    # 1. ניסיון אמיתי
    df = get_real_bizportal_data()
    
    if df is not None and not df.empty:
        print("הצלחה! נתונים אמיתיים נטענו.")
        return df
    
    # 2. אם נכשל - החזרת נתוני דמה
    print("הנתונים האמיתיים נכשלו - עובר למצב פיתוח (Mock Data).")
    return generate_mock_data()

if __name__ == "__main__":
    df = get_tase_options_chain()
    print(df.head())