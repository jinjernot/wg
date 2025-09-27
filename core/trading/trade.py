import logging
import json
import os
from datetime import datetime, timezone
from config import (
    CHAT_URL_PAXFUL, CHAT_URL_NOONES, PAYMENT_REMINDER_DELAY,
    EMAIL_CHECK_DURATION, JSON_PATH
)
from core.state.get_files import load_processed_trades, save_processed_trade
from core.api.trade_chat import fetch_trade_chat_messages
from core.validation.email import check_for_payment_email, get_gmail_service
from core.validation.ocr import (
    extract_text_from_image,
    find_amount_in_text,
    find_name_in_text,
    identify_bank_from_text,
    save_ocr_text
)
from core.messaging.welcome_message import send_welcome_message
from core.messaging.payment_details import send_payment_details_message
from core.messaging.trade_lifecycle_messages import (
    send_trade_completion_message,
    send_payment_received_message,
    send_payment_reminder_message
)
from core.messaging.attachment_message import send_attachment_message
from core.messaging.alerts.telegram_alert import (
    send_telegram_alert,
    send_attachment_alert,
    send_amount_validation_alert,
    send_email_validation_alert,
    send_name_validation_alert
)
from core.messaging.alerts.discord_alert import (
    create_new_trade_embed,
    create_attachment_embed,
    create_amount_validation_embed,
    create_email_validation_embed,
    create_name_validation_embed,
    create_chat_message_embed
)
from core.messaging.alerts.discord_thread_manager import create_trade_thread
from config_messages.email_validation_details import EMAIL_ACCOUNT_DETAILS

logger = logging.getLogger(__name__)

