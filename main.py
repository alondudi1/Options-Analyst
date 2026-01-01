import streamlit as st
import pandas as pd
# אנו מייבאים את הקובץ החדש שיצרנו
from tase_data import get_tase_options_chain 

st.set_page_config(layout="wide", page_title="מעו\"ף אנליסט")

st.title('🇮🇱 מערכת ניתוח אופציות מעו"ף (ת"א 35)')

# 1. טעינת הנתונים
st.info("מתחבר לשרתי הבורסה לניירות ערך...")

# שימוש ב-Cache כדי לא להפציץ את הבורסה בבקשות כל רענון
@st.cache_data(ttl=600) # שומר זיכרון ל-10 דקות
def load_data():
    return get_tase_options_chain()

df = load_data()

if df.empty:
    st.error("לא הצלחנו למשוך נתונים מהבורסה כרגע. ייתכן שהמסחר סגור או שה-API השתנה.")
else:
    st.success(f"נמשכו {len(df)} אופציות בהצלחה!")

    # 2. סינון לפי תאריך פקיעה
    # המרת תאריכים לפורמט קריא אם צריך
    expirations = df['ExpirationDate'].unique()
    selected_expiry = st.sidebar.selectbox("בחר תאריך פקיעה:", sorted(expirations))
    
    # סינון הטבלה
    filtered_df = df[df['ExpirationDate'] == selected_expiry]
    
    # הפרדה ל-Call ו-Put
    calls = filtered_df[filtered_df['Type'] == 'Call']
    puts = filtered_df[filtered_df['Type'] == 'Put']
    
    # 3. תצוגה
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Calls 🟢")
        st.dataframe(calls[['Strike', 'LastPrice', 'Bid', 'Ask']], hide_index=True, use_container_width=True)
        
    with col2:
        st.subheader("Puts 🔴")
        st.dataframe(puts[['Strike', 'LastPrice', 'Bid', 'Ask']], hide_index=True, use_container_width=True)

    # כאן בהמשך נוסיף את גרף ה-Smile