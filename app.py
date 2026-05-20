from flask import Flask, jsonify, make_response
from flask_cors import CORS
import requests
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

STOCKS = ["2330", "0050"]
TW_TZ = pytz.timezone("Asia/Taipei")

HEADERS_TWSE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.twse.com.tw/zh/trading/historical/stock-day.html",
    "X-Requested-With": "XMLHttpRequest",
}

HEADERS_MIS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://mis.twse.com.tw/stock/index.jsp",
}

def get_market_session():
    """Return current Taiwan market session"""
    now = datetime.now(TW_TZ)
    hour = now.hour
    minute = now.minute
    total_minutes = hour * 60 + minute

    # Mon-Fri only
    if now.weekday() >= 5:
        return "closed_weekend"

    if total_minutes < 9 * 60:          # Before 9:00am
        return "pre_market"
    elif total_minutes < 11 * 60 + 30:  # 9:00am - 11:30am
        return "morning"
    elif total_minutes < 13 * 60 + 30:  # 11:30am - 1:30pm
        return "lunch"
    elif total_minutes < 15 * 60:       # 1:30pm - 3:00pm (data processing)
        return "post_close"
    else:                                # After 3:00pm
        return "closed"

def get_eod_price(stock_no):
    """Fetch end-of-day closing price from TWSE historical API"""
    today = datetime.now(TW_TZ).strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={today}&stockNo={stock_no}"
    res = requests.get(url, timeout=10, headers=HEADERS_TWSE)

    if not res.text.strip():
        raise Exception("Empty response from TWSE")

    data = res.json()
    if data.get("stat") != "OK" or not data.get("data"):
        raise Exception(f"TWSE stat: {data.get('stat','?')}")

    latest = data["data"][-1]
    # Columns: [date, vol, val, open, high, low, close, change, txn]
    open_p = float(latest[3].replace(",", ""))
    high   = float(latest[4].replace(",", ""))
    low    = float(latest[5].replace(",", ""))
    close  = float(latest[6].replace(",", ""))
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
        "date":      date_label,
    }

def get_intraday_price(stock_no):
    """Fetch live intraday price from TWSE MIS API"""
    symbol = f"tse_{stock_no}.tw"
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={symbol}&json=1&delay=0"
    res = requests.get(url, timeout=10, headers=HEADERS_MIS)

    if not res.text.strip():
        raise Exception("Empty MIS response")

    data = res.json()
    items = data.get("msgArray", [])
    if not items:
        raise Exception("No MIS data")

    item = items[0]
    # z = current price, y = yesterday close, o = open, h = high, l = low
    def safe_float(val):
        try:
            return float(str(val).replace(",", ""))
        except:
            return None

    current = safe_float(item.get("z")) or safe_float(item.get("y"))
    prev    = safe_float(item.get("y")) or 0
    open_p  = safe_float(item.get("o")) or current
    high    = safe_float(item.get("h")) or current
    low     = safe_float(item.get("l")) or current

    change     = round(current - prev, 2) if current and prev else 0
    change_pct = round((change / prev) * 100, 2) if prev > 0 else 0

    now_tw     = datetime.now(TW_TZ)
    date_label = now_tw.strftime("%m/%d")

    return {
        "price":     current,
        "open":      open_p,
        "high":      high,
        "low":       low,
        "change":    change,
        "changePct": change_pct,
        "date":      date_label,
    }

@app.route("/prices")
def get_prices():
    session = get_market_session()
    now_tw  = datetime.now(TW_TZ)

    # Determine session label for the app to display
    if session == "pre_market":
        session_label = "盤前"
        session_desc  = "早盤前 — 顯示昨日收盤"
    elif session == "morning":
        session_label = "早盤"
        session_desc  = f"早盤進行中 {now_tw.strftime('%H:%M')}"
    elif session == "lunch":
        session_label = "午盤"
        session_desc  = f"午盤進行中 {now_tw.strftime('%H:%M')}"
    elif session == "post_close":
        session_label = "盤後"
        session_desc  = "收盤後，等待官方數據"
    elif session == "closed_weekend":
        session_label = "休市"
        session_desc  = "週末休市 — 顯示上週五收盤"
    else:
        session_label = "收盤"
        session_desc  = f"收盤 {now_tw.strftime('%m/%d')} 官方數據"

    result = {
        "session":      session_label,
        "sessionDesc":  session_desc,
        "time":         now_tw.strftime("%H:%M"),
    }

    for code in STOCKS:
        try:
            # Use intraday during market hours, EOD otherwise
            if session in ("morning", "lunch"):
                try:
                    result[code] = get_intraday_price(code)
                    result[code]["source"] = "intraday"
                except:
                    # Fallback to EOD if intraday fails
                    result[code] = get_eod_price(code)
                    result[code]["source"] = "eod_fallback"
            else:
                result[code] = get_eod_price(code)
                result[code]["source"] = "eod"
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
    now_tw  = datetime.now(TW_TZ)
    session = get_market_session()
    return f"TWSE Price Server ✓ | Taiwan Time: {now_tw.strftime('%Y-%m-%d %H:%M')} | Session: {session}"

if __name__ == "__main__":
    app.run()
