import logging
import time
from core.utils.http_client import get_http_client

logger = logging.getLogger(__name__)

def send_message_with_retry(url, data, headers, max_retries=3):
    """
    Sends a POST message to the given URL with retry logic.
    Uses the shared pooled HTTP client instead of raw requests.post()
    to benefit from connection pooling and avoid spawning a new TCP
    connection for every message.
    """
    http_client = get_http_client()
    for attempt in range(max_retries):
        try:
            logger.debug(f"[MessageSender] Attempt {attempt + 1} to send message.")
            response = http_client.post(url, data=data, headers=headers, timeout=10)

            if response.status_code == 200:
                return True
            else:
                logger.error(f"[MessageSender] Failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"[MessageSender] Exception: {e}")

        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            logger.debug(f"[MessageSender] Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    logger.error("[MessageSender] Max retries reached. Giving up.")
    return False