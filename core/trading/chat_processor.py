import logging
from datetime import datetime, timezone
from config import ONLINE_QUERY_KEYWORDS, BOT_OWNER_USERNAMES, BANK_TRANSFER_SLUGS
from core.messaging.trade_lifecycle_messages import (
    send_spam_warning_message,
    send_online_reply_message,
    send_oxxo_redirect_message,
    send_third_party_allowed_message,
    send_delay_message,
    send_release_message,
    send_afk_message,
    send_extended_afk_message
)
from core.messaging.welcome_message import is_afk_mode_enabled

logger = logging.getLogger(__name__)

class ChatProcessor:
    def __init__(self, trade):
        """
        Initializes the ChatProcessor with a reference to the Trade instance.
        """
        self.trade = trade

    def process_new_messages(self, new_messages):
        """Processes all logic related to incoming new messages."""
        if not new_messages:
            return

        self.handle_spam_detection(new_messages)
        self.handle_online_query(new_messages)
        self.handle_oxxo_query(new_messages)
        self.handle_third_party_query(new_messages)
        self.handle_release_query(new_messages)
        self.handle_delay_query(new_messages)

    def handle_spam_detection(self, new_messages):
        logger.debug(f"--- Checking for Spam: {self.trade.trade_hash} ---")

        spam_threshold = 10
        spam_window_seconds = 3 * 60   # 3 minutes
        cooldown_seconds   = 30 * 60   # 30 minutes

        last_sent = self.trade.trade_state.get('spam_warning_last_sent_ts')
        if last_sent and (datetime.now(timezone.utc).timestamp() - last_sent) < cooldown_seconds:
            logger.debug(f"Spam warning on cooldown for {self.trade.trade_hash}. Skipping.")
            return

        all_messages = self.trade._get_chat_messages()
        if not all_messages:
            return

        now = datetime.now(timezone.utc).timestamp()
        
        # Optimize scanning backwards
        recent_buyer_count = 0
        for msg in reversed(all_messages):
            if msg.get("author") not in BOT_OWNER_USERNAMES and msg.get("author") is not None and msg.get("type") != "trade_attach_uploaded" and isinstance(msg.get("text"), str):
                ts = msg.get("timestamp") or 0
                if (now - ts) <= spam_window_seconds:
                    recent_buyer_count += 1
                else:
                    break

        if recent_buyer_count >= spam_threshold:
            logger.info(
                f"Spam detected for trade {self.trade.trade_hash}: "
                f"{recent_buyer_count} buyer messages in the last {spam_window_seconds // 60} minutes. "
                f"Sending warning."
            )
            self.trade.send_interactive_auto_message(send_spam_warning_message, self.trade.trade_hash, self.trade.account, self.trade.headers)
            self.trade.trade_state['spam_warning_last_sent_ts'] = now
            self.trade.save()

    def handle_online_query(self, new_messages):
        logger.debug(f"--- Checking for Online Query: {self.trade.trade_hash} ---")

        cooldown_seconds = 5 * 60
        last_sent = self.trade.trade_state.get('online_reply_last_sent_ts')
        if last_sent and (datetime.now(timezone.utc).timestamp() - last_sent) < cooldown_seconds:
            logger.debug(f"Online reply on cooldown for {self.trade.trade_hash}. Skipping.")
            return

        for msg in new_messages:
            message_text = msg.get("text", "")
            if isinstance(message_text, dict):
                message_text = str(message_text)

            message_text = message_text.lower()
            if any(keyword in message_text for keyword in ONLINE_QUERY_KEYWORDS):
                logger.info(f"Online query detected for trade {self.trade.trade_hash}. Sending reply.")
                self.trade.send_interactive_auto_message(send_online_reply_message, self.trade.trade_hash, self.trade.account, self.trade.headers)
                self.trade.trade_state['online_reply_last_sent_ts'] = datetime.now(timezone.utc).timestamp()
                self.trade.save()
                break

    def handle_oxxo_query(self, new_messages):
        logger.debug(f"--- Checking for OXXO Query in Bank Trade: {self.trade.trade_hash} ---")
        
        payment_method_slug = self.trade.trade_state.get("payment_method_slug", "").lower()
        is_bank_transfer = payment_method_slug in BANK_TRANSFER_SLUGS
        
        if not is_bank_transfer or self.trade.trade_state.get('oxxo_redirect_sent'):
            return

        for msg in new_messages:
            if msg.get("author") not in BOT_OWNER_USERNAMES and msg.get("author") is not None:
                message_text = msg.get("text", "")
                if isinstance(message_text, str) and "oxxo" in message_text.lower():
                    logger.info(f"OXXO keyword detected in bank transfer trade {self.trade.trade_hash}. Sending redirect message.")
                    self.trade.send_interactive_auto_message(send_oxxo_redirect_message, self.trade.trade_hash, self.trade.account, self.trade.headers)
                    self.trade.trade_state['oxxo_redirect_sent'] = True
                    self.trade.save()
                    break 

    def handle_third_party_query(self, new_messages):
        logger.debug(f"--- Checking for Third Party Query: {self.trade.trade_hash} ---")
        if self.trade.trade_state.get('third_party_reply_sent'):
            return

        third_party_keywords = ["3rd party", "third party"]

        for msg in new_messages:
            if msg.get("author") not in BOT_OWNER_USERNAMES and msg.get("author") is not None:
                message_text = msg.get("text", "")
                if isinstance(message_text, str):
                    message_lower = message_text.lower()
                    if any(keyword in message_lower for keyword in third_party_keywords):
                        logger.info(f"Third party query detected for trade {self.trade.trade_hash}. Sending reply.")
                        self.trade.send_interactive_auto_message(send_third_party_allowed_message, self.trade.trade_hash, self.trade.account, self.trade.headers)
                        self.trade.trade_state['third_party_reply_sent'] = True
                        self.trade.save()
                        break

    def handle_delay_query(self, new_messages):
        logger.debug(f"--- Checking for Delay Query: {self.trade.trade_hash} ---")

        if self.trade.trade_state.get("trade_status") != "Paid":
            return
        processed_attachments = self.trade.trade_state.get('processed_attachments', {})
        if not any(v.get('downloaded') for v in processed_attachments.values()):
            return

        cooldown_seconds = 5 * 60
        last_sent = self.trade.trade_state.get('delay_reply_last_sent_ts')
        if last_sent and (datetime.now(timezone.utc).timestamp() - last_sent) < cooldown_seconds:
            logger.debug(f"Delay reply on cooldown for {self.trade.trade_hash}. Skipping.")
            return

        for msg in new_messages:
            if msg.get("author") not in BOT_OWNER_USERNAMES and msg.get("author") is not None:
                message_text = msg.get("text", "")
                if isinstance(message_text, str) and message_text.strip():
                    logger.info(
                        f"Delay reply triggered for trade {self.trade.trade_hash}: "
                        f"buyer messaged after receipt upload while still Paid."
                    )
                    self.trade.send_interactive_auto_message(send_delay_message, self.trade.trade_hash, self.trade.account, self.trade.headers)
                    self.trade.trade_state['delay_reply_last_sent_ts'] = datetime.now(timezone.utc).timestamp()
                    self.trade.save()
                    break

    def handle_release_query(self, new_messages):
        logger.debug(f"--- Checking for Release Query: {self.trade.trade_hash} ---")

        cooldown_seconds = 5 * 60
        last_sent = self.trade.trade_state.get('release_reply_last_sent_ts')
        if last_sent and (datetime.now(timezone.utc).timestamp() - last_sent) < cooldown_seconds:
            logger.debug(f"Release reply on cooldown for {self.trade.trade_hash}. Skipping.")
            return

        for msg in new_messages:
            if msg.get("author") not in BOT_OWNER_USERNAMES and msg.get("author") is not None:
                message_text = msg.get("text", "")
                if isinstance(message_text, str) and "release" in message_text.lower():
                    logger.info(f"Release query detected for trade {self.trade.trade_hash}. Sending reply.")
                    self.trade.send_interactive_auto_message(send_release_message, self.trade.trade_hash, self.trade.account, self.trade.headers)
                    self.trade.trade_state['release_reply_last_sent_ts'] = datetime.now(timezone.utc).timestamp()
                    self.trade.save()
                    break

    def check_for_afk(self):
        logger.debug(f"--- Checking for AFK: {self.trade.trade_hash} ---")
        if not is_afk_mode_enabled():
            logger.debug(f"AFK mode is disabled. Skipping AFK check for {self.trade.trade_hash}.")
            return
        if self.trade.trade_state.get('afk_message_sent'):
            return

        all_messages = self.trade._get_chat_messages()

        if not all_messages:
            return

        last_owner_message_ts = None
        for msg in reversed(all_messages):
            if msg.get("author") in BOT_OWNER_USERNAMES:
                last_owner_message_ts = msg.get("timestamp")
                break

        buyer_messages = [msg for msg in all_messages if msg.get("author") not in BOT_OWNER_USERNAMES]

        if not buyer_messages:
            return

        if all_messages[-1].get("author") not in BOT_OWNER_USERNAMES:
            consecutive_buyer_messages = 0
            for msg in reversed(all_messages):
                if msg.get("author") not in BOT_OWNER_USERNAMES:
                    consecutive_buyer_messages += 1
                else:
                    break

            logger.debug(f"AFK Check for trade {self.trade.trade_hash}: Found {consecutive_buyer_messages} consecutive buyer messages.")

            first_consecutive_message_ts = all_messages[-consecutive_buyer_messages].get("timestamp")
            if not first_consecutive_message_ts:
                return

            time_since_first_message = (datetime.now(timezone.utc).timestamp() - first_consecutive_message_ts) / 60
            logger.debug(f"AFK Check for trade {self.trade.trade_hash}: Time since first message is {time_since_first_message:.2f} minutes.")

            message_threshold = 3
            time_threshold_minutes = 5
            
            owner_responded_during_consecutive = last_owner_message_ts and last_owner_message_ts > first_consecutive_message_ts
            
            if owner_responded_during_consecutive:
                logger.debug(f"AFK not triggered for {self.trade.trade_hash}: Owner sent a message during the consecutive buyer messages.")
            elif (consecutive_buyer_messages >= message_threshold and time_since_first_message > time_threshold_minutes):
                logger.info(f"AFK TRIGGERED for trade {self.trade.trade_hash}. Buyer sent {consecutive_buyer_messages} messages over {time_since_first_message:.2f} minutes without owner response. Sending AFK message.")
                self.trade.send_interactive_auto_message(send_afk_message, self.trade.trade_hash, self.trade.account, self.trade.headers)
                self.trade.trade_state['afk_message_sent'] = True
                self.trade.save()
            else:
                if consecutive_buyer_messages < message_threshold:
                    logger.debug(f"AFK not triggered for {self.trade.trade_hash}: Not enough messages ({consecutive_buyer_messages}/{message_threshold}).")
                if time_since_first_message <= time_threshold_minutes:
                    logger.debug(f"AFK not triggered for {self.trade.trade_hash}: Not enough time ({time_since_first_message:.2f}/{time_threshold_minutes} min).")

    def check_for_extended_afk(self):
        logger.debug(f"--- Checking for Extended AFK: {self.trade.trade_hash} ---")
        if not is_afk_mode_enabled():
            logger.debug(f"AFK mode is disabled. Skipping extended AFK check for {self.trade.trade_hash}.")
            return
        if self.trade.trade_state.get('extended_afk_message_sent') or not self.trade.trade_state.get('afk_message_sent'):
            return

        all_messages = self.trade._get_chat_messages()
        if not all_messages:
            return

        last_buyer_message_ts = None
        for msg in reversed(all_messages):
            if msg.get("author") not in BOT_OWNER_USERNAMES:
                last_buyer_message_ts = msg.get("timestamp")
                break

        if not last_buyer_message_ts:
            return

        time_since_last_buyer_message = (datetime.now(timezone.utc).timestamp() - last_buyer_message_ts) / 60
        logger.debug(f"Extended AFK Check for trade {self.trade.trade_hash}: Time since last buyer message is {time_since_last_buyer_message:.2f} minutes.")

        extended_time_threshold_minutes = 15

        if time_since_last_buyer_message > extended_time_threshold_minutes:
            logger.info(f"EXTENDED AFK TRIGGERED for trade {self.trade.trade_hash}. No response for over {extended_time_threshold_minutes} minutes. Sending extended AFK message.")
            self.trade.send_interactive_auto_message(send_extended_afk_message, self.trade.trade_hash, self.trade.account, self.trade.headers)
            self.trade.trade_state['extended_afk_message_sent'] = True
            self.trade.save()
