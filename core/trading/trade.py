# jinjernot/wg/wg-89c3d83219d0d8811cde10eb2ef6004ace783b14/core/trading/trade.py

import logging
import json
import os
from datetime import datetime, timezone
from config import (
    CHAT_URL_NOONES, PAYMENT_REMINDER_DELAY,
    EMAIL_CHECK_DURATION, PAYMENT_ACCOUNTS_PATH, IMAGE_API_URL_NOONES,
    ONLINE_QUERY_KEYWORDS
)
from core.state.trade_state_loader import load_processed_trades, save_processed_trade
from core.api.trade_chat import get_all_messages_from_chat, download_attachment
# from core.validation.email import check_for_payment_email, get_gmail_service  # EMAIL MODULE DISABLED
from core.validation.ocr import (
    extract_text_from_image,
    find_amount_in_text,
    find_name_in_text,
    identify_bank_from_text,
    save_ocr_text,
    hash_image,
    is_duplicate_receipt
)
from core.messaging.welcome_message import send_welcome_message
from core.messaging.payment_details import send_payment_details_message
from core.messaging.trade_lifecycle_messages import (
    send_trade_completion_message,
    send_payment_received_message,
    send_payment_reminder_message,
    send_attachment_message,
    send_afk_message,
    send_extended_afk_message,
    send_payment_confirmed_no_attachment_message,
    send_online_reply_message,
    send_oxxo_redirect_message,
    send_third_party_allowed_message,
    send_release_message
)
from core.messaging.alerts.telegram_alert import (
    send_telegram_alert,
    send_attachment_alert,
    send_amount_validation_alert,
    # send_email_validation_alert,  # EMAIL MODULE DISABLED
    send_name_validation_alert,
    send_chat_message_alert,
    send_duplicate_receipt_alert
)
from core.messaging.alerts.discord_alert import (
    create_new_trade_embed,
    create_trade_status_update_embed,
    create_attachment_embed,
    create_amount_validation_embed,
    # create_email_validation_embed,  # EMAIL MODULE DISABLED
    create_name_validation_embed,
    create_chat_message_embed,
    create_duplicate_receipt_embed
)
from core.messaging.alerts.discord_thread_manager import create_trade_thread
# from config_messages.email_validation_details import EMAIL_ACCOUNT_DETAILS  # EMAIL MODULE DISABLED


logger = logging.getLogger(__name__)


