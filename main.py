import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
TD_KEY = os.getenv("TWELVEDATA_API")

SYMBOLS = {
    "gold": {"td": "XAU/USD", "name": "XAU/USD"},
    "zec": {"td": "ZEC/USD", "name": "ZEC/USD"},
    "btc": {"td": "BTC/USD", "name": "BTC/USD"},
    "us100": {"td": "NDX", "name": "NASDAQ-100"}
}

def get_data(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&outputsize=50&apikey={TD_KEY}"
    r = requests.get(url).json()
    if "values" not in r:
        return None, None
    df = pd.DataFrame(r["values"])
    df = df.astype({"open": float, "high": float, "low": float, "close": float})
    df = df.iloc[::-1]
    df['ema5'] = df['close'].ewm(span=5).mean()
    df['ema13'] = df['close'].ewm(span=13).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df.iloc[-1], df

def make_chart(df, symbol_name):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df['close'], label='Price', color='white', linewidth=2)
    ax.plot(df['ema5
