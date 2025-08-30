import time
import logging
from datetime import datetime, timezone
from api.auth import fetch_token_with_retry
from core.get_trade_list import get_trade_list
from core.get_trade_chat import fetch_trade_chat_messages
from core.messaging.welcome_message import send_welcome_message
from core.messaging.payment_details import send_payment_details_message
from core.get_files import load_processed_trades, save_processed_trade
from core.messaging.telegram_alert import send_telegram_alert, send_attachment_alert
from config import CHAT_URL_PAXFUL, CHAT_URL_NOONES, PAYMENT_REMINDER_DELAY
from core.messaging.attachment_message import send_attachment_message
from core.messaging.trade_lifecycle_messages import (
    send_trade_completion_message,
    send_payment_received_message,
    send_payment_reminder_message,
)

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
                trade_status = trade.get("trade_status")
                started_at_str = trade.get("start_date")

                if not trade_hash or not owner_username:
                    logging.error(f"Missing trade_hash or owner_username for trade: {trade}")
                    continue

                if payment_method_name not in payment_methods:
                    payment_methods.add(payment_method_name)
                    logging.info(f"New Payment Method Found for {account['name']}: {payment_method_name}")

                platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
                chat_url = CHAT_URL_PAXFUL if platform == "Paxful" else CHAT_URL_NOONES

                processed_trades = load_processed_trades(owner_username, platform)
                processed_trade_data = processed_trades.get(trade_hash, {})

                if not processed_trade_data:
                    send_telegram_alert(trade, platform)
                    send_welcome_message(trade, account, headers)

                    if payment_method_slug in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios","domestic-wire-transfer"]:
                        send_payment_details_message(trade_hash, payment_method_slug, headers, chat_url, owner_username)

                    processed_trade_data['status_history'] = [trade_status]
                    save_processed_trade(trade, platform, processed_trade_data)

                else:
                    logging.debug(f"Trade {trade_hash} for {owner_username} ({account['name']}) already processed.")

                if trade_status not in processed_trade_data.get('status_history', []):
                    logging.info(f"Trade {trade_hash} has a new status: '{trade_status}'")
                    if trade_status == 'Successful':
                        send_trade_completion_message(trade_hash, account, headers)
                    elif trade_status == 'Paid':
                        send_payment_received_message(trade_hash, account, headers)

                    processed_trade_data.setdefault('status_history', []).append(trade_status)
                    save_processed_trade(trade, platform, processed_trade_data)

                # Fetch chat info once for both reminder and attachment logic
                attachment_found, author, last_buyer_ts = fetch_trade_chat_messages(trade_hash, account, headers)

                # --- New Payment Reminder Logic ---
                if trade_status.startswith('Active') and not processed_trade_data.get('reminder_sent'):
                    reference_time = None
                    # Use the buyer's last message time if available
                    if last_buyer_ts:
                        reference_time = datetime.fromtimestamp(last_buyer_ts, tz=timezone.utc)
                    # Otherwise, fall back to the trade start time
                    elif started_at_str:
                        try:
                            reference_time = datetime.fromisoformat(started_at_str).replace(tzinfo=timezone.utc)
                        except ValueError:
                            logging.error(f"Could not parse start_date '{started_at_str}' for trade {trade_hash}.")

                    # If we have a valid time, check if the delay has passed
                    if reference_time:
                        if (datetime.now(timezone.utc) - reference_time).total_seconds() > PAYMENT_REMINDER_DELAY:
                            logging.info(f"Sending payment reminder for trade {trade_hash} due to inactivity.")
                            send_payment_reminder_message(trade_hash, account, headers)
                            processed_trade_data['reminder_sent'] = True
                            save_processed_trade(trade, platform, processed_trade_data)
                    else:
                        logging.warning(f"Cannot check for reminder for trade {trade_hash}: no valid reference time.")


                # --- Attachment Handling Logic ---
                if attachment_found and not processed_trade_data.get('attachment_message_sent'):
                    logging.info(f"New attachment found for trade {trade_hash}. Sending one-time message.")
                    send_attachment_message(trade_hash, account, headers)
                    send_attachment_alert(trade_hash, author)
                    processed_trade_data['attachment_message_sent'] = True
                    save_processed_trade(trade, platform, processed_trade_data)

        else:
            logging.debug(f"No new trades found for {account['name']}.")

        time.sleep(60)