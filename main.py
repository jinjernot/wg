import requests
import time
import threading

from config import (
    NOONES_API_KEY_JOE, NOONES_SECRET_KEY_JOE,
    NOONES_API_KEY_DAVID, NOONES_SECRET_KEY_DAVID, TOKEN_URL
)
from data.get_trade_list import get_trade_list
from core.telegram_alert import send_telegram_alert
from core.send_welcome_message import send_welcome_message
from data.get_files import load_processed_trades, save_processed_trade

# Account configurations
ACCOUNTS = [
    {"name": "Joe", "api_key": NOONES_API_KEY_JOE, "secret_key": NOONES_SECRET_KEY_JOE},
    {"name": "David", "api_key": NOONES_API_KEY_DAVID, "secret_key": NOONES_SECRET_KEY_DAVID},
]

def process_trades(account):
    processed_trades = {}
    payment_methods = set()

    token_data = {
        "grant_type": "client_credentials",
        "client_id": account["api_key"],
        "client_secret": account["secret_key"]
    }

    response = requests.post(TOKEN_URL, data=token_data)
    if response.status_code == 200:
        access_token = response.json().get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}

        while True:
            print(f"Checking for new trades for {account['name']}...")

            trades = get_trade_list(headers, limit=10, page=1)

            if trades:
                for trade in trades:
                    trade_hash = trade.get("trade_hash")
                    owner_username = trade.get("owner_username", "unknown_user")
                    payment_method_name = trade.get("payment_method_name", "Unknown")

                    if payment_method_name not in payment_methods:
                        payment_methods.add(payment_method_name)
                        print(f"New Payment Method Found for {account['name']}: {payment_method_name}")

                    # Load processed trades for this user
                    processed_trades = load_processed_trades(owner_username)

                    if trade_hash not in processed_trades:
                        send_telegram_alert(trade)
                        send_welcome_message(trade, headers)
                        save_processed_trade(trade)
                    else:
                        print(f"Trade {trade_hash} for {owner_username} ({account['name']}) has already been processed.")
            else:
                print(f"No new trades found for {account['name']}.")

            time.sleep(60)

    else:
        print(f"Error fetching token for {account['name']}: {response.status_code} - {response.text}")

def main():
    threads = []
    for account in ACCOUNTS:
        thread = threading.Thread(target=process_trades, args=(account,))
        thread.start()
        threads.append(thread)

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
