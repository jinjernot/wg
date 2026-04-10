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

def send_trade_completion_message(trade_hash, account, headers, max_retries=3):
    """Sends a thank you and feedback request message when a trade is completed."""
    _send_lifecycle_message(trade_hash, account, headers, TRADE_COMPLETION_MESSAGE, "Completion", max_retries)

def send_payment_received_message(trade_hash, account, headers, max_retries=3):
    """Sends a confirmation that payment has been received."""
    _send_lifecycle_message(trade_hash, account, headers, PAYMENT_RECEIVED_MESSAGE, "Payment received", max_retries)

def send_payment_reminder_message(trade_hash, account, headers, max_retries=3):
    """Sends a reminder to the user to complete their payment."""
    _send_lifecycle_message(trade_hash, account, headers, PAYMENT_REMINDER_MESSAGE, "Payment reminder", max_retries)
    
def send_afk_message(trade_hash, account, headers, max_retries=3):
    """Sends a message to the user to ask them to be patient."""
    _send_lifecycle_message(trade_hash, account, headers, AFK_MESSAGE, "AFK", max_retries)

def send_extended_afk_message(trade_hash, account, headers, max_retries=3):
    """Sends a message to the user indicating a longer delay."""
    _send_lifecycle_message(trade_hash, account, headers, EXTENDED_AFK_MESSAGE, "Extended AFK", max_retries)

def send_payment_confirmed_no_attachment_message(trade_hash, account, headers, max_retries=3):
    """Sends a reminder to attach proof of payment."""
    _send_lifecycle_message(trade_hash, account, headers, NO_ATTACHMENT_MESSAGE, "No Attachment Reminder", max_retries)

def send_attachment_message(trade_hash, account, headers, max_retries=3):
    """Sends a message confirming an attachment was received and is being checked."""
    _send_lifecycle_message(trade_hash, account, headers, ATTACHMENT_MESSAGE, "Attachment received", max_retries)

def send_online_reply_message(trade_hash, account, headers, max_retries=3):
    """Sends a message to reply to "are you online?" questions."""
    _send_lifecycle_message(trade_hash, account, headers, ONLINE_REPLY_MESSAGE, "Online reply", max_retries)
    
def send_oxxo_redirect_message(trade_hash, account, headers, max_retries=3):
    """Sends a message redirecting the user to an OXXO offer."""
    _send_lifecycle_message(trade_hash, account, headers, OXXO_IN_BANK_TRANSFER_MESSAGE, "OXXO Redirect", max_retries)
    
def send_third_party_allowed_message(trade_hash, account, headers, max_retries=3):
    """Sends a message to the user to inform them that third party is allowed."""
    _send_lifecycle_message(trade_hash, account, headers, THIRD_PARTY_ALLOWED_MESSAGE, "Third Party Allowed", max_retries)

def send_release_message(trade_hash, account, headers, max_retries=3):
    """Sends a message to reply when user asks about release."""
    _send_lifecycle_message(trade_hash, account, headers, RELEASE_MESSAGE, "Release reply", max_retries)

def send_delay_message(trade_hash, account, headers, max_retries=3):
    """Sends a neutral stalling message while the trade is pending manual review."""
    _send_lifecycle_message(trade_hash, account, headers, DELAY_MESSAGE, "Delay", max_retries)

def send_spam_warning_message(trade_hash, account, headers, max_retries=3):
    """Sends a warning message when a buyer sends too many messages in a short period."""
    _send_lifecycle_message(trade_hash, account, headers, SPAM_WARNING_MESSAGE, "Spam Warning", max_retries)