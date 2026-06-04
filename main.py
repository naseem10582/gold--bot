import os
import requests
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import hmac
import hashlib
import time
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

print("Starting Delta Auto Bot...")

TOKEN = os.getenv("TELEGRAM_TOKEN")
TD_KEY = os.getenv("TWELVEDATA_API")
DELTA_KEY = os.getenv("DELTA_API_KEY")
DELTA_SECRET = os.getenv("DELTA_SECRET")
CHAT_ID = os.getenv("CHAT_ID")

if not all([TOKEN, TD_KEY, CHAT_ID]):
    print("ERROR: TELEGRAM_TOKEN, TWELVEDATA_API, CHAT_ID chahiye")
    exit()

SYMBOLS = {
    "gold": {"td": "XAU/USD", "name": "XAU/USD", "delta": "GOLDUSD", "qty": 0.1}, 
    "btc": {"td": "BTC/USD", "name": "BTC/USD", "delta": "BTCUSD", "qty": 0.001},
    "luna": {"td": "LUNAUSD", "name": "LUNA/USD", "delta": "LUNAUSD", "qty": 1}
}

def delta_place_order(product_symbol, side, size, stop_price=None, limit_price=None):
    if not DELTA_KEY: return "Delta API keys missing"
    try:
        timestamp = str(int(time.time()))
        method = 'POST'
        path = '/v2/orders'
        body = {
            "product_symbol": product_symbol,
            "size": size,
            "side": side.lower(),
            "order_type": "market_order"
        }
        if stop_price and limit_price:
            body["bracket_stop_loss_price"] = str(stop_price)
            body["bracket_take_profit_price"] = str(limit_price)
        
        body_str = json.dumps(body, separators=(',', ':'))
        signature_data = method + timestamp + path + body_str
        signature = hmac.new(DELTA_SECRET.encode(), signature_data.encode(), 'sha256').hexdigest()
        headers = {'api-key': DELTA_KEY, 'timestamp': timestamp, 'signature': signature, 'Content-Type': 'application/json'}
        url = f"https://api.delta.exchange{path}"
        r = requests.post(url, headers=headers, data=body_str, timeout=10).json()
        return f"Order ID: {r['result']['id']}" if r.get('success') else f"Error: {r.get('error')}"
    except Exception as e:
        return f"Exception: {e}"

def get_data(symbol):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=15min&outputsize=50&apikey={TD_KEY}"
        r = requests.get(url, timeout=10).json()
        if "values" not in r: return None, None
        df = pd.DataFrame(r["values"]).astype({"open": float, "high": float, "low": float, "close": float}).iloc[::-1]
        df["ema5"] = df["close"].ewm(span=5).mean()
        df["ema13"] = df["close"].ewm(span=13).mean()
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
        df["rsi"] = 100 - (100 / (1 + gain / loss))
        return df.iloc[-1], df
    except: return None, None

def make_chart(df, symbol_name):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["close"], label="Price", color="white", linewidth=2)
    ax.plot(df["ema5"], label="EMA5", color="cyan")
    ax.plot(df["ema13"], label="EMA13", color="yellow")
    ax.set_title(f"{symbol_name} - 15min", color="white", fontsize=16)
    ax.legend()
    ax.grid(True, alpha=0.3)
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    plt.close()
    return buf

def calc_signal(row, pair):
    price, ema5, ema13, rsi = row["close"], row["ema5"], row["ema13"], row["rsi"]
    sl_dist = {"XAU/USD": 6.0, "BTC/USD": 250.0, "LUNA/USD": 0.015}.get(pair, 6.0)
    rr = 5
    if ema5 > ema13 and rsi > 55:
        return "BUY", price, round(price - sl_dist, 4), round(price + sl_dist * rr, 4), rsi
    elif ema5 < ema13 and rsi < 45:
        return "SELL", price, round(price + sl_dist, 4), round(price - sl_dist * rr, 4), rsi
    return None, price, 0, 0, rsi

async def auto_check(context: ContextTypes.DEFAULT_TYPE):
    print("Running auto check...")
    for key, info in SYMBOLS.items():
        row, df = get_data(info["td"])
        if row is None: continue
        signal, price, sl, tp, rsi = calc_signal(row, info["name"])
        if signal:
            text = f"🤖 AUTO SIGNAL\n⚡ {info['name']} {signal}\nEntry: {price:.4f}\nSL: {sl} | TP: {tp}\nRSI: {rsi:.1f} | RR 1:5"
            order = delta_place_order(info["delta"], signal, info["qty"], sl, tp)
            text += f"\n\nDelta: {order}"
            chart = make_chart(df.tail(30), info["name"])
            await context.bot.send_photo(chat_id=CHAT_ID, photo=chart, caption=text)

async def manual_signal(update: Update, context: ContextTypes.DEFAULT_TYPE, pair_key):
    info = SYMBOLS[pair_key]
    row, df = get_data(info["td"])
    if row is None:
        await update.message.reply_text("Data error")
        return
    signal, price, sl, tp, rsi = calc_signal(row, info["name"])
    if signal:
        text = f"⚡ {info['name']} {signal}\nEntry:
