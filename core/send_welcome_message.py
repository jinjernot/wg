import requests

def send_welcome_message(trade, headers):
    url = "https://api.noones.com/noones/v1/trade-chat/post"

    trade_hash = trade.get("trade_hash")
    payment_method_slug = trade.get("payment_method_slug", "").lower()

    if payment_method_slug == "bank-transfer":
        message = "Hi, this offer is for BANK TRANSFER ONLY, no cash deposit in window or through OXXO. Any cash deposit will be reported to the bank as an unacknowledged deposit and it will be lost immediately. If you agree with this, proceed."
    elif payment_method_slug == "oxxo":
        message = "Hi, this offer is exclusive for cash deposits through OXXO, please follow the rules"
    elif payment_method_slug == "amazon-gift-card":
        message = "Hi, this offer is only for Amazon physical card, I do not accept amounts less than $300, If you agree with this, proceed and send card code and receipt. If you have an E-code, it will be taken at a different rate."
    else:
        message = "Welcome to WillGang Trading"

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
