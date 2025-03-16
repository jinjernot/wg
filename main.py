import requests
import time
import json
from config import *
from data.get_history import get_trade_history
from data.get_trade_list import get_trade_list
from core.telegram_alert import send_telegram_alert
from core.send_welcome_message import send_welcome_message



def load_processed_trades():
    """ Load previously processed trades from a JSON file. """
    try:
        with open(TRADES_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_processed_trade(trade):
    """ Save processed trades to a JSON file. """
    trades = load_processed_trades()
    trade_hash = trade.get("trade_hash")
    
    trades[trade_hash] = trade  # Save full trade data

    with open(TRADES_FILE, "w") as file:
        json.dump(trades, file, indent=4)

def main():
    processed_trades = load_processed_trades()
    payment_methods = set()

    token_url = "https://auth.noones.com/oauth2/token"
    token_data = {
        "grant_type": "client_credentials",
        "client_id": NOONES_API_KEY,
        "client_secret": NOONES_SECRET_KEY
    }

    response = requests.post(token_url, data=token_data)
    if response.status_code == 200:
        access_token = response.json().get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}

        while True:
            print("Checking for new trades...")

            trades = get_trade_list(headers, limit=10, page=1)

            if trades:
                for trade in trades:
                    trade_hash = trade.get("trade_hash")
                    payment_method_name = trade.get("payment_method_name", "Unknown")

                    if payment_method_name not in payment_methods:
                        payment_methods.add(payment_method_name)
                        print(f"New Payment Method Found: {payment_method_name}")

                    if trade_hash not in processed_trades:
                        send_telegram_alert(trade)
                        send_welcome_message(trade, headers)
                        save_processed_trade(trade)  # Save trade details
                        processed_trades[trade_hash] = trade  # Add to in-memory cache
                    else:
                        print(f"Trade {trade_hash} has already been processed.")
            else:
                print("No new trades found.")

            time.sleep(60)

    else:
        print(f"Error fetching token: {response.status_code} - {response.text}")

if __name__ == "__main__":
    main()
