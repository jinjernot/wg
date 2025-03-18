import requests
import json
from config import *

def send_welcome_message(trade, headers):

    trade_hash = trade.get("trade_hash")
    payment_method_slug = trade.get("payment_method_slug", "").lower()

    message = WELCOME_MESSAGES.get(payment_method_slug, WELCOME_MESSAGES["default"])
    body = {"trade_hash": trade_hash, "message": message}
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    response = requests.post(CHAT_URL, data=body, headers=headers)

    if response.status_code == 200:
        print(f"Welcome message sent for trade {trade_hash}")
    else:
        print(f"Failed to send welcome message for trade {trade_hash}. Status Code: {response.status_code} - {response.text}")
        return 

    # Send second message if payment method is OXXO
    if payment_method_slug == "oxxo":
        try:
            with open(DB_PATH, "r") as f:
                oxxo_data = json.load(f)

            selected_id = oxxo_data["oxxo"].get("selected_id")
            oxxo_accounts = oxxo_data["oxxo"].get("accounts", [])

            # Find the account with the matching ID
            selected_account = next((acc for acc in oxxo_accounts if acc["id"] == selected_id), None)

            if not selected_account:
                print(f"No OXXO account found for selected_id: {selected_id}")
                return

            second_message = f"Payment Details:\n\n" \
                            f"Bank: {selected_account['bank']}\n" \
                            f"Name: {selected_account['name']}\n" \
                            f"Card Number: {selected_account['card_number']}\n\n" \

            # Send the second message
            body = {"trade_hash": trade_hash, "message": second_message}
            response = requests.post(CHAT_URL, data=body, headers=headers)

            if response.status_code == 200:
                print(f"Payment details sent for trade {trade_hash}")
            else:
                print(f"Failed to send payment details for trade {trade_hash}. Status Code: {response.status_code} - {response.text}")

        except Exception as e:
            print(f"Error reading OXXO data: {e}")
