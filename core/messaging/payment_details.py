import os
import json
import logging
from config import PAYMENT_ACCOUNTS_PATH
from config_messages.payment_david import PAYMENT_MESSAGES_DAVID
from config_messages.payment_joe import PAYMENT_MESSAGES_JOE
from core.messaging.message_sender import send_message_with_retry

logger = logging.getLogger(__name__)

def send_payment_details_message(trade_hash, payment_method_slug, headers, chat_url, owner_username, max_retries=3):
    try:
        if payment_method_slug in [
            "spei-sistema-de-pagos-electronicos-interbancarios",
            "domestic-wire-transfer"
        ]:
            normalized_slug = "bank-transfer"
            json_key_slug = "bank-transfer"
        else:
            normalized_slug = payment_method_slug
            json_key_slug = payment_method_slug

        json_filename = f"{normalized_slug}.json"
        json_path = os.path.join(PAYMENT_ACCOUNTS_PATH, json_filename)

        with open(json_path, "r") as f:
            payment_data = json.load(f)

        user_data = payment_data.get(owner_username, {})
        method_data = user_data.get(json_key_slug, {})
        selected_id = str(method_data.get("selected_id", ""))

        if not selected_id:
            logger.error(f"Missing selected_id in {json_filename} for {owner_username}")
            return

        account = next((acc for acc in method_data.get("accounts", []) if str(acc["id"]) == selected_id), None)

        if not account:
            logger.error(f"No account found for selected_id: {selected_id} for {owner_username}")
            return

        if owner_username == "davidvs":
            message_dict = PAYMENT_MESSAGES_DAVID
        elif owner_username == "JoeWillgang":
            message_dict = PAYMENT_MESSAGES_JOE
        else:
            message_dict = PAYMENT_MESSAGES_DAVID

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
            logger.info(f"Payment details sent for trade {trade_hash} ({account['name']}) for {owner_username}")
        else:
            logger.error(f"Failed to send payment details for trade {trade_hash} ({account['name']}) for {owner_username}")

    except Exception as e:
        logger.error(f"Error sending payment details: {e}")