from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

STOCKS = ["2330", "0050"]

# Full browser headers — TWSE blocks requests without these
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.twse.com.tw/zh/trading/historical/stock-day.html",
    "X-Requested-With": "XMLHttpRequest",
}

def get_price(stock_no):
    today = datetime.now().strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={today}&stockNo={stock_no}"
    
    res = requests.get(url, timeout=10, headers=HEADERS)
    
    if res.status_code != 200:
        raise Exception(f"HTTP {res.status_code}")
    
    if not res.text.strip():
        raise Exception("Empty response from TWSE")

    data = res.json()

    if data.get("stat") != "OK" or not data.get("data"):
        # Try previous month if current month has no data yet (e.g. first day of month)
        prev_month = datetime.now().strftime("%Y%m") + "01"
        url2 = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={prev_month}&stockNo={stock_no}"
        res2 = requests.get(url2, timeout=10, headers=HEADERS)
        data = res2.json()
        if data.get("stat") != "OK" or not data.get("data"):
            raise Exception(f"No data: {data.get('stat', 'unknown')}")

    latest = data["data"][-1]
    # Columns: [date, vol, val, open, high, low, close, change, txn]
    close = float(latest[6].replace(",", ""))
    try:
        change = float(latest[7].replace(",", "").strip())
    except:
        change = 0.0

    prev = close - change
    change_pct = round((change / prev) * 100, 2) if prev > 0 else 0

    # ROC date "115/05/18" → "05/18"
    parts = latest[0].split("/")
    date_label = f"{parts[1]}/{parts[2]}" if len(parts) == 3 else latest[0]

    return {"price": close, "change": round(change, 2), "changePct": change_pct, "date": date_label}

@app.route("/prices")
def get_prices():
    result = {}
    for code in STOCKS:
        try:
            result[code] = get_price(code)
        except Exception as e:
            result[code] = {"error": str(e)}
    return jsonify(result)

@app.route("/")
def index():
    return "TWSE Price Server is running ✓"

if __name__ == "__main__":
    app.run()
