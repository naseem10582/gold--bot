import os
import requests
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

print("Starting bot...")

TOKEN = os.getenv("TELEGRAM_TOKEN")
TD_KEY = os.getenv("TWELVEDATA_API")

if not TOKEN:
    print("ERROR: TELEGRAM_TOKEN missing")
    exit()
if not TD_KEY:
    print("ERROR: TWELVEDATA_API missing") 
    exit()

print("Env variables OK")

SYMBOLS = {
    "gold": {"td": "XAU/USD", "name": "XAU/USD"},
    "zec": {"td": "ZECUSD", "name": "ZEC/USD"},
    "btc": {"td": "BTC/USD", "name": "BTC/USD"},
    "us100": {"td": "NDX", "name": "NASDAQ-100"}
}

def get_data(symbol):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&outputsize=50&apikey={TD_KEY}"
        r = requests.get(url, timeout=10).json()
        if "values" not in r:
            print(f"API Error: {r}")
            return None, None
        df = pd.DataFrame(r["values"])
        df = df.astype({"open": float, "high": float, "low": float, "close": float})
        df = df.iloc[::-1]
        df["ema5"] = df["close"].ewm(span=5).mean()
        df["ema13"] = df["close"].ewm(span=13).mean()
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(7).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))
        return df.iloc[-1], df
    except Exception as e:
        print(f"get_data error: {e}")
        return None, None

def make_chart(df, symbol_name):
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["close"], label="Price", color="white", linewidth=2)
    ax.plot(df["ema5"], label="EMA5", color="cyan", linewidth=1.5)
    ax.plot(df["ema13"], label="EMA13", color="yellow", linewidth=1.5)
    ax.set_title(f"{symbol_name} - 5min SCALP", color="white", fontsize=16)
    ax.legend()
    ax.grid(True, alpha=0.3)
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    plt.close()
    return buf

def calc_signal(row, pair):
    price = row["close"]
    ema5, ema13, rsi = row["ema5"], row["ema13"], row["rsi"]
    
    # SL distances
    if pair == "XAU/USD": sl_dist = 4.0
    elif pair == "ZEC/USD": sl_dist = 2.5
    elif pair == "BTC/USD": sl_dist = 150.0
    elif pair == "NASDAQ-100": sl_dist = 25.0
    else: sl_dist = 4.0
    
    rr_ratio = 5  # 1:5 RR
    
    if ema5 > ema13 and rsi > 55:
        sl = price - sl_dist
        tp = price + sl_dist * rr_ratio
        text = "⚡ {} 5M SCALP BUY\nEntry: {:.2f}\nSL: {:.2f}\nTP: {:.2f}\nRSI: {:.1f} | RR 1:5".format(pair, price, sl, tp, rsi)
        return text
    elif ema5 < ema13 and rsi < 45:
        sl = price + sl_dist
        tp = price - sl_dist * rr_ratio
        text = "⚡ {} 5M SCALP SELL\nEntry: {:.2f}\nSL: {:.2f}\nTP: {:.2f}\nRSI: {:.1f} | RR 1:5".format(pair, price, sl, tp, rsi)
        return text
    else:
        text = "⏳ {} NO SCALP\nPrice: {:.2f}\nEMA5: {:.2f} | EMA13: {:.2f} | RSI: {:.1f}".format(pair, price, ema5, ema13, rsi)
        return text

async def send_signal(update: Update, context: ContextTypes.DEFAULT_TYPE, pair_key):
    symbol_info = SYMBOLS[pair_key]
    row, df = get_data(symbol_info["td"])
    if row is None:
        await update.message.reply_text("Error: Data nahi mila. API key ya symbol check kar.")
        return
    signal_text = calc_signal(row, symbol_info["name"])
    chart = make_chart(df.tail(30), symbol_info["name"])
    await update.message.reply_photo(photo=chart, caption=signal_text)

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_signal(update, context, "gold")
async def zec(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_signal(update, context, "zec")
async def btc(update: Update, context
