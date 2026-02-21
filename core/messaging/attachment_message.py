import logging
import random
from config import CHAT_URL_NOONES
from core.messaging.message_sender import send_message_with_retry
from config_messages.chat_messages import ATTACHMENT_MESSAGE

logger = logging.getLogger(__name__)

def send_attachment_message(trade_hash, account, headers, max_retries=3):
    """
    Sends an initial message to the chat saying "Checking, this may take a few minutes."
    """
    try:
        message = random.choice(ATTACHMENT_MESSAGE)
        body = {
            "trade_hash": trade_hash,
            "message": message
        }

        chat_url = CHAT_URL_NOONES

        if send_message_with_retry(chat_url, body, headers, max_retries):
            logger.info(f"Initial message sent for trade {trade_hash}.")
        else:
            logger.error(f"Failed to send initial message for trade {trade_hash}.")
    except Exception as e:
        logger.error(f"Error sending initial message: {e}")