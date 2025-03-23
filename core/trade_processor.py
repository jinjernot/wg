import time
import logging
from api.auth import fetch_token_with_retry
from core.get_trade_list import get_trade_list
from core.telegram_alert import send_telegram_alert
from core.send_welcome_message import send_welcome_message
from core.get_files import load_processed_trades, save_processed_trade

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def process_trades(account):
    """Handles trade processing logic, fetching new trades, and sending notifications."""
    processed_trades = {}
    payment_methods = set()

    # Fetch API token
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
