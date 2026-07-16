# jinjernot/wg/wg-89c3d83219d0d8811cde10eb2ef6004ace783b14/core/trading/trade.py

import logging
import json
import os
import atexit
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from config import (
    CHAT_URL_NOONES, PAYMENT_REMINDER_DELAY, ATTACHMENT_WAIT_SECONDS,
    PAYMENT_ACCOUNTS_PATH, IMAGE_API_URL_NOONES,
    ONLINE_QUERY_KEYWORDS, BOT_OWNER_USERNAMES, BANK_TRANSFER_SLUGS,
    AUTO_MESSAGE_LIMIT
)
from core.state.trade_state_loader import load_processed_trades, save_processed_trade
from core.api.trade_chat import download_attachment, get_all_messages_from_chat
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
from core.trading.chat_processor import ChatProcessor
from core.messaging.welcome_message import send_welcome_message, is_afk_mode_enabled
from core.messaging.payment_details import send_payment_details_message
from core.utils.config_cache import get_cached_payment_account, get_cached_app_settings
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
    send_release_message,
    send_delay_message,
    send_spam_warning_message,
    send_final_away_message
)
from core.messaging.alerts.telegram_alert import (
    send_telegram_alert,
    send_high_value_trade_alert,
    send_attachment_alert,
    send_amount_validation_alert,
    # send_email_validation_alert,  # EMAIL MODULE DISABLED
    send_name_validation_alert,
    send_chat_message_alert,
    send_duplicate_receipt_alert
)
from core.messaging.alerts.discord_alert import (
    create_new_trade_embed,
    create_high_value_trade_embed,
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

# Shared thread pool for fire-and-forget notification sends (Telegram/Discord).
# Keeps the main trade-processing loop from blocking on network I/O.
_notification_executor = ThreadPoolExecutor(max_workers=30, thread_name_prefix="notif")
atexit.register(_notification_executor.shutdown, wait=True, cancel_futures=False)


class Trade:
    def __init__(self, trade_data, account, headers, loaded_trades=None):
        self.account = account
        self.headers = headers
        self.trade_hash = trade_data.get("trade_hash")
        self.owner_username = trade_data.get("owner_username", "unknown_user")
        self.platform = "Noones"
        if loaded_trades is None:
            all_trades = load_processed_trades(self.owner_username, self.platform)
        else:
            all_trades = loaded_trades
        existing_data = all_trades.get(self.trade_hash, {})
        self.trade_state = {**existing_data, **trade_data}
        self._messages_cache = None  # Cleared each process() cycle
        self.chat_processor = ChatProcessor(self)

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

    def _is_owner_recently_active(self) -> bool:
        """
        Returns True if a human operator sent a message in the trade chat
        within the 'owner_active_suppression_minutes' window (default 15 min).

        When an owner is actively handling the trade manually, we want the bot
        to stay silent and not fire spam warnings, AFK replies, delay replies, etc.
        over the top of the real conversation.

        Uses the already-cached chat messages so it costs zero extra API calls.
        """
        settings = get_cached_app_settings()
        window_minutes = settings.get("owner_active_suppression_minutes", 15)
        if window_minutes <= 0:
            return False  # Suppression disabled (window of 0 = always allow auto-msgs)

        # First try the timestamp we already track in state — faster path.
        last_owner_ts = self.trade_state.get("last_owner_ts")
        if last_owner_ts:
            elapsed_minutes = (datetime.now(timezone.utc).timestamp() - last_owner_ts) / 60
            if elapsed_minutes < window_minutes:
                logger.debug(
                    f"[OwnerActive] Owner was active {elapsed_minutes:.1f}m ago in trade "
                    f"{self.trade_hash} (window={window_minutes}m) — suppressing auto-message."
                )
                return True

        # Fallback: scan cached chat history (no extra API call — _messages_cache is reused).
        all_messages = self._get_chat_messages()
        if not all_messages:
            return False

        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - (window_minutes * 60)
        for msg in reversed(all_messages):
            author = msg.get("author")
            if author in BOT_OWNER_USERNAMES:
                ts = msg.get("timestamp", 0) or 0
                if ts > cutoff:
                    logger.debug(
                        f"[OwnerActive] Found owner message {(now - ts) / 60:.1f}m ago in trade "
                        f"{self.trade_hash} — suppressing auto-message."
                    )
                    return True
                break  # Messages are oldest-first; first owner msg we hit going backward is the latest
        return False

    def send_interactive_auto_message(self, send_func, *args, **kwargs):
        """Sends an interactive auto-message, increments the counter, and handles limits."""
        if self.trade_state.get('auto_responses_disabled'):
            logger.debug(f"Skipping auto-message for trade {self.trade_hash} as auto-responses are disabled.")
            return False

        # If a human operator is actively chatting, stay silent.
        # This prevents the bot from firing spam warnings, delay replies, AFK
        # messages, etc. over the top of a real conversation.
        if self._is_owner_recently_active():
            logger.info(
                f"[OwnerActive] Suppressing auto-message for trade {self.trade_hash} "
                f"— owner recently active in chat."
            )
            return False

        # Send the actual message
        send_func(*args, **kwargs)

        # Increment interactive counter
        count = self.trade_state.get('interactive_auto_message_count', 0) + 1
        self.trade_state['interactive_auto_message_count'] = count
        logger.info(f"Interactive auto-message count for trade {self.trade_hash}: {count}")

        # Check threshold (configured limit)
        if count >= AUTO_MESSAGE_LIMIT:
            logger.warning(f"Trade {self.trade_hash} hit interactive auto-message limit ({count}/{AUTO_MESSAGE_LIMIT}). Pausing auto-responses.")
            # Send the final away message
            send_final_away_message(self.trade_hash, self.account, self.headers)
            self.trade_state['auto_responses_disabled'] = True
            
        self.save()
        return True

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
        else:
            self.ensure_initial_messages_sent()
        self.check_status_change()
        self.check_for_completion_message()

        # Stop all further processing once the trade is completed.
        # Handlers below must not fire on released/successful trades — they
        # caused spurious messages (online replies, delay replies, attachment
        # confirmations) to be sent into an already-closed chat.
        trade_status = str(self.trade_state.get("trade_status", "")).lower()
        status = str(self.trade_state.get("status", "")).lower()
        if trade_status in ['released', 'successful'] or status == 'successful':
            logger.debug(
                f"Trade {self.trade_hash} is completed — skipping all "
                f"post-completion message handlers."
            )
            self.save()
            return

        # On the very first cycle for a new trade, skip chat/attachment
        # processing.  Thread creation is async — dispatching chat embeds
        # before the thread ID exists causes them to race against the 45 s
        # waiter and may still fall back to the main channel when there are
        # many messages or the API is slow.  The next polling cycle will
        # pick up all messages once the thread ID is safely cached.
        if is_new:
            logger.debug(
                f"Trade {self.trade_hash} is new — deferring chat/attachment "
                f"processing to the next cycle so the Discord thread has time "
                f"to be created."
            )
            self.save()
            return

        # self.check_for_email_confirmation()  # EMAIL MODULE DISABLED
        self.check_chat_and_attachments()
        self.chat_processor.check_for_afk()
        self.chat_processor.check_for_extended_afk()
        self.check_for_inactivity()
        self.check_for_paid_without_attachment()
        self.save()
        logger.debug(f"--- Finished processing trade: {self.trade_hash} ---")

    def handle_new_trade(self):
        """Handles logic for a trade seen for the first time."""
        logger.info(
            f"--- New trade found: {self.trade_hash}. Handling initial messages. ---")

        # Snapshot immutable data for safe capture in background threads
        trade_snapshot = dict(self.trade_state)
        _trade_hash = self.trade_hash
        _platform = self.platform

        def _send_new_trade_notifications():
            send_telegram_alert(trade_snapshot, _platform)
            embed_data = create_new_trade_embed(trade_snapshot, _platform, send=False)
            if embed_data:
                create_trade_thread(_trade_hash, embed_data)

        _notification_executor.submit(_send_new_trade_notifications)

        # High-value alert: fire an extra notification for trades >3000 MXN
        try:
            amount = float(self.trade_state.get('fiat_amount_requested', 0))
            currency = (self.trade_state.get('fiat_currency_code') or '').upper()
            if amount > 3000 and currency == 'MXN':
                logger.info(f"High-value trade detected ({amount} {currency}) for {self.trade_hash}. Sending priority alerts.")
                _notification_executor.submit(send_high_value_trade_alert, trade_snapshot, _platform)
                _notification_executor.submit(create_high_value_trade_embed, trade_snapshot, _platform)
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not evaluate amount for high-value check on {self.trade_hash}: {e}")

        self.trade_state['first_seen_utc'] = datetime.now(
            timezone.utc).isoformat()
        self.ensure_initial_messages_sent(is_new=True)
        self.trade_state['status_history'] = [
            self.trade_state.get("trade_status")]

    def _was_welcome_message_sent_in_chat(self):
        """Scans chat history to verify if the welcome message has already been sent by the owner."""
        all_messages = self._get_chat_messages()
        if not all_messages:
            return False
        
        # Welcome messages have distinctive text patterns across standard, night, and AFK modes
        for msg in all_messages:
            author = msg.get("author")
            if author and (author == self.owner_username or author in BOT_OWNER_USERNAMES):
                text = str(msg.get("text") or "")
                if any(kw in text for kw in [
                    "TRADE STARTED", 
                    "INSTRUCTIONS:", 
                    "follow the offer terms", 
                    "WELCOME", 
                    "WILL GANG TRADING",
                    "CURRENTLY OFFLINE",
                    "TEMPORARILY UNAVAILABLE"
                ]):
                    return True
        return False

    def _was_payment_details_sent_in_chat(self):
        """Scans chat history to verify if the payment details message has already been sent by the owner."""
        all_messages = self._get_chat_messages()
        if not all_messages:
            return False

        # Load current payment account data to match specific bank details in chat
        json_key_slug, method_data = self._load_payment_method_data()
        expected_details = []
        if method_data:
            selected_id = str(method_data.get("selected_id", ""))
            accounts = method_data.get("accounts", [])
            for acc in accounts:
                if str(acc.get("id")) == selected_id:
                    if acc.get("SPEI"):
                        expected_details.append(str(acc["SPEI"]))
                    if acc.get("card_number"):
                        expected_details.append(str(acc["card_number"]))
                    break

        for msg in all_messages:
            author = msg.get("author")
            if author and (author == self.owner_username or author in BOT_OWNER_USERNAMES):
                text = str(msg.get("text") or "")
                
                # Check for active account's SPEI/card number in chat
                for detail in expected_details:
                    if detail in text:
                        return True
                        
                # Generic fallback check for common payment structure keywords
                if "PAYMENT DETAILS" in text or "OXXO PAYMENT" in text or "Payment details sent" in text:
                    if any(kw in text for kw in ["Bank:", "Store:", "SPEI:", "Card:"]):
                        return True
        return False

    def ensure_initial_messages_sent(self, is_new=False):
        """Ensures welcome and payment details are sent, retrying if they failed or were skipped."""
        trade_status = str(self.trade_state.get("trade_status", "")).lower()
        status = str(self.trade_state.get("status", "")).lower()
        if trade_status in ['released', 'successful'] or status == 'successful':
            return

        if self.trade_state.get('auto_responses_disabled'):
            return

        # Check if we should force verify the chat even on new trades
        settings = get_cached_app_settings()
        force_check = settings.get("force_welcome_chat_check", True)

        # Ensure welcome message has been sent
        if not self.trade_state.get('welcome_message_sent'):
            # Self-healing fallback: verify chat history
            # For brand new trades, skip the slow chat check unless force_check is enabled.
            if (not is_new or force_check) and self._was_welcome_message_sent_in_chat():
                logger.info(f"Welcome message already exists in chat for {self.trade_hash}. Marking as sent.")
                self.trade_state['welcome_message_sent'] = True
                self.save()
            else:
                logger.info(f"Sending missing welcome message for trade {self.trade_hash}...")
                if send_welcome_message(self.trade_state, self.account, self.headers):
                    self.trade_state['welcome_message_sent'] = True
                    self.save()

        # Ensure payment details are sent for bank-transfer/oxxo trades
        payment_method_slug = self.trade_state.get("payment_method_slug", "").lower()
        is_supported_payment = payment_method_slug in ["oxxo"] + BANK_TRANSFER_SLUGS

        if is_supported_payment:
            if not self.trade_state.get('payment_details_sent'):
                # Self-healing fallback: verify chat history
                # For brand new trades, skip the slow chat check unless force_check is enabled.
                if (not is_new or force_check) and self._was_payment_details_sent_in_chat():
                    logger.info(f"Payment details already exist in chat for {self.trade_hash}. Marking as sent.")
                    self.trade_state['payment_details_sent'] = True
                    self.save()
                else:
                    logger.info(f"Sending missing payment details for trade {self.trade_hash} ({payment_method_slug})...")
                    if send_payment_details_message(
                        self.trade_hash, payment_method_slug, self.headers, CHAT_URL_NOONES, self.owner_username
                    ):
                        self.trade_state['payment_details_sent'] = True
                        self.save()

    def check_status_change(self):
        """Checks for and handles changes in the trade's status."""
        logger.debug(f"--- Checking Status Change for {self.trade_hash} ---")
        current_status = self.trade_state.get("trade_status")
        if current_status not in self.trade_state.get('status_history', []):
            logger.info(
                f"Trade {self.trade_hash} has a new status: '{current_status}'")

            _notification_executor.submit(
                create_trade_status_update_embed,
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
            
        trade_status = str(self.trade_state.get("trade_status")).lower()
        status = str(self.trade_state.get("status")).lower()
        
        if trade_status in ['released', 'successful'] or status == 'successful':
            logger.info(f"Trade {self.trade_hash} is completed. Sending completion message.")
            send_trade_completion_message(self.trade_hash, self.account, self.headers)
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
            if not self.trade_state.get('auto_responses_disabled'):
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
                if (datetime.now(timezone.utc).timestamp() - paid_timestamp) > ATTACHMENT_WAIT_SECONDS:
                    all_messages = self._get_chat_messages()
                    has_attachment = any(msg.get("type") == "trade_attach_uploaded" for msg in (all_messages or []))

                    if not has_attachment:
                        logger.info(f"Trade {self.trade_hash} is 'Paid' for over 2 minutes with no attachment. Sending a reminder.")
                        self.send_interactive_auto_message(send_payment_confirmed_no_attachment_message, self.trade_hash, self.account, self.headers)
                        self.trade_state['no_attachment_reminder_sent'] = True
                        
    def _load_payment_method_data(self):
        """Shared helper: maps the payment slug, reads the JSON file, and returns
        (json_key_slug, method_data) for this trade's owner.
        Returns (None, None) when the payment method is not supported or data is missing."""
        slug = self.trade_state.get("payment_method_slug", "").lower()

        if slug == "oxxo":
            json_key_slug = "oxxo"
        elif slug in BANK_TRANSFER_SLUGS:
            json_key_slug = "bank-transfer"
        else:
            return None, None

        json_filename = f"{json_key_slug}.json"
        payment_data = get_cached_payment_account(json_filename)
        if payment_data is None:
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

        # Stamp the cursor NOW — before any processing or saves — so that every
        # intermediate self.save() inside this function persists the correct value
        # and the next cycle never re-sends the same messages.
        if all_messages:
            self.trade_state['last_processed_message_id'] = all_messages[-1].get('id')

        # Process new text messages
        for msg in new_messages:
            # Check if the message is NOT an attachment upload notification before processing as a text message
            if msg.get("type") != "trade_attach_uploaded" and msg.get("author") is not None:
                message_text = msg.get("text")
                # Ensure that the message is a string before sending
                if isinstance(message_text, str) and message_text:
                    msg_author = msg.get("author", "Unknown")
                    _notification_executor.submit(
                        send_chat_message_alert, message_text, self.trade_hash, self.owner_username, msg_author
                    )
                    _notification_executor.submit(
                        create_chat_message_embed, self.trade_hash, self.owner_username, msg_author, message_text, self.platform
                    )

        if new_messages:
            self.chat_processor.process_new_messages(new_messages)
            for msg in reversed(new_messages):
                author = msg.get("author")
                if author not in BOT_OWNER_USERNAMES and author is not None:
                    self.trade_state['last_buyer_ts'] = msg.get("timestamp")
                    break
            # Track the most recent owner message so _is_owner_recently_active()
            # can use the state value as a fast path without re-scanning chat.
            for msg in reversed(new_messages):
                author = msg.get("author")
                if author in BOT_OWNER_USERNAMES:
                    ts = msg.get("timestamp")
                    if ts:
                        self.trade_state['last_owner_ts'] = ts
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
            return

        if not self.trade_state.get('attachment_message_sent'):
            logger.info(f"New attachment found for trade {self.trade_hash}. Processing.")
            if not self.trade_state.get('auto_responses_disabled'):
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
                
            if author not in BOT_OWNER_USERNAMES:
                logger.debug(f"Processing new attachment by {author} for {self.trade_hash}.")
                
                # Check for duplicate receipt
                image_hash = hash_image(path)
                is_duplicate, previous_trade_info = is_duplicate_receipt(image_hash, self.trade_hash, self.owner_username)
                if is_duplicate:
                    _notification_executor.submit(
                        send_duplicate_receipt_alert, self.trade_hash, self.owner_username, path, previous_trade_info
                    )
                    _notification_executor.submit(
                        create_duplicate_receipt_embed, self.trade_hash, self.owner_username, path, self.platform, previous_trade_info
                    )

                text = extract_text_from_image(path)
                identified_bank = identify_bank_from_text(text)
                save_ocr_text(self.trade_hash, self.owner_username, text, identified_bank)
                _notification_executor.submit(
                    send_attachment_alert, self.trade_hash, self.owner_username, author, path, identified_bank
                )
                _notification_executor.submit(
                    create_attachment_embed, self.trade_hash, self.owner_username, author, path, self.platform, identified_bank
                )

                if identified_bank:
                    self.trade_state['ocr_identified_bank'] = identified_bank
                    logger.info(f"Receipt for trade {self.trade_hash} identified as {identified_bank}.")

                logger.debug(f"Performing amount validation for {self.trade_hash}.")
                found_amount = find_amount_in_text(text, self.trade_state.get("fiat_amount_requested"))
                if not self.trade_state.get('amount_validation_alert_sent'):
                    expected = self.trade_state.get("fiat_amount_requested")
                    currency = self.trade_state.get("fiat_currency_code")
                    self.trade_state['amount_validation_alert_sent'] = True  # Set flag before submit
                    _notification_executor.submit(
                        send_amount_validation_alert, self.trade_hash, self.owner_username, expected, found_amount, currency
                    )
                    _notification_executor.submit(
                        create_amount_validation_embed, self.trade_hash, self.owner_username, expected, found_amount, currency
                    )

                if expected_names:
                    logger.debug(f"Performing name validation for {self.trade_hash}.")
                    is_name_found = find_name_in_text(text, expected_names)
                    if not self.trade_state.get('name_validation_alert_sent'):
                        self.trade_state['name_validation_alert_sent'] = True  # Set flag before submit
                        _notification_executor.submit(
                            send_name_validation_alert, self.trade_hash, is_name_found, credential_identifier
                        )
                        _notification_executor.submit(
                            create_name_validation_embed, self.trade_hash, is_name_found, credential_identifier
                        )

                # Mark alerts as sent for this attachment
                processed_attachments[url]['alerts_sent'] = True
                logger.debug(f"Marked attachment {url} as alerts_sent=True")

        # Save once after processing all attachments, not on every iteration
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
            self.send_interactive_auto_message(send_payment_reminder_message, self.trade_hash, self.account, self.headers)
            self.trade_state['reminder_sent'] = True