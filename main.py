import requests
import time
from config import *
from data.get_history import get_trade_history
from data.get_trade_list import get_trade_list
from core.telegram_alert import send_telegram_alert
from core.send_welcome_message import send_welcome_message


def load_processed_trades():
    try:
        with open("processed_trades.txt", "r") as file:
            return set(line.strip() for line in file.readlines())
    except FileNotFoundError:
        return set()


def save_processed_trade(trade_hash):
    with open("processed_trades.txt", "a") as file:
        file.write(trade_hash + "\n")


def main():
    processed_trades = load_processed_trades()

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

                    if trade_hash not in processed_trades:
                        send_telegram_alert(trade)
                        send_welcome_message(trade_hash, headers)
                        save_processed_trade(trade_hash)
                        processed_trades.add(trade_hash)
                    else:
                        print(f"Trade {trade_hash} has already been processed.")
            else:
                print("No new trades found.")

            time.sleep(60)

    else:
        print(f"Error fetching token: {response.status_code} - {response.text}")


if __name__ == "__main__":
    main()
