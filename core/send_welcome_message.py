import requests
from config import *

def send_welcome_message(trade, headers):
    url = "https://api.noones.com/noones/v1/trade-chat/post"

    trade_hash = trade.get("trade_hash")
    payment_method_slug = trade.get("payment_method_slug", "").lower()

    message = WELCOME_MESSAGES.get(payment_method_slug, WELCOME_MESSAGES["default"])

    body = {
        "trade_hash": trade_hash,
        "message": message
    }

    headers["Content-Type"] = "application/x-www-form-urlencoded"

    response = requests.post(url, data=body, headers=headers)

    if response.status_code == 200:
        print(f"Welcome message sent for trade {trade_hash}")
    else:
        print(f"Failed to send welcome message for trade {trade_hash}. Status Code: {response.status_code} - {response.text}")
