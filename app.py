from flask import Flask, jsonify, make_response
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

STOCKS = ["2330", "0050"]

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
        raise Exception(f"TWSE HTTP {res.status_code}")
    if not res.text.strip():
        raise Exception("Empty response from TWSE")

    data = res.json()
    if data.get("stat") != "OK" or not data.get("data"):
        raise Exception(f"TWSE stat: {data.get('stat','?')}")

    latest = data["data"][-1]
    # Columns: [date, vol, val, open, high, low, close, change, txn]
    open_p  = float(latest[3].replace(",", ""))
    high    = float(latest[4].replace(",", ""))
    low     = float(latest[5].replace(",", ""))
    close   = float(latest[6].replace(",", ""))
    try:
        change = float(latest[7].replace(",", "").strip())
    except:
        change = 0.0

    prev = close - change
    change_pct = round((change / prev) * 100, 2) if prev > 0 else 0
    parts = latest[0].split("/")
    date_label = f"{parts[1]}/{parts[2]}" if len(parts) == 3 else latest[0]

    return {
        "price":     close,
        "open":      open_p,
        "high":      high,
        "low":       low,
        "change":    round(change, 2),
        "changePct": change_pct,
        "date":      date_label
    }

@app.route("/prices")
def get_prices():
    result = {}
    for code in STOCKS:
        try:
            result[code] = get_price(code)
        except Exception as e:
            result[code] = {"error": str(e)}

    response = make_response(jsonify(result))
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route("/prices", methods=["OPTIONS"])
def prices_options():
    response = make_response("", 200)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route("/")
def index():
    return "TWSE Price Server is running ✓"

if __name__ == "__main__":
    app.run()