class Trade:
    def __init__(self, trade_data, account, headers):
        self.account = account
        self.headers = headers
        self.gmail_service = None
        self.trade_hash = trade_data.get("trade_hash")
        self.owner_username = trade_data.get("owner_username", "unknown_user")
        self.platform = "Paxful" if "_Paxful" in self.account["name"] else "Noones"
        all_trades = load_processed_trades(self.owner_username, self.platform)
        existing_data = all_trades.get(self.trade_hash, {})
        self.trade_state = {**existing_data, **trade_data}

    def save(self):
        """Saves the current, complete state of the trade."""
        save_processed_trade(self.trade_state, self.platform)

    def process(self):
        """Main entry point to process a trade's lifecycle."""
        if self.trade_state.get("trade_status") == "Dispute open":
            logger.info(f"Trade {self.trade_hash} is in dispute. Halting all automated messages.")
            return

        if not self.trade_hash or not self.owner_username:
            logger.error(f"Missing trade_hash or owner_username for trade: {self.trade_state}")
            return
        is_new = 'first_seen_utc' not in self.trade_state
        if is_new:
            self.handle_new_trade()
        self.check_status_change()
        self.check_for_email_confirmation()
        self.check_chat_and_attachments()
        self.check_for_inactivity()
        self.save()

    def handle_new_trade(self):
        """Handles logic for a trade seen for the first time."""
        logger.info(f"New trade found: {self.trade_hash}. Handling initial messages.")
        send_telegram_alert(self.trade_state, self.platform)

        new_trade_embed_data = create_new_trade_embed(self.trade_state, self.platform, send=False)
        if new_trade_embed_data:
            create_trade_thread(self.trade_hash, new_trade_embed_data)

        self.trade_state['first_seen_utc'] = datetime.now(timezone.utc).isoformat()
        send_welcome_message(self.trade_state, self.account, self.headers)
        payment_method_slug = self.trade_state.get("payment_method_slug", "").lower()
        if payment_method_slug in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios","domestic-wire-transfer"]:
            chat_url = CHAT_URL_PAXFUL if self.platform == "Paxful" else CHAT_URL_NOONES
            send_payment_details_message(self.trade_hash, payment_method_slug, self.headers, chat_url, self.owner_username)
        self.trade_state['status_history'] = [self.trade_state.get("trade_status")]

    def check_status_change(self):
        """Checks for and handles changes in the trade's status."""
        current_status = self.trade_state.get("trade_status")
        if current_status not in self.trade_state.get('status_history', []):
            logger.info(f"Trade {self.trade_hash} has a new status: '{current_status}'")
            if current_status == 'Successful':
                send_trade_completion_message(self.trade_hash, self.account, self.headers)
            elif current_status == 'Paid':
                send_payment_received_message(self.trade_hash, self.account, self.headers)
                if 'paid_timestamp' not in self.trade_state:
                    self.trade_state['paid_timestamp'] = datetime.now(timezone.utc).timestamp()
            self.trade_state.setdefault('status_history', []).append(current_status)

    def get_credential_identifier_for_trade(self):
        """Finds the name identifier for credentials based on the selected payment account."""
        slug = self.trade_state.get("payment_method_slug", "").lower()

        json_key_slug = ""
        if slug == "oxxo":
            json_key_slug = "oxxo"
        elif slug in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]:
            json_key_slug = "bank-transfer"
        else:
            return None

        json_filename = f"{json_key_slug}.json"
        json_path = os.path.join(JSON_PATH, json_filename)

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                payment_data = json.load(f)

            user_data = payment_data.get(self.owner_username, {})
            method_data = user_data.get(json_key_slug, {})
            selected_id = str(method_data.get("selected_id", ""))

            if not selected_id:
                logger.warning(f"No selected_id found for {self.owner_username} in {json_filename}")
                return None

            account = next((acc for acc in method_data.get("accounts", []) if str(acc.get("id")) == selected_id), None)

            if account and "name" in account:
                return account["name"]
            else:
                logger.warning(f"No 'name' found for account id {selected_id} in {json_filename}")

        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not read or parse {json_filename}: {e}")

        return None

    def check_for_email_confirmation(self):
        """Checks for payment confirmation emails if the trade is marked as Paid."""
        is_paid = self.trade_state.get("trade_status") == 'Paid'
        is_relevant = self.trade_state.get("payment_method_slug", "").lower() in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]
        is_pending = not self.trade_state.get('email_verified') and not self.trade_state.get('email_check_timed_out')

        if not (is_paid and is_relevant and is_pending):
            return

        credential_identifier = self.get_credential_identifier_for_trade()
        if not credential_identifier:
            logger.warning(f"Could not determine credential identifier for trade {self.trade_hash}. Skipping email check.")
            return

        self.gmail_service = get_gmail_service(credential_identifier)
        if not self.gmail_service:
            return

        paid_timestamp = self.trade_state.get('paid_timestamp')
        if not paid_timestamp:
            return

        elapsed_time = datetime.now(timezone.utc).timestamp() - paid_timestamp
        if elapsed_time < EMAIL_CHECK_DURATION:
            if check_for_payment_email(self.gmail_service, self.trade_state, self.platform, credential_identifier):
                logger.info(f"PAYMENT VERIFIED via email for trade {self.trade_hash} in '{credential_identifier}' account.")
                if not self.trade_state.get('email_validation_alert_sent'):
                    send_email_validation_alert(self.trade_hash, success=True, account_name=credential_identifier)
                    create_email_validation_embed(self.trade_hash, success=True, account_name=credential_identifier)
                    self.trade_state['email_validation_alert_sent'] = True
                    self.save()
                self.trade_state['email_verified'] = True
        else:
            logger.warning(f"Email check for trade {self.trade_hash} timed out.")
            if not self.trade_state.get('email_validation_alert_sent'):
                send_email_validation_alert(self.trade_hash, success=False, account_name=credential_identifier)
                create_email_validation_embed(self.trade_hash, success=False, account_name=credential_identifier)
                self.trade_state['email_validation_alert_sent'] = True
                self.save()
            self.trade_state['email_check_timed_out'] = True

    def check_chat_and_attachments(self):
        """Fetches chat history and processes any new attachments."""
        attachment_found, last_buyer_ts, new_attachments = fetch_trade_chat_messages(
            self.trade_hash, self.owner_username, self.account, self.headers)
        if last_buyer_ts: self.trade_state['last_buyer_ts'] = last_buyer_ts
        if not new_attachments: return
        if not self.trade_state.get('attachment_message_sent'):
            logger.info(f"New attachment found for trade {self.trade_hash}. Processing.")
            send_attachment_message(self.trade_hash, self.account, self.headers)
            self.trade_state['attachment_message_sent'] = True

        credential_identifier = self.get_credential_identifier_for_trade()
        account_config = EMAIL_ACCOUNT_DETAILS.get(credential_identifier)
        expected_names = account_config.get("name_receipt", []) if account_config else []

        for attachment in new_attachments:
            path, author = attachment['path'], attachment['author']
            if author not in ["davidvs", "JoeWillgang"]:

                text = extract_text_from_image(path)
                identified_bank = identify_bank_from_text(text)

                # --- UPDATED LINE ---
                save_ocr_text(self.trade_hash, self.owner_username, text, identified_bank)

                send_attachment_alert(self.trade_hash, self.owner_username, author, path, bank_name=identified_bank)
                create_attachment_embed(self.trade_hash, self.owner_username, author, path, self.platform, bank_name=identified_bank)

                if identified_bank:
                    self.trade_state['ocr_identified_bank'] = identified_bank
                    logger.info(f"Receipt for trade {self.trade_hash} identified as {identified_bank}.")

                # --- Perform and Alert on Amount Validation ---
                found_amount = find_amount_in_text(text, self.trade_state.get("fiat_amount_requested"))
                if not self.trade_state.get('amount_validation_alert_sent'):
                    expected = self.trade_state.get("fiat_amount_requested")
                    currency = self.trade_state.get("fiat_currency_code")
                    send_amount_validation_alert(self.trade_hash, self.owner_username, expected, found_amount, currency)
                    create_amount_validation_embed(self.trade_hash, self.owner_username, expected, found_amount, currency)
                    self.trade_state['amount_validation_alert_sent'] = True

                # --- Perform and Alert on Name Validation ---
                if expected_names:
                    is_name_found = find_name_in_text(text, expected_names)
                    if not self.trade_state.get('name_validation_alert_sent'):
                        send_name_validation_alert(self.trade_hash, is_name_found, credential_identifier)
                        create_name_validation_embed(self.trade_hash, is_name_found, credential_identifier)
                        self.trade_state['name_validation_alert_sent'] = True

                self.save()


    def check_for_inactivity(self):
        """Sends a payment reminder if the trade has been inactive for too long."""
        is_active = self.trade_state.get("trade_status", "").startswith('Active')
        if not is_active or self.trade_state.get('reminder_sent'): return
        reference_time = None
        if self.trade_state.get('last_buyer_ts'):
            reference_time = datetime.fromtimestamp(self.trade_state['last_buyer_ts'], tz=timezone.utc)
        elif self.trade_state.get("start_date"):
            try:
                reference_time = datetime.fromisoformat(self.trade_state["start_date"]).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                logger.error(f"Could not parse start_date for trade {self.trade_hash}.")
        if reference_time and (datetime.now(timezone.utc) - reference_time).total_seconds() > PAYMENT_REMINDER_DELAY:
            logger.info(f"Sending payment reminder for trade {self.trade_hash} due to inactivity.")
            send_payment_reminder_message(self.trade_hash, self.account, self.headers)
            self.trade_state['reminder_sent'] = True