import os
import json
import logging
from config import JSON_PATH
from core.messaging.message_sender import send_message_with_retry

def send_payment_details_message(trade_hash, payment_method_slug, headers, chat_url, max_retries=3):
    try:
        json_filename = f"{payment_method_slug}.json"
        json_path = os.path.join(JSON_PATH, json_filename)

        with open(json_path, "r") as f:
            payment_data = json.load(f)

        method_data = payment_data.get(payment_method_slug, {})
        selected_id = str(method_data.get("selected_id", ""))

        if not selected_id:
            print(f"Missing selected_id in {json_filename}")
            return

        account = next((acc for acc in method_data.get("accounts", []) if str(acc["id"]) == selected_id), None)

        if not account:
            print(f"No account found for selected_id: {selected_id}")
            return

        if payment_method_slug in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios"]:
            message = f"Payment Details:\n\nBank: {account['bank']}\nName: {account['name']}\nSPEI: {account.get('SPEI', 'N/A')}\n\n"
        elif payment_method_slug == "oxxo":
            message = f"Payment Details:\n\nBank: {account['bank']}\nName: {account['name']}\nCard Number: {account.get('card_number', 'N/A')}\n\n"
        else:
            print(f"Unsupported payment method: {payment_method_slug}")
            return

        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = {"trade_hash": trade_hash, "message": message}

        if send_message_with_retry(chat_url, body, headers, max_retries):
            print(f"Payment details sent for trade {trade_hash} ({account['name']})")
        else:
            print(f"Failed to send payment details for trade {trade_hash} ({account['name']})")

    except Exception as e:
        print(f"Error sending payment details: {e}")