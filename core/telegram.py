from config import *
import requests
from data.get_balance import *

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    requests.post(url, json=payload)

def monitor_wallet():
    
    threshold_btc = 0.005
    threshold_usdt = 50 
    while True:
        balance = get_wallet_balance()
        
        if balance and "data" in balance:
            btc_balance = float(balance["data"].get("BTC", 0))
            usdt_balance = float(balance["data"].get("USDT", 0))

            if btc_balance < threshold_btc:
                send_telegram_alert(f"⚠️ Low BTC Balance: {btc_balance} BTC")

            if usdt_balance < threshold_usdt:
                send_telegram_alert(f"⚠️ Low USDT Balance: {usdt_balance} USDT")

        time.sleep(300)