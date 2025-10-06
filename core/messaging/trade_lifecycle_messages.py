import logging
import random
from core.messaging.message_sender import send_message_with_retry
from config import (
    CHAT_URL_PAXFUL,
    CHAT_URL_NOONES,
)
from config_messages.chat_messages import *

logger = logging.getLogger(__name__)

def _send_lifecycle_message(trade_hash, account, headers, message_list, message_type, max_retries=3):
    """Generic function to send a trade lifecycle message."""
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES
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