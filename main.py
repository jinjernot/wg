import requests
import time
import json
import os
from config import *
from data.get_history import get_trade_history
from data.get_trade_list import get_trade_list
from core.telegram_alert import send_telegram_alert
from core.send_welcome_message import send_welcome_message



def ensure_trade_storage():
    """ Ensure the trade storage directory exists. """
    if not os.path.exists(TRADE_STORAGE_DIR):
        os.makedirs(TRADE_STORAGE_DIR)

def load_processed_trades(owner_username):
    """ Load previously processed trades for a specific owner. """
    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}.json")
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_processed_trade(trade):
    """ Save processed trades separately based on owner_username. """
    ensure_trade_storage()
    
    owner_username = trade.get("owner_username", "unknown_user")  # Default if no username found
    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}.json")

    trades = load_processed_trades(owner_username)
    trade_hash = trade.get("trade_hash")
    
    trades[trade_hash] = trade  # Store trade details

    with open(file_path, "w") as file:
        json.dump(trades, file, indent=4)

def main():
    ensure_trade_storage()
    processed_trades = {}
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
                    owner_username = trade.get("owner_username", "unknown_user")
                    payment_method_name = trade.get("payment_method_name", "Unknown")

                    if payment_method_name not in payment_methods:
                        payment_methods.add(payment_method_name)
                        print(f"New Payment Method Found: {payment_method_name}")

                    # Load processed trades for this user
                    processed_trades = load_processed_trades(owner_username)

                    if trade_hash not in processed_trades:
                        send_telegram_alert(trade)
                        send_welcome_message(trade, headers)
                        save_processed_trade(trade)
                    else:
                        print(f"Trade {trade_hash} for {owner_username} has already been processed.")
            else:
                print("No new trades found.")

            time.sleep(60)

    else:
        print(f"Error fetching token: {response.status_code} - {response.text}")

if __name__ == "__main__":
    main()
