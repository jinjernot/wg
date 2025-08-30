import logging
from config import CHAT_URL_PAXFUL, CHAT_URL_NOONES
from core.messaging.message_sender import send_message_with_retry
from config_messages.chat_messages import ATTACHMENT_MESSAGE

def send_attachment_message(trade_hash, account, headers, max_retries=3):
    """
    Sends an initial message to the chat saying "Checking, this may take a few minutes."
    """
    try:
        body = {
            "trade_hash": trade_hash,
            "message": ATTACHMENT_MESSAGE
        }

        # Pick correct sending URL
        chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES

        # Send message
        if send_message_with_retry(chat_url, body, headers, max_retries):
            logging.info(f"Initial message sent for trade {trade_hash}.")
        else:
            logging.error(f"Failed to send initial message for trade {trade_hash}.")
    except Exception as e:
        logging.error(f"Error sending initial message: {e}")