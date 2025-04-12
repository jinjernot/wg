import logging
from core.messaging.message_sender import send_message_with_retry
from config import *

def send_welcome_message(trade, account, headers, max_retries=3):
    trade_hash = trade.get("trade_hash")
    payment_method_slug = trade.get("payment_method_slug", "").lower()
    owner_username = trade.get("owner_username", "unknown_user")

    # Select the appropriate message dictionary based on the owner username
    if owner_username == "davidvs":
        message_dict = WELCOME_MESSAGES_DAVID
    elif owner_username == "JoeWillgang":
        message_dict = WELCOME_MESSAGES_JOE
    else:
        message_dict = WELCOME_MESSAGES_DAVID  # Default to David's messages (or set a general default if needed)

    # Get the appropriate message for the payment method
    message = message_dict.get(payment_method_slug, message_dict["default"])

    # Determine which chat URL to use based on account type
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES

    # Prepare the message body
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    body = {"trade_hash": trade_hash, "message": message}

    # Send the message with retry logic
    if send_message_with_retry(chat_url, body, headers, max_retries):
        print(f"Welcome message sent for trade {trade_hash} ({account['name']})")
    else:
        print(f"Failed to send welcome message for trade {trade_hash} ({account['name']})")