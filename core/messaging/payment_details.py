import os
import json
import logging
from config import JSON_PATH
from config_messages.payment_david import PAYMENT_MESSAGES_DAVID
from config_messages.payment_joe import PAYMENT_MESSAGES_JOE
from core.messaging.message_sender import send_message_with_retry

def send_payment_details_message(trade_hash, payment_method_slug, headers, chat_url, owner_username, max_retries=3):
    try:
        # Normalize slug for shared bank-based methods (but exclude 'oxxo')
        if payment_method_slug in [
            "spei-sistema-de-pagos-electronicos-interbancarios",
            "domestic-wire-transfer"
        ]:
            normalized_slug = "bank-transfer"
            json_key_slug = "bank-transfer"
        else:
            normalized_slug = payment_method_slug
            json_key_slug = payment_method_slug

        # Load the correct JSON file
        json_filename = f"{normalized_slug}.json"
        json_path = os.path.join(JSON_PATH, json_filename)

        with open(json_path, "r") as f:
            payment_data = json.load(f)

        # Use the json_key_slug to access data inside the file
        user_data = payment_data.get(owner_username, {})
        method_data = user_data.get(json_key_slug, {})
        selected_id = str(method_data.get("selected_id", ""))

        if not selected_id:
            print(f"Missing selected_id in {json_filename} for {owner_username}")
            return

        account = next((acc for acc in method_data.get("accounts", []) if str(acc["id"]) == selected_id), None)

        if not account:
            print(f"No account found for selected_id: {selected_id} for {owner_username}")
            return

        # Choose correct message dictionary
        if owner_username == "davidvs":
            message_dict = PAYMENT_MESSAGES_DAVID
        elif owner_username == "JoeWillgang":
            message_dict = PAYMENT_MESSAGES_JOE
        else:
            message_dict = PAYMENT_MESSAGES_DAVID

        # Get the right message template using original slug
        template = message_dict.get(payment_method_slug, message_dict["default"])

        message = template.format(
            bank=account.get("bank", "N/A"),
            name=account.get("name", "N/A"),
            SPEI=account.get("SPEI", "N/A"),
            card_number=account.get("card_number", "N/A")
        )

        headers["Content-Type"] = "application/x-www-form-urlencoded"
        body = {"trade_hash": trade_hash, "message": message}

        if send_message_with_retry(chat_url, body, headers, max_retries):
            print(f"Payment details sent for trade {trade_hash} ({account['name']}) for {owner_username}")
        else:
            print(f"Failed to send payment details for trade {trade_hash} ({account['name']}) for {owner_username}")

    except Exception as e:
        print(f"Error sending payment details: {e}")