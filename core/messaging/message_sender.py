import logging
import time
import requests

logger = logging.getLogger(__name__)

def send_message_with_retry(url, data, headers, max_retries=3):
    for attempt in range(max_retries):
        try:
            logger.debug(f"[MessageSender] Attempt {attempt + 1} to send message.")
            response = requests.post(url, data=data, headers=headers, timeout=10)

            if response.status_code == 200:
                return True
            else:
                logger.error(f"[MessageSender] Failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[MessageSender] Exception: {e}")

        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            logger.debug(f"[MessageSender] Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    logger.error("[MessageSender] Max retries reached. Giving up.")
    return False