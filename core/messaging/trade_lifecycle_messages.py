import logging
from core.messaging.message_sender import send_message_with_retry
from config import (
    CHAT_URL_PAXFUL,
    CHAT_URL_NOONES,
)
from config_messages.chat_messages import *

logger = logging.getLogger(__name__)

def _send_lifecycle_message(trade_hash, account, headers, message, message_type, max_retries=3):
    """Generic function to send a trade lifecycle message."""
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES
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
    _send_lifecycle_message(trade_hash, account, headers, "Thank you for your patience, I will be with you shortly.", "AFK", max_retries)