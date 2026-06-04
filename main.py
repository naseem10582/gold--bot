import os
import requests
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TD_API_KEY = os.getenv("TWELVEDATA_API")

# EMA calculate karne ka function
def calculate_ema(prices, period):
    ema = []
    k = 2 / (period + 1)
    ema.append(sum(prices[:period]) / period) # First EMA = SMA
    for price in prices[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema

# RSI calculate karne ka function
def calculate_rsi(prices, period=14):
    gains, losses = [], []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(prices)-1):
        avg_gain = (avg_gain * (period-1) + gains[i]) / period
        avg_loss = (avg_loss * (period-1) + losses[i]) / period

    rs = avg_gain / avg_loss if avg_loss!= 0 else 100
    rsi = 100 - (100 / (1 + rs))
    return rsi

# Signal generate karne ka function
async def get_signal(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=5min&outputsize=50&apikey={TD_API_KEY}"
    data = requests.get(url).json()

    if "values" not in data:
        return "❌ Data nahi mila. API limit ya symbol galat."

    closes = [float(i["close"]) for i in reversed(data["values"])]
    highs = [float(i["high"]) for i in reversed(data["values"])]
    lows = [float(i["low"]) for i in reversed(data["values"])]

    ema9 = calculate_ema(closes, 9)
    ema21 = calculate_ema(closes, 21)
    rsi = calculate_rsi(closes, 14)

    current_price = closes[-1]
    current_ema9 = ema9[-1]
    current_ema21 = ema21[-1]
    current_rsi = rsi

    # BUY Condition
    if current_ema9 > current_ema21 and 50 < current_rsi < 70 and current_price > current_ema9:
        sl = round(current_ema21 - 2, 2) # 21 EMA ke 2$ neeche
        tp1 = round(current_price + (current_price - sl), 2) # 1:1 RR
        tp2 = round(current_price + 2 * (current_price - sl), 2) # 1:2 RR

        return f"""
🚀 {symbol} BUY SIGNAL

Entry: ${current_price}
Stop Loss: ${sl} [-${round(current_price-sl,2)}]
TP1: ${tp1} [+${round(tp1-current_price,2)}] 1:1
TP2: ${tp2} [+${round(tp2-current_price,2)}] 1:2

Reason: 9EMA>21EMA + RSI {round(current_rsi,1)} + Price above 9EMA
Time: 5min TF
"""

    # SELL Condition
    elif current_ema9 < current_ema21 and 30 < current_rsi < 50 and current_price < current_ema9:
        sl = round(current_ema21 + 2, 2)
        tp1 = round(current_price - (sl - current_price), 2)
        tp2 = round(current_price - 2 * (sl - current_price), 2)

        return f"""
🔻 {symbol} SELL SIGNAL

Entry: ${current_price}
Stop Loss: ${sl} [+${round(sl-current_price,2)}]
TP1: ${tp1} [-${round(current_price-tp1,2)}] 1:1
TP2: ${tp2} [-${round(current_price-tp2,2)}] 1:2

Reason: 9EMA<21EMA + RSI {round(current_rsi,1)} + Price below 9EMA
Time: 5min TF
"""

    else:
        return f"⌛ {symbol} NO SIGNAL\nPrice: ${current_price}\nEMA9: {round(current_ema9,2)} | EMA21: {round(current_ema21,2)} | RSI: {round(current_rsi,1)}\nWait for setup..."

# Telegram Commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ GOLD+ZEC Signal Bot Online\nCommands:\n/gold - XAUUSD Signal\n/zec - ZEC Signal")

async def gold_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Checking GOLD...")
    signal = await get_signal("XAU/USD")
    await update.message.reply_text(signal)

async def zec_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Checking ZEC...")
    signal = await get_signal("ZEC/USD")
    await update.message.reply_text(signal)

# Bot Start
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold_signal))
    app.add_handler(CommandHandler("zec", zec_signal))
    print("Bot Starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
