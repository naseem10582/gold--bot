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
    "zec": {"td": "ZEC/USD", "name": "ZEC/USD"},
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
        loss = (-delta.where(delta < 0
