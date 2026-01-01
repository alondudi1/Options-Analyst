import requests
import pandas as pd
import json

def get_tase_options_chain():
    print("--- מתחיל ניסיון התחברות לבורסה ---")
    
    # כתובת מעודכנת ומדויקת יותר למדד ת"א 35
    # (לפעמים הבורסה דורשת פרמטרים ספציפיים)
    url = "https://api.tase.co.il/api/content/derivativesseries/he/0/0/0/0"
    
    headers = {
        # אנחנו "מתחפשים" לדפדפן כרום רגיל
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://market.tase.co.il/",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://market.tase.co.il"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}") # 200 זה טוב, 403 זה חסימה
        
        if response.status_code != 200:
            print("הבורסה החזירה שגיאה. תוכן התגובה:")
            print(response.text[:200]) # מדפיס את תחילת השגיאה
            return pd.DataFrame()

        data = response.json()
        
        # הדפסה לבדיקת מבנה הנתונים שחזר
        if 'result' in data:
            print(f"התקבלו {len(data['result'])} שורות גולמיות.")
        else:
            print("המפתח 'result' לא נמצא בתשובה. המפתחות הקיימים הם:")
            print(data.keys())
            return pd.DataFrame()

        options_list = []
        
        for item in data.get('result', []):
            # בדיקה גסה יותר - האם זה נגזר על מדד?
            # 142 הוא המזהה הפנימי של מדד ת"א 35 בדרך כלל
            if "תא35" not in item.get('Name', '').replace('"', '').replace("'", ""):
                continue

            options_list.append({
                'Symbol': item.get('Id'),
                'Name': item.get('Name'),
                'Strike': item.get('ExercisePrice'),
                'ExpirationDate': item.get('ExpDate'),
                'Type': 'Call' if item.get('Type') == 1 else 'Put',
                'LastPrice': item.get('LastPrice'),
                'Bid': item.get('BidPrice'),
                'Ask': item.get('AskPrice')
            })
            
        print(f"סוננו {len(options_list)} אופציות רלוונטיות לתא-35.")
        return pd.DataFrame(options_list)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    # הרצה מקומית לבדיקה
    df = get_tase_options_chain()
    if not df.empty:
        print("\n--- הצלחה! הנה 5 השורות הראשונות: ---")
        print(df.head())
    else:
        print("\n--- כישלון: לא חזרה טבלה ---")
