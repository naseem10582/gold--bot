import requests, time, os
from datetime import datetime, timedelta

BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
API_KEY = os.environ['TWELVEDATA_API_KEY']
CHAT_ID = ""

def is_macro_time():
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    total_min = now.hour * 60 + now.minute
    return 1040 <= total_min <= 1250 or total_min >= 1390 or total_min <= 100

def get_candles(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=15min&outputsize=50&apikey={API_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if 'values' not in data: return None
        return [{'high': float(v['high']),'low': float(v['low']),'close': float(v['close'])} for v in reversed(data['values'])]
    except: return None

def send_msg(text):
    global CHAT_ID
    if not CHAT_ID:
        updates = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates").json()
        if updates.get('result'): CHAT_ID = updates['result'][-1]['message']['chat']['id']
    if CHAT_ID: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'Markdown'})

def check_signals():
    for symbol, name in [('XAU/USD', 'GOLD'), ('ZEC/USD', 'ZEC')]:
        candles = get_candles(symbol)
        if not candles: continue
        price = candles[-1]['close']
        if is_macro_time():
            send_msg(f"✅ *{name} Bot Online*\nPrice: `${price:.2f}`\n_Macro Time Active_")

print("Bot Starting...")
while True:
    check_signals()
    time.sleep(300)
