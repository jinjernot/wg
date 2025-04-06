import logging
from config import WELCOME_MESSAGES, CHAT_URL_PAXFUL, CHAT_URL_NOONES
from core.messaging.message_sender import send_message_with_retry

def send_welcome_message(trade, account, headers, max_retries=3):
    trade_hash = trade.get("trade_hash")
    payment_method_slug = trade.get("payment_method_slug", "").lower()

    chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES
    message = WELCOME_MESSAGES.get(payment_method_slug, WELCOME_MESSAGES["default"])
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    body = {"trade_hash": trade_hash, "message": message}

    if send_message_with_retry(chat_url, body, headers, max_retries):
        print(f"Welcome message sent for trade {trade_hash} ({account['name']})")
    else:
        print(f"sFailed to send welcome message for trade {trade_hash} ({account['name']})")
