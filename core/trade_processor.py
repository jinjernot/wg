import time
import logging
from api.auth import fetch_token_with_retry
from core.get_trade_list import get_trade_list
from core.get_trade_chat import fetch_trade_chat_messages
from core.messaging.welcome_message import send_welcome_message
from core.messaging.payment_details import send_payment_details_message
from core.get_files import load_processed_trades, save_processed_trade
from core.messaging.telegram_alert import send_telegram_alert
from config import CHAT_URL_PAXFUL, CHAT_URL_NOONES

logging.basicConfig(level=logging.DEBUG)

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
                payment_method_slug = trade.get("payment_method_slug", "").lower()
                payment_method_name = trade.get("payment_method_name", "Unknown")

                # Debug log to check if trade_hash and owner_username are valid
                logging.debug(f"Trade data - trade_hash: {trade_hash}, owner_username: {owner_username}, payment_method_slug: {payment_method_slug}")

                # Check if valid trade_hash exists
                if not trade_hash or not owner_username:
                    logging.error(f"Missing trade_hash or owner_username for trade: {trade}")
                    continue

                if payment_method_name not in payment_methods:
                    payment_methods.add(payment_method_name)
                    logging.info(f"New Payment Method Found for {account['name']}: {payment_method_name}")

                platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
                chat_url = CHAT_URL_PAXFUL if platform == "Paxful" else CHAT_URL_NOONES

                processed_trades = load_processed_trades(owner_username, platform)

                if trade_hash not in processed_trades:
                    send_telegram_alert(trade, platform)
                    send_welcome_message(trade, account, headers)

                    # Send payment details after the welcome message, passing the owner username
                    if payment_method_slug in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios","domestic-wire-transfer"]:
                        send_payment_details_message(trade_hash, payment_method_slug, headers, chat_url, owner_username)

                    save_processed_trade(trade, platform)
                    
                else:
                    logging.debug(f"Trade {trade_hash} for {owner_username} ({account['name']}) already processed.")
                
                # Optional: Keep reading chat messages even for old trades
                fetch_trade_chat_messages(trade_hash, account, headers)

        else:
            logging.debug(f"No new trades found for {account['name']}.")
        
        time.sleep(60)