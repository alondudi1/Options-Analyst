import requests
import pandas as pd
import datetime

def get_tase_options_chain():
    """
    פונקציה זו מושכת את שרשרת האופציות העדכנית של מדד ת"א 35 ישירות מאתר הבורסה.
    """
    # כתובת ה-API של הבורסה לנגזרים על מדדים (ת"א 35)
    url = "https://api.tase.co.il/api/content/derivativesseries/he/0/0/0/0"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://market.tase.co.il/"
    }

    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        # הבורסה מחזירה מבנה מורכב, אנחנו צריכים לפרק אותו לטבלה שטוחה
        options_list = []
        
        for item in data.get('result', []):
            # סינון: אנחנו רוצים רק אופציות על ת"א 35 (מדד 142 בד"כ)
            # לרוב ה-API הזה מחזיר את כל הנגזרים, צריך לסנן לפי שם או קוד
            if "תא35" not in item.get('Name', '').replace('"', '').replace("'", ""):
                continue

            # חילוץ סטרייק ותאריך פקיעה
            # הנתונים הגולמיים בבורסה מגיעים לפעמים בצורה שונה, זה ניסיון בסיסי:
            options_list.append({
                'Symbol': item.get('Id'),
                'Name': item.get('Name'),
                'Strike': item.get('ExercisePrice'),
                'ExpirationDate': item.get('ExpDate'), # פורמט תאריך צריך המרה
                'Type': 'Call' if item.get('Type') == 1 else 'Put', # הנחה: 1=Call, 2=Put (דורש בדיקה מול הדאטה בזמן אמת)
                'LastPrice': item.get('LastPrice'),
                'Bid': item.get('BidPrice'),
                'Ask': item.get('AskPrice'),
                'ImpliedVol': 0.0 # הבורסה לא תמיד נותנת את זה, אולי נצטרך לחשב לבד
            })
            
        df = pd.DataFrame(options_list)
        return df

    except Exception as e:
        print(f"Error fetching TASE data: {e}")
        return pd.DataFrame()

# בדיקה עצמית אם מריצים את הקובץ ישירות
if __name__ == "__main__":
    df = get_tase_options_chain()
    print(df.head())