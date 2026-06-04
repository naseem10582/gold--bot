import os
import requests
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
TD_KEY = os.getenv("TWELVEDATA_API")

# Sab pairs yahan add kar
SYMBOLS = {
    "gold": {"td": "XAU/USD", "name": "XAU/USD"},
    "zec": {"td": "ZEC/USD", "name": "ZEC/USD"},
    "btc": {"td": "BTC/USD", "name": "BTC/USD"},
    "us100": {"td": "NDX", "name": "NASDAQ-100"}
}

def get_data(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=15min&outputsize=50&apikey={TD_KEY}"
    r = requests.get(url).json()
    if "values" not in r: return None, None
    df = pd.DataFrame(r["values"])
    df = df.astype({"open": float, "high": float, "low": float, "close": float})
    df = df.iloc[::-1] # reverse to old->new
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df.iloc[-1], df

def make_chart(df, symbol_name):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10,6))
    ax.plot(df['close'], label='Price', color='white', linewidth=2)
    ax.plot(df['ema9'], label='EMA9', color='cyan', linewidth=1.5)
    ax.plot(df['ema21'], label='EMA21', color='yellow', linewidth=1.5)
    ax.set_title(f'{symbol_name} - 15min', color='white', fontsize=16)
    ax.legend()
    ax.grid(True, alpha=0.3)
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close()
    return buf

def calc_signal(row, pair):
    price = row['close']
    ema9, ema21, rsi = row['ema9'], row['ema21'], row['rsi']

    # Gold aur Index ke liye SL/TP alag
    pip_value = 1 if "USD" in pair else 10
    sl_pips = 100 if pair == "XAU/USD" else 200

    if ema9 > ema21 and rsi > 50:
        sl = price - sl_pips * pip_value
        tp1 = price + sl_pips * pip_value
        tp2 = price + 2 * sl_pips * pip_value
        return f"🚀 {pair} BUY SIGNAL\nEntry: {price:.2f}\nSL: {sl:.2f}\nTP1: {tp1:.2f}\nTP2: {tp2:.2f}\nRSI: {rsi:.1f}"

    elif ema9 < ema21 and rsi < 50:
        sl = price + sl_pips * pip_value
        tp1 = price - sl_pips * pip_value
        tp2 = price - 2 * sl_pips * pip_value
        return f"🔻 {pair} SELL SIGNAL\nEntry: {price:.2f}\nSL: {sl:.2f}\nTP1: {tp1:.2f}\nTP2: {tp2:.2f}\nRSI: {rsi:.1f}"

    else:
        return f"⏳ {pair} NO SIGNAL\nPrice: {price:.2f}\nEMA9: {ema9:.2f} | EMA21: {ema21:.2f} | RSI: {rsi:.1f}\nWait for setup..."

async def send_signal(update: Update, context: ContextTypes.DEFAULT_TYPE, pair_key):
    symbol_info = SYMBOLS[pair_key]
    row, df = get_data(symbol_info["td"])
    if row is None:
        await update.message.reply_text("Error: Data nahi mila. API limit check kar.")
        return

    signal_text = calc_signal(row, symbol_info["name"])
    chart = make_chart(df.tail(30), symbol_info["name"])
    await update.message.reply_photo(photo=chart, caption=signal_text)

async def gold(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_signal(update, context, "gold")
async def zec(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_signal(update, context, "zec")
async def btc(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_signal(update, context, "btc")
async def us100(update: Update, context: ContextTypes.DEFAULT_TYPE): await send_signal(update, context, "us100")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ GoldZec Signals Pro Bot Online\nCommands:\n/gold - XAUUSD\n/zec - ZEC\n/btc - BTC\n/us100 - NASDAQ\n\nAuto alerts har 5 min mein ON hai")

async def check_all_auto(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    for key in SYMBOLS:
        symbol_info = SYMBOLS[key]
        row, df = get_data(symbol_info["td"])
        if row is None: continue
        signal = calc_signal(row, symbol_info["name"])
        if "SIGNAL" in signal and "NO SIGNAL" not in signal:
            chart = make_chart(df.tail(30), symbol_info["name"])
            await context.bot.send_photo(chat_id=chat_id, photo=chart, caption=f"🔔 AUTO ALERT\n{signal}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gold", gold))
    app.add_handler(CommandHandler("zec", zec))
    app.add_handler(CommandHandler("btc", btc))
    app.add_handler(CommandHandler("us100", us100))

    # Auto alert setup - pehle /start karna padega ek baar
    # job_queue = app.job_queue
    # job_queue.run_repeating(check_all_auto, interval=300, first=10)

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
