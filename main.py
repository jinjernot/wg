import requests
import time
import threading
import logging
from config import TOKEN_URL_NOONES, TOKEN_URL_PAXFUL, ACCOUNTS
from data.get_trade_list import get_trade_list
from core.telegram_alert import send_telegram_alert
from core.send_welcome_message import send_welcome_message
from data.get_files import load_processed_trades, save_processed_trade

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def fetch_token_with_retry(account, max_retries=3):
    """Fetch an access token with retry logic, handling different APIs for Noones and Paxful."""
    
    # Determine which API to use
    if "_Paxful" in account["name"]:
        token_url = TOKEN_URL_PAXFUL
        token_data = {
            "grant_type": "client_credentials",
            "client_id": account["api_key"],
            "client_secret": account["secret_key"]
        }
        print("si salio paxful")
    else:
        token_url = TOKEN_URL_NOONES
        token_data = {
            "grant_type": "client_credentials",
            "client_id": account["api_key"],
            "client_secret": account["secret_key"]
        }

    for attempt in range(max_retries):
        try:
            logging.debug(f"Attempt {attempt + 1} of {max_retries} to fetch token for {account['name']} using {token_url}")
            response = requests.post(token_url, data=token_data, timeout=10)
            
            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                logging.error(f"Failed to fetch token for {account['name']}. Status Code: {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logging.debug(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error("Max retries reached. Giving up.")
                    return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logging.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                logging.error("Max retries reached. Giving up.")
                return None
    return None

def process_trades(account):
    processed_trades = {}
    payment_methods = set()

    access_token = fetch_token_with_retry(account)
    if not access_token:
        logging.error(f"Failed to fetch access token for {account['name']}. Skipping account.")
        return

    headers = {"Authorization": f"Bearer {access_token}"}

    while True:
        logging.debug(f"Checking for new trades for {account['name']}...")

        trades = get_trade_list(account, headers, limit=10, page=1)

        if trades:
            for trade in trades:
                trade_hash = trade.get("trade_hash")
                owner_username = trade.get("owner_username", "unknown_user")
                payment_method_name = trade.get("payment_method_name", "Unknown")

                if payment_method_name not in payment_methods:
                    payment_methods.add(payment_method_name)
                    logging.info(f"New Payment Method Found for {account['name']}: {payment_method_name}")

                # Determine platform for the alert based on account name
                platform = "Paxful" if "_Paxful" in account["name"] else "Noones"

                processed_trades = load_processed_trades(owner_username, platform)

                if trade_hash not in processed_trades:
                    send_telegram_alert(trade, platform)
                    send_welcome_message(trade, account, headers)
                    save_processed_trade(trade, platform)
                else:
                    logging.debug(f"Trade {trade_hash} for {owner_username} ({account['name']}) has already been processed.")
        else:
            logging.debug(f"No new trades found for {account['name']}.")
        
        time.sleep(60)
        
def main():
    threads = []
    for account in ACCOUNTS:
        thread = threading.Thread(target=process_trades, args=(account,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()