class Trade:
    def __init__(self, trade_data, account, headers):
        self.account = account
        self.headers = headers
        self.gmail_service = None
        self.trade_hash = trade_data.get("trade_hash")
        self.owner_username = trade_data.get("owner_username", "unknown_user")
        self.platform = "Noones"
        all_trades = load_processed_trades(self.owner_username, self.platform)
        existing_data = all_trades.get(self.trade_hash, {})
        self.trade_state = {**existing_data, **trade_data}
        self._messages_cache = None  # Cleared each process() cycle

    def _get_chat_messages(self):
        """Returns chat messages, fetching from the API only once per process() cycle."""
        if self._messages_cache is None:
            self._messages_cache = get_all_messages_from_chat(
                self.trade_hash, self.account, self.headers
            )
            logger.debug(
                f"[CACHE] Fetched {len(self._messages_cache or [])} messages "
                f"for trade {self.trade_hash}"
            )
        return self._messages_cache

    def save(self):
        """Saves the current, complete state of the trade."""
        save_processed_trade(self.trade_state, self.platform)

    def process(self):
        """Main entry point to process a trade's lifecycle."""
        logger.debug(f"--- Starting to process trade: {self.trade_hash} ---")
        self._messages_cache = None  # Reset cache at the start of every cycle
        
        if self.trade_state.get("trade_status") == "Dispute open":
            logger.info(
                f"Trade {self.trade_hash} is in dispute. Halting all automated messages.")
            return

        if not self.trade_hash or not self.owner_username:
            logger.error(
                f"Missing trade_hash or owner_username for trade: {self.trade_state}")
            return
        is_new = 'first_seen_utc' not in self.trade_state
        if is_new:
            self.handle_new_trade()
        self.check_status_change()
        self.check_for_completion_message()
        # self.check_for_email_confirmation()  # EMAIL MODULE DISABLED
        self.check_chat_and_attachments()
        self.check_for_afk()
        self.check_for_extended_afk()
        self.check_for_inactivity()
        self.check_for_paid_without_attachment()
        self.save()
        logger.debug(f"--- Finished processing trade: {self.trade_hash} ---")

    def handle_new_trade(self):
        """Handles logic for a trade seen for the first time."""
        logger.info(
            f"--- New trade found: {self.trade_hash}. Handling initial messages. ---")
        send_telegram_alert(self.trade_state, self.platform)

        new_trade_embed_data = create_new_trade_embed(
            self.trade_state, self.platform, send=False)
        
        if new_trade_embed_data:
            create_trade_thread(self.trade_hash, new_trade_embed_data)

        self.trade_state['first_seen_utc'] = datetime.now(
            timezone.utc).isoformat()
        send_welcome_message(self.trade_state, self.account, self.headers)
        payment_method_slug = self.trade_state.get(
            "payment_method_slug", "").lower()
        if payment_method_slug in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]:
            send_payment_details_message(
                self.trade_hash, payment_method_slug, self.headers, CHAT_URL_NOONES, self.owner_username)
        self.trade_state['status_history'] = [
            self.trade_state.get("trade_status")]

    def check_status_change(self):
        """Checks for and handles changes in the trade's status."""
        logger.debug(f"--- Checking Status Change for {self.trade_hash} ---")
        current_status = self.trade_state.get("trade_status")
        if current_status not in self.trade_state.get('status_history', []):
            logger.info(
                f"Trade {self.trade_hash} has a new status: '{current_status}'")

            create_trade_status_update_embed(
                self.trade_hash, self.owner_username, current_status, self.platform
            )

            if current_status == 'Paid':
                self.handle_paid_status()
            self.trade_state.setdefault(
                'status_history', []).append(current_status)

    def check_for_completion_message(self):
        """Sends the completion message whenever the trade is Released/Successful and not yet sent.
        This runs every cycle independently of status_history so it retries if the first cycle was missed."""
        if self.trade_state.get('completion_message_sent'):
            return
        current_status = self.trade_state.get("trade_status")
        if current_status in ['Released', 'Successful']:
            logger.info(
                f"Trade {self.trade_hash} is '{current_status}'. Sending completion message.")
            send_trade_completion_message(
                self.trade_hash, self.account, self.headers)
            self.trade_state['completion_message_sent'] = True
            self.save()

    def handle_paid_status(self):
        """Handles the logic when a trade is marked as paid."""
        logger.debug(f"--- Handling 'Paid' status for {self.trade_hash} ---")

        # Check if buyer already uploaded a receipt before we ask for one
        all_messages = self._get_chat_messages()
        has_attachment = any(msg.get("type") == "trade_attach_uploaded" for msg in (all_messages or []))

        if has_attachment:
            logger.info(
                f"Trade {self.trade_hash} marked Paid but attachment already present — "
                f"skipping receipt request message."
            )
        else:
            send_payment_received_message(self.trade_hash, self.account, self.headers)

        if 'paid_timestamp' not in self.trade_state:
            self.trade_state['paid_timestamp'] = datetime.now(timezone.utc).timestamp()

            # IMMEDIATE EMAIL CHECK when marked as Paid  # EMAIL MODULE DISABLED
            # logger.info(f"Trade {self.trade_hash} marked as Paid. Triggering immediate email check.")
            # self.check_for_email_confirmation()

    def check_for_paid_without_attachment(self):
        """If a trade is paid, and some time has passed, check for an attachment and send a reminder if needed."""
        if self.trade_state.get("trade_status") == 'Paid' and not self.trade_state.get('no_attachment_reminder_sent'):
            paid_timestamp = self.trade_state.get('paid_timestamp')
            if paid_timestamp:
                if (datetime.now(timezone.utc).timestamp() - paid_timestamp) > 120:
                    all_messages = get_all_messages_from_chat(self.trade_hash, self.account, self.headers)
                    has_attachment = any(msg.get("type") == "trade_attach_uploaded" for msg in all_messages)

                    if not has_attachment:
                        logger.info(f"Trade {self.trade_hash} is 'Paid' for over 2 minutes with no attachment. Sending a reminder.")
                        send_payment_confirmed_no_attachment_message(self.trade_hash, self.account, self.headers)
                        self.trade_state['no_attachment_reminder_sent'] = True
                        
    def _load_payment_method_data(self):
        """Shared helper: maps the payment slug, reads the JSON file, and returns
        (json_key_slug, method_data) for this trade's owner.
        Returns (None, None) when the payment method is not supported or data is missing."""
        slug = self.trade_state.get("payment_method_slug", "").lower()

        if slug == "oxxo":
            json_key_slug = "oxxo"
        elif slug in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]:
            json_key_slug = "bank-transfer"
        else:
            return None, None

        json_filename = f"{json_key_slug}.json"
        json_path = os.path.join(PAYMENT_ACCOUNTS_PATH, json_filename)

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                payment_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Could not read or parse {json_filename}: {e}")
            return None, None

        user_data = payment_data.get(self.owner_username, {})
        method_data = user_data.get(json_key_slug, {})
        return json_key_slug, method_data

    def get_credential_identifier_for_trade(self):
        """Returns the name of the currently selected payment account, or None."""
        logger.debug(f"--- Getting Credential Identifier for {self.trade_hash} ---")
        json_key_slug, method_data = self._load_payment_method_data()
        if method_data is None:
            return None

        selected_id = str(method_data.get("selected_id", ""))
        if not selected_id:
            logger.warning(f"No selected_id found for {self.owner_username}")
            return None

        account = next(
            (acc for acc in method_data.get("accounts", [])
             if str(acc.get("id")) == selected_id),
            None
        )
        if account and "name" in account:
            return account["name"]

        logger.warning(f"No 'name' found for account id {selected_id}")
        return None

    def get_all_credential_identifiers_for_trade(self):
        """Returns ALL account names for the payment method, with the selected account first."""
        logger.debug(f"--- Getting All Credential Identifiers for {self.trade_hash} ---")
        json_key_slug, method_data = self._load_payment_method_data()
        if method_data is None:
            return []

        selected_id = str(method_data.get("selected_id", ""))
        all_accounts = method_data.get("accounts", [])

        # Build list: selected account first, then remaining ones that have credentials
        account_names = []

        if selected_id:
            selected_account = next(
                (acc for acc in all_accounts if str(acc.get("id")) == selected_id),
                None
            )
            if selected_account and "name" in selected_account:
                account_names.append(selected_account["name"])
                logger.debug(f"Selected account: {selected_account['name']}")

        for acc in all_accounts:
            if "name" in acc:
                acc_name = acc["name"]
                if acc_name not in account_names and acc_name in EMAIL_ACCOUNT_DETAILS:
                    account_names.append(acc_name)
                    logger.debug(f"Additional account to check: {acc_name}")

        logger.debug(f"Total accounts to check for email: {len(account_names)}")
        return account_names

    # --- EMAIL MODULE DISABLED ---
    # def check_for_email_confirmation(self):
    #     """Checks for payment confirmation emails if the trade is marked as Paid and has an attachment."""
    #     (entire method commented out — re-enable when email module is fixed)

    def check_chat_and_attachments(self):
        """Fetches the entire chat history and processes any unprocessed messages or attachments."""
        logger.debug(f"--- Checking Chat & Attachments for {self.trade_hash} ---")
        all_messages = self._get_chat_messages()
        if not all_messages:
            return

        # Determine which messages are new
        last_processed_id = self.trade_state.get('last_processed_message_id')
        new_messages = []
        if last_processed_id:
            last_index = -1
            for i, msg in enumerate(all_messages):
                if str(msg.get("id")) == str(last_processed_id):
                    last_index = i
                    break
            if last_index != -1:
                new_messages = all_messages[last_index + 1:]
        else:
            new_messages = all_messages
        
        # Process new text messages
        for msg in new_messages:
            # Check if the message is NOT an attachment upload notification before processing as a text message
            if msg.get("type") != "trade_attach_uploaded" and msg.get("author") is not None:
                message_text = msg.get("text")
                # Ensure that the message is a string before sending
                if isinstance(message_text, str) and message_text:
                    msg_author = msg.get("author", "Unknown")
                    # send_chat_message_alert(message_text, self.trade_hash, self.owner_username, msg_author)
                    create_chat_message_embed(self.trade_hash, self.owner_username, msg_author, message_text, self.platform)

        if new_messages:
            self.handle_online_query(new_messages)
            self.handle_oxxo_query(new_messages)
            self.handle_third_party_query(new_messages)
            self.handle_release_query(new_messages)
            for msg in reversed(new_messages):
                 if msg.get("author") not in ["davidvs", "JoeWillgang", None]:
                    self.trade_state['last_buyer_ts'] = msg.get("timestamp")
                    break

        # Process attachments from entire history, avoiding duplicates
        processed_attachments = self.trade_state.get('processed_attachments', {})
        new_attachments_to_process = []
        image_api_url = IMAGE_API_URL_NOONES

        for msg in all_messages:
            if msg.get("type") == "trade_attach_uploaded":
                files = msg.get("text", {}).get("files", [])
                author = msg.get("author", "Unknown")
                for file_info in files:
                    image_url_path = file_info.get("url")
                    if image_url_path:
                        # Check if this attachment has been processed and alerts sent
                        if image_url_path not in processed_attachments:
                            logger.info(f"New attachment uploaded by '{author}' for trade {self.trade_hash}. URL: {image_url_path}")
                            file_path = download_attachment(image_url_path, image_api_url, self.trade_hash, self.headers)
                            if file_path:
                                new_attachments_to_process.append({
                                    "path": file_path, 
                                    "author": author,
                                    "url": image_url_path
                                })
                                # Mark as downloaded but alerts not yet sent
                                processed_attachments[image_url_path] = {"downloaded": True, "alerts_sent": False}
        
        self.trade_state['processed_attachments'] = processed_attachments

        if not new_attachments_to_process:
            if all_messages:
                self.trade_state['last_processed_message_id'] = all_messages[-1].get('id')
            return

        if not self.trade_state.get('attachment_message_sent'):
            logger.info(f"New attachment found for trade {self.trade_hash}. Processing.")
            send_attachment_message(self.trade_hash, self.account, self.headers)
            self.trade_state['attachment_message_sent'] = True

        credential_identifier = self.get_credential_identifier_for_trade()
        # account_config = EMAIL_ACCOUNT_DETAILS.get(credential_identifier)  # EMAIL MODULE DISABLED
        # expected_names = account_config.get("name_receipt", []) if account_config else []
        expected_names = []  # Email module disabled — name validation skipped

        for attachment in new_attachments_to_process:
            path, author, url = attachment['path'], attachment['author'], attachment['url']
            
            # Check if alerts have already been sent for this attachment
            if processed_attachments.get(url, {}).get('alerts_sent'):
                logger.debug(f"Alerts already sent for attachment {url}, skipping.")
                continue
                
            if author not in ["davidvs", "JoeWillgang"]:
                logger.debug(f"Processing new attachment by {author} for {self.trade_hash}.")
                
                # Check for duplicate receipt
                image_hash = hash_image(path)
                is_duplicate, previous_trade_info = is_duplicate_receipt(image_hash, self.trade_hash, self.owner_username)
                if is_duplicate:
                    send_duplicate_receipt_alert(self.trade_hash, self.owner_username, path, previous_trade_info)
                    
                    create_duplicate_receipt_embed(self.trade_hash, self.owner_username, path, self.platform, previous_trade_info)

                text = extract_text_from_image(path)
                identified_bank = identify_bank_from_text(text)
                save_ocr_text(self.trade_hash, self.owner_username, text, identified_bank)
                send_attachment_alert(self.trade_hash, self.owner_username, author, path, bank_name=identified_bank)
                
                create_attachment_embed(self.trade_hash, self.owner_username, author, path, self.platform, bank_name=identified_bank)

                if identified_bank:
                    self.trade_state['ocr_identified_bank'] = identified_bank
                    logger.info(f"Receipt for trade {self.trade_hash} identified as {identified_bank}.")

                logger.debug(f"Performing amount validation for {self.trade_hash}.")
                found_amount = find_amount_in_text(text, self.trade_state.get("fiat_amount_requested"))
                if not self.trade_state.get('amount_validation_alert_sent'):
                    expected = self.trade_state.get("fiat_amount_requested")
                    currency = self.trade_state.get("fiat_currency_code")
                    send_amount_validation_alert(self.trade_hash, self.owner_username, expected, found_amount, currency)
                    
                    create_amount_validation_embed(self.trade_hash, self.owner_username, expected, found_amount, currency)
                    
                    self.trade_state['amount_validation_alert_sent'] = True

                if expected_names:
                    logger.debug(f"Performing name validation for {self.trade_hash}.")
                    is_name_found = find_name_in_text(text, expected_names)
                    if not self.trade_state.get('name_validation_alert_sent'):
                        send_name_validation_alert(self.trade_hash, is_name_found, credential_identifier)
                        
                        create_name_validation_embed(self.trade_hash, is_name_found, credential_identifier)
                        
                        self.trade_state['name_validation_alert_sent'] = True
                
                # Mark alerts as sent for this attachment
                processed_attachments[url]['alerts_sent'] = True
                logger.debug(f"Marked attachment {url} as alerts_sent=True")
                
            self.save()

        if all_messages:
            self.trade_state['last_processed_message_id'] = all_messages[-1].get('id')
    
    def handle_online_query(self, new_messages):
        """Checks for messages asking if the user is online and sends a reply."""
        logger.debug(f"--- Checking for Online Query: {self.trade_hash} ---")
        if self.trade_state.get('online_reply_sent'):
            return

        for msg in new_messages:
            message_text = msg.get("text", "")
            if isinstance(message_text, dict):
                message_text = str(message_text)

            message_text = message_text.lower()
            if any(keyword in message_text for keyword in ONLINE_QUERY_KEYWORDS):
                logger.info(f"Online query detected for trade {self.trade_hash}. Sending reply.")
                send_online_reply_message(self.trade_hash, self.account, self.headers)
                self.trade_state['online_reply_sent'] = True
                self.save()
                break

    def handle_oxxo_query(self, new_messages):
        """Checks if a user mentions OXXO in a bank transfer trade."""
        logger.debug(f"--- Checking for OXXO Query in Bank Trade: {self.trade_hash} ---")
        
        payment_method_slug = self.trade_state.get("payment_method_slug", "").lower()
        is_bank_transfer = payment_method_slug in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]
        
        if not is_bank_transfer or self.trade_state.get('oxxo_redirect_sent'):
            return

        for msg in new_messages:
            if msg.get("author") not in ["davidvs", "JoeWillgang", None]:
                message_text = msg.get("text", "")
                if isinstance(message_text, str) and "oxxo" in message_text.lower():
                    logger.info(f"OXXO keyword detected in bank transfer trade {self.trade_hash}. Sending redirect message.")
                    send_oxxo_redirect_message(self.trade_hash, self.account, self.headers)
                    self.trade_state['oxxo_redirect_sent'] = True
                    self.save()
                    break 

    def handle_third_party_query(self, new_messages):
        """Checks if a user asks about third party payments."""
        logger.debug(f"--- Checking for Third Party Query: {self.trade_hash} ---")
        if self.trade_state.get('third_party_reply_sent'):
            return

        third_party_keywords = ["3rd party", "third party"]

        for msg in new_messages:
            if msg.get("author") not in ["davidvs", "JoeWillgang", None]:
                message_text = msg.get("text", "")
                if isinstance(message_text, str):
                    message_lower = message_text.lower()
                    if any(keyword in message_lower for keyword in third_party_keywords):
                        logger.info(f"Third party query detected for trade {self.trade_hash}. Sending reply.")
                        send_third_party_allowed_message(self.trade_hash, self.account, self.headers)
                        self.trade_state['third_party_reply_sent'] = True
                        self.save()
                        break

    def handle_release_query(self, new_messages):
        """Checks if a user asks about release."""
        logger.debug(f"--- Checking for Release Query: {self.trade_hash} ---")
        if self.trade_state.get('release_reply_sent'):
            return

        for msg in new_messages:
            if msg.get("author") not in ["davidvs", "JoeWillgang", None]:
                message_text = msg.get("text", "")
                if isinstance(message_text, str) and "release" in message_text.lower():
                    logger.info(f"Release query detected for trade {self.trade_hash}. Sending reply.")
                    send_release_message(self.trade_hash, self.account, self.headers)
                    self.trade_state['release_reply_sent'] = True
                    self.save()
                    break

    def check_for_afk(self):
        """Checks if the buyer has sent multiple messages without a response."""
        logger.debug(f"--- Checking for AFK: {self.trade_hash} ---")
        if self.trade_state.get('afk_message_sent'):
            return

        all_messages = self._get_chat_messages()

        if not all_messages:
            return

        owner_usernames = ["davidvs", "JoeWillgang"]
        
        # Find the timestamp of the last message from the owner
        last_owner_message_ts = None
        for msg in reversed(all_messages):
            if msg.get("author") in owner_usernames:
                last_owner_message_ts = msg.get("timestamp")
                break

        buyer_messages = [msg for msg in all_messages if msg.get(
            "author") not in owner_usernames]

        if not buyer_messages:
            return

        if all_messages[-1].get("author") not in owner_usernames:
            consecutive_buyer_messages = 0
            for msg in reversed(all_messages):
                if msg.get("author") not in owner_usernames:
                    consecutive_buyer_messages += 1
                else:
                    break

            logger.debug(
                f"AFK Check for trade {self.trade_hash}: Found {consecutive_buyer_messages} consecutive buyer messages.")

            first_consecutive_message_ts = all_messages[-consecutive_buyer_messages].get(
                "timestamp")
            if not first_consecutive_message_ts:
                return

            time_since_first_message = (datetime.now(
                timezone.utc).timestamp() - first_consecutive_message_ts) / 60
            logger.debug(
                f"AFK Check for trade {self.trade_hash}: Time since first message is {time_since_first_message:.2f} minutes.")

            message_threshold = 3
            time_threshold_minutes = 5
            
            # FIXED: Check if owner sent any message AFTER the first consecutive buyer message
            # This prevents false positives when owner is actively responding
            owner_responded_during_consecutive = last_owner_message_ts and last_owner_message_ts > first_consecutive_message_ts
            
            if owner_responded_during_consecutive:
                logger.debug(
                    f"AFK not triggered for {self.trade_hash}: Owner sent a message during the consecutive buyer messages.")
            elif (consecutive_buyer_messages >= message_threshold and 
                  time_since_first_message > time_threshold_minutes):
                logger.info(
                    f"AFK TRIGGERED for trade {self.trade_hash}. Buyer sent {consecutive_buyer_messages} messages over {time_since_first_message:.2f} minutes without owner response. Sending AFK message.")
                send_afk_message(self.trade_hash, self.account, self.headers)
                self.trade_state['afk_message_sent'] = True
                self.save()
            else:
                if consecutive_buyer_messages < message_threshold:
                    logger.debug(
                        f"AFK not triggered for {self.trade_hash}: Not enough messages ({consecutive_buyer_messages}/{message_threshold}).")
                if time_since_first_message <= time_threshold_minutes:
                    logger.debug(
                        f"AFK not triggered for {self.trade_hash}: Not enough time ({time_since_first_message:.2f}/{time_threshold_minutes} min).")
                    
            
    def check_for_extended_afk(self):
        """Checks for extended inactivity from the buyer and sends a specific message."""
        logger.debug(f"--- Checking for Extended AFK: {self.trade_hash} ---")
        if self.trade_state.get('extended_afk_message_sent') or not self.trade_state.get('afk_message_sent'):
            return

        all_messages = self._get_chat_messages()
        if not all_messages:
            return

        owner_usernames = ["davidvs", "JoeWillgang"]
        last_buyer_message_ts = None
        for msg in reversed(all_messages):
            if msg.get("author") not in owner_usernames:
                last_buyer_message_ts = msg.get("timestamp")
                break

        if not last_buyer_message_ts:
            return

        time_since_last_buyer_message = (
            datetime.now(timezone.utc).timestamp() - last_buyer_message_ts) / 60
        logger.debug(
            f"Extended AFK Check for trade {self.trade_hash}: Time since last buyer message is {time_since_last_buyer_message:.2f} minutes.")

        extended_time_threshold_minutes = 15

        if time_since_last_buyer_message > extended_time_threshold_minutes:
            logger.info(
                f"EXTENDED AFK TRIGGERED for trade {self.trade_hash}. No response for over {extended_time_threshold_minutes} minutes. Sending extended AFK message.")
            send_extended_afk_message(
                self.trade_hash, self.account, self.headers)
            self.trade_state['extended_afk_message_sent'] = True
            self.save()

    def check_for_inactivity(self):
        """Sends a payment reminder if the trade has been inactive for too long."""
        logger.debug(f"--- Checking for Inactivity: {self.trade_hash} ---")
        is_active = self.trade_state.get(
            "trade_status", "").startswith('Active')
        if not is_active or self.trade_state.get('reminder_sent'):
            return
        reference_time = None
        if self.trade_state.get('last_buyer_ts'):
            reference_time = datetime.fromtimestamp(
                self.trade_state['last_buyer_ts'], tz=timezone.utc)
        elif self.trade_state.get("start_date"):
            try:
                reference_time = datetime.fromisoformat(
                    self.trade_state["start_date"]).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                logger.error(
                    f"Could not parse start_date for trade {self.trade_hash}.")
        if reference_time and (datetime.now(timezone.utc) - reference_time).total_seconds() > PAYMENT_REMINDER_DELAY:
            logger.info(
                f"Sending payment reminder for trade {self.trade_hash} due to inactivity.")
            send_payment_reminder_message(
                self.trade_hash, self.account, self.headers)
            self.trade_state['reminder_sent'] = True