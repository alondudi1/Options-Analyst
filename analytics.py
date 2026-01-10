import QuantLib as ql
import math

def calculate_iv(price, spot, strike, expiry_date, option_type, risk_free_rate=0.04):
    """
    מחשב סטיית תקן גלומה (Implied Volatility) באמצעות QuantLib
    """
    try:
        if price <= 0: return None # הגנה ממחירים לא הגיוניים

        # 1. הגדרת לוח שנה ותאריכים
        calendar = ql.Israel()
        today = ql.Date.todaysDate()
        
        # המרת תאריך (טיפול בפורמטים שונים)
        try:
            # מנסה פורמט יום/חודש/שנה (כמו בגלובס/סינתטי)
            d, m, y = map(int, expiry_date.split('/'))
            expiry = ql.Date(d, m, y)
        except:
            # הגנה למקרה שהתאריך מגיע בפורמט אחר
            return None

        # אם התאריך עבר, אין מה לחשב
        if expiry <= today:
            return None
        
        ql.Settings.instance().evaluationDate = today

        # 2. בניית האופציה
        option_type_ql = ql.Option.Call if option_type == 'Call' else ql.Option.Put
        payoff = ql.PlainVanillaPayoff(option_type_ql, float(strike))
        exercise = ql.EuropeanExercise(expiry)
        option = ql.VanillaOption(payoff, exercise)

        # 3. נתוני שוק
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(float(spot)))
        rate_handle = ql.YieldTermStructureHandle(ql.FlatForward(today, risk_free_rate, ql.Actual365Fixed()))
        div_handle = ql.YieldTermStructureHandle(ql.FlatForward(today, 0.0, ql.Actual365Fixed()))
        vol_handle = ql.BlackVolTermStructureHandle(ql.BlackConstantVol(today, calendar, 0.20, ql.Actual365Fixed()))

        process = ql.BlackScholesMertonProcess(spot_handle, div_handle, rate_handle, vol_handle)

        # 4. חישוב ה-IV
        implied_vol = option.impliedVolatility(
            float(price),
            process,
            1.0e-4, # דיוק
            100,    # מקסימום איטרציות
            0.001,  # מינימום סטייה
            4.0     # מקסימום סטייה
        )
        
        return implied_vol

    except Exception as e:
        # במקרה שהחישוב נכשל (נפוץ באופציות עמוקות בכסף)
        return None