import logging
import random
from core.messaging.message_sender import send_message_with_retry
from config import CHAT_URL_NOONES
from config_messages.chat_messages import (
    TRADE_COMPLETION_MESSAGE,
    PAYMENT_RECEIVED_MESSAGE,
    PAYMENT_REMINDER_MESSAGE,
    ATTACHMENT_MESSAGE,
    AFK_MESSAGE,
    EXTENDED_AFK_MESSAGE,
    NO_ATTACHMENT_MESSAGE,
    ONLINE_REPLY_MESSAGE,
    OXXO_IN_BANK_TRANSFER_MESSAGE,
    THIRD_PARTY_ALLOWED_MESSAGE,
    RELEASE_MESSAGE,
    DELAY_MESSAGE,
    SPAM_WARNING_MESSAGE,
    FINAL_AWAY_MESSAGE,
)

logger = logging.getLogger(__name__)

def _send_lifecycle_message(trade_hash, account, headers, message_list, message_type, max_retries=3):
    """Generic function to send a trade lifecycle message."""
    chat_url = CHAT_URL_NOONES
    message = random.choice(message_list)
    body = {"trade_hash": trade_hash, "message": message}
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    if send_message_with_retry(chat_url, body, headers, max_retries):
        logger.info(f"{message_type} message sent for trade {trade_hash}.")
    else:
        logger.error(f"Failed to send {message_type} message for trade {trade_hash}.")

def _make_sender(message_list, log_label):
    """Factory to create a sender function for a specific lifecycle message type."""
    def sender(trade_hash, account, headers, max_retries=3):
        _send_lifecycle_message(trade_hash, account, headers, message_list, log_label, max_retries)
    return sender

# Define the lifecycle message senders statically for type hinting and IDE autocomplete support
send_trade_completion_message = _make_sender(TRADE_COMPLETION_MESSAGE, "Completion")
send_payment_received_message = _make_sender(PAYMENT_RECEIVED_MESSAGE, "Payment received")
send_payment_reminder_message = _make_sender(PAYMENT_REMINDER_MESSAGE, "Payment reminder")
send_afk_message = _make_sender(AFK_MESSAGE, "AFK")
send_extended_afk_message = _make_sender(EXTENDED_AFK_MESSAGE, "Extended AFK")
send_payment_confirmed_no_attachment_message = _make_sender(NO_ATTACHMENT_MESSAGE, "No Attachment Reminder")
send_attachment_message = _make_sender(ATTACHMENT_MESSAGE, "Attachment received")
send_online_reply_message = _make_sender(ONLINE_REPLY_MESSAGE, "Online reply")
send_oxxo_redirect_message = _make_sender(OXXO_IN_BANK_TRANSFER_MESSAGE, "OXXO Redirect")
send_third_party_allowed_message = _make_sender(THIRD_PARTY_ALLOWED_MESSAGE, "Third Party Allowed")
send_release_message = _make_sender(RELEASE_MESSAGE, "Release reply")
send_delay_message = _make_sender(DELAY_MESSAGE, "Delay")
send_spam_warning_message = _make_sender(SPAM_WARNING_MESSAGE, "Spam Warning")
send_final_away_message = _make_sender(FINAL_AWAY_MESSAGE, "Final Away")