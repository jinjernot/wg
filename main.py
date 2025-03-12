from data.get_trades import *
from core.telegram import *

from config import *

def check_new_trades():
    while True:
        paxful_trades = fetch_paxful_trades()
        noones_trades = fetch_noones_trades()

        if paxful_trades:
            for trade in paxful_trades.get("data", []):
                message = f"Paxful Trade Alert:\nTrade ID: {trade['trade_id']}\nStatus: {trade['status']}"
                send_telegram_alert(message)

        if noones_trades:
            for trade in noones_trades.get("data", []):
                message = f"Noones Trade Alert:\nTrade ID: {trade['trade_id']}\nStatus: {trade['status']}"
                send_telegram_alert(message)

        time.sleep(60)

if __name__ == "__main__":
    check_new_trades()