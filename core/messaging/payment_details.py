import os
import logging
from config_messages.payment_david import PAYMENT_MESSAGES_DAVID
from config_messages.payment_joe import PAYMENT_MESSAGES_JOE
from core.messaging.message_sender import send_message_with_retry
from core.utils.config_cache import get_cached_payment_account

logger = logging.getLogger(__name__)

OWNERS_PAYMENT_CONFIG = {
    "davidvs": PAYMENT_MESSAGES_DAVID,
    "JoeWillgang": PAYMENT_MESSAGES_JOE
}

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
        
        payment_data = get_cached_payment_account(json_filename)
        if payment_data is None:
            logger.error(f"Failed to load payment data for {json_filename}")
            return False

        user_data = payment_data.get(owner_username, {})
        method_data = user_data.get(json_key_slug, {})
        selected_id = str(method_data.get("selected_id", ""))

        if not selected_id:
            logger.error(f"Missing selected_id in {json_filename} for {owner_username}")
            return False

        account = next((acc for acc in method_data.get("accounts", []) if str(acc["id"]) == selected_id), None)

        if not account:
            logger.error(f"No account found for selected_id: {selected_id} for {owner_username}")
            return False

        # If a required bank field is missing, fail safely
        if account.get("bank") is None:
            logger.error(f"Missing 'bank' detail for selected_id {selected_id} for {owner_username}. Aborting message to avoid sending broken details.")
            return False

        message_dict = OWNERS_PAYMENT_CONFIG.get(owner_username, PAYMENT_MESSAGES_DAVID)

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
            return True
        else:
            logger.error(f"Failed to send payment details for trade {trade_hash} ({account['name']}) for {owner_username}")
            return False

    except Exception as e:
        logger.error(f"Error sending payment details: {e}")
        return False