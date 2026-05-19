from flask import Flask, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)  # This allows your portfolio app to call this server

STOCKS = ["2330", "0050"]

@app.route("/prices")
def get_prices():
    result = {}
    for code in STOCKS:
        try:
            url = f"https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY?stockNo={code}"
            res = requests.get(url, timeout=10)
            rows = res.json()
            latest = rows[-1]  # Last row = most recent trading day

            close = float(latest["ClosingPrice"].replace(",", ""))

            # Parse change field (may have ▲ ▼ or +/-)
            raw = latest["Change"].replace(",", "").strip()
            if "▼" in raw or raw.startswith("-"):
                change = -float(raw.replace("▼", "").replace("-", "").strip())
            else:
                change = float(raw.replace("▲", "").replace("+", "").strip() or "0")

            prev = close - change
            change_pct = round((change / prev) * 100, 2) if prev > 0 else 0

            # Convert ROC date e.g. "1150518" → "05/18"
            d = latest["Date"]
            date_label = f"{d[3:5]}/{d[5:7]}" if len(d) >= 7 else d

            result[code] = {
                "price": close,
                "change": round(change, 2),
                "changePct": change_pct,
                "date": date_label
            }
        except Exception as e:
            result[code] = {"error": str(e)}

    return jsonify(result)

@app.route("/")
def index():
    return "TWSE Price Server is running ✓"

if __name__ == "__main__":
    app.run()
