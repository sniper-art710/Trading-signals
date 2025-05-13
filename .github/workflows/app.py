from flask import Flask, render_template, request, jsonify
from tradingview_ta import TA_Handler, Interval
import requests

app = Flask(__name__)

# Constants
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5

# Trading pairs list
pairs = [
    ("BTCUSD", "crypto", "BINANCE"),
    ("USDJPY", "forex", "FX_IDC"),
    ("EURUSD", "forex", "FX_IDC"),
    ("AUDUSD", "forex", "FX_IDC"),
]

# Get price for forex pair
def get_forex_price(pair, api_key):
    try:
        url = f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={pair[:3]}&to_currency={pair[3:]}&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        rate_info = data.get("Realtime Currency Exchange Rate", {})
        return float(rate_info["5. Exchange Rate"])
    except Exception:
        return None

# Get ATR value
def get_atr_value(symbol, api_key):
    try:
        url = f"https://www.alphavantage.co/query?function=ATR&symbol={symbol}&interval=30min&time_period={ATR_PERIOD}&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        atr_data = data.get("Technical Analysis: ATR", {})
        if atr_data:
            latest_time = sorted(atr_data.keys())[-1]
            return float(atr_data[latest_time]["ATR"])
        return None
    except:
        return None

# Get BTC price
def get_btc_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        response = requests.get(url)
        return float(response.json()["price"])
    except:
        return None

# Home route
@app.route('/')
def index():
    return render_template('index.html', pairs=[p[0] for p in pairs])

# Signal API - only return one signal based on requested pair
@app.route('/signal', methods=['POST'])
def signal():
    data = request.json
    api_key = data.get("api_key")
    requested_pair = data.get("pair")

    if not api_key or not requested_pair:
        return jsonify({"error": "API key and pair are required."}), 400

    # Find the matching pair in the config
    match = next((p for p in pairs if p[0] == requested_pair), None)
    if not match:
        return jsonify({"error": "Invalid trading pair."}), 400

    pair, screener, exchange = match

    entry_price = get_btc_price() if pair == "BTCUSD" else get_forex_price(pair, api_key)
    if not entry_price:
        return jsonify({"pair": pair, "error": "Price unavailable."})

    atr = get_atr_value(pair, api_key)
    if not atr:
        return jsonify({"pair": pair, "error": "ATR unavailable."})

    precision = 2 if pair == "BTCUSD" or "JPY" in pair else 4

    try:
        handler = TA_Handler(
            symbol=pair,
            screener=screener,
            exchange=exchange,
            interval=Interval.INTERVAL_30_MINUTES
        )
        analysis = handler.get_analysis()
        original = analysis.summary["RECOMMENDATION"]
        recommendation = "SELL" if original == "BUY" else "BUY" if original == "SELL" else original
    except:
        recommendation = "Analysis failed"

    # TP and SL logic
    if recommendation == "BUY":
        tp = round(entry_price + atr * ATR_MULTIPLIER, precision)
        sl = round(entry_price - atr * ATR_MULTIPLIER, precision)
    elif recommendation == "SELL":
        tp = round(entry_price - atr * ATR_MULTIPLIER, precision)
        sl = round(entry_price + atr * ATR_MULTIPLIER, precision)
    else:
        tp = round(entry_price, precision)
        sl = round(entry_price, precision)

    return jsonify({
        "pair": pair,
        "entry": entry_price,
        "atr": atr,
        "tp": tp,
        "sl": sl,
        "recommendation": recommendation
    })

if __name__ == '__main__':
    app.run(debug=True)