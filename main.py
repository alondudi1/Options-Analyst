import streamlit as st
import yfinance as yf
import QuantLib as ql

# 1. כותרת האפליקציה
st.title('מערכת ניתוח אופציות - גירסה 1.0')
st.write('ברוך הבא למערכת. כרגע האתר מחובר לשרת ומוכן לחישובים.')

# 2. בדיקת חיבור לספריות
today = ql.Date.todaysDate()
st.info(f'הליבה המתמטית (QuantLib) נטענה בהצלחה. תאריך המערכת: {today}')

# 3. בדיקה ויזואלית - גרף מנייה פשוט
ticker = st.text_input('הקלד סימול מניה (למשל GOOG, MSFT):', 'AAPL')

if ticker:
    st.write(f'מושך נתונים עבור {ticker}...')
    try:
        # משיכת נתונים לחודש האחרון
        data = yf.download(ticker, period='1mo')
        
        if not data.empty:
            # ציור גרף סגירה
            st.line_chart(data['Close'])
            st.success('הנתונים נטענו והוצגו בהצלחה.')
        else:
            st.error('לא נמצאו נתונים. בדוק את הסימול.')
            
    except Exception as e:
        st.error(f'שגיאה במשיכת נתונים: {e}')