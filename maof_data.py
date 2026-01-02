import requests
import yfinance as yf
import re
import numpy as np

def get_market_price():
    price = None
    source = ""
    # 1. TASE API
    try:
        url = "https://api.tase.co.il/api/index/rec/Indices"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tase.co.il/"}
        r = requests.get(url, headers=headers, timeout=4)
        if r.status_code == 200:
            data = r.json()
            for idx in data['indices']:
                if idx['indexId'] == 137: 
                    price = float(idx['lastPrice'])
                    source = "TASE API"
                    break
    except: pass

    # 2. Google Finance Scraping
    if price is None:
        try:
            url = "https://www.google.com/finance/quote/TA35:TLV"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                match = re.search(r'class="YMlKec fxKbKc">([0-9,.]+)<', r.text)
                if match:
                    price = float(match.group(1).replace(',', ''))
                    source = "Google Finance"
        except: pass

    # 3. Yahoo Finance
    if price is None:
        try:
            ticker = yf.Ticker("^TA35.TA")
            price = ticker.fast_info.get('last_price')
            if price and not np.isnan(price):
                source = "Yahoo Live"
            else:
                hist = ticker.history(period="5d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    source = "Yahoo History"
        except: pass
            
    return price, source