from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

STOCKS = ["2330", "0050"]

def get_price(stock_no):
    today = datetime.now().strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={today}&stockNo={stock_no}"
    res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    data = res.json()

    if data.get("stat") != "OK" or not data.get("data"):
        raise Exception(f"No data for {stock_no}: {data.get('stat')}")

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
