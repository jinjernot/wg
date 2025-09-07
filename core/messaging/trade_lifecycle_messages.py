# core/messaging/trade_lifecycle_messages.py
import logging
from core.messaging.message_sender import send_message_with_retry
from config import (
    CHAT_URL_PAXFUL,
    CHAT_URL_NOONES,
)
from config_messages.chat_messages import *

logger = logging.getLogger(__name__)

def send_trade_completion_message(trade_hash, account, headers, max_retries=3):
    """Sends a thank you and feedback request message when a trade is completed."""
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES
    body = {"trade_hash": trade_hash, "message": TRADE_COMPLETION_MESSAGE}
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    if send_message_with_retry(chat_url, body, headers, max_retries):
        logger.info(f"Completion message sent for trade {trade_hash}.")
    else:
        logger.error(f"Failed to send completion message for trade {trade_hash}.")


def send_payment_received_message(trade_hash, account, headers, max_retries=3):
    """Sends a confirmation that payment has been received."""
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES
    body = {"trade_hash": trade_hash, "message": PAYMENT_RECEIVED_MESSAGE}
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    if send_message_with_retry(chat_url, body, headers, max_retries):
        logger.info(f"Payment received message sent for trade {trade_hash}.")
    else:
        logger.error(f"Failed to send payment received message for trade {trade_hash}.")


def send_payment_reminder_message(trade_hash, account, headers, max_retries=3):
    """Sends a reminder to the user to complete their payment."""
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES
    body = {"trade_hash": trade_hash, "message": PAYMENT_REMINDER_MESSAGE}
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    if send_message_with_retry(chat_url, body, headers, max_retries):
        logger.info(f"Payment reminder sent for trade {trade_hash}.")
    else:
        logger.error(f"Failed to send payment reminder for trade {trade_hash}.")