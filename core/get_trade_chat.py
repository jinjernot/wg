import json
import requests
import logging
import time
import os
from config import (
    GET_CHAT_URL_NOONES, GET_CHAT_URL_PAXFUL,
    CHAT_LOG_PATH, ATTACHMENT_PATH,
    IMAGE_API_URL_PAXFUL, IMAGE_API_URL_NOONES
)
from core.messaging.telegram_alert import send_chat_message_alert
from core.messaging.discord_alert import create_chat_message_embed
from core.persistent_state import load_last_message_ids, save_last_message_id

logger = logging.getLogger(__name__)

LAST_MESSAGE_IDS = load_last_message_ids()

def save_chat_log(trade_hash, messages, account_name):
    account_log_path = os.path.join(CHAT_LOG_PATH, account_name)
    os.makedirs(account_log_path, exist_ok=True)
    log_file_path = os.path.join(account_log_path, f"{trade_hash}_chat_log.json")

    chat_log_data = { "trade_hash": trade_hash, "messages": messages, "timestamp": time.time() }

    try:
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            json.dump(chat_log_data, log_file, indent=4)
        logger.info(f"Chat log for trade {trade_hash} saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save chat log for trade {trade_hash}: {e}")

def fetch_trade_chat_messages(trade_hash, account, headers, max_retries=3):
    """
    Fetches chat messages, processes only new messages (including attachments)
    based on the last processed message ID.
    """
    platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
    chat_url = GET_CHAT_URL_PAXFUL if platform == "Paxful" else GET_CHAT_URL_NOONES
    image_api_url = IMAGE_API_URL_PAXFUL if platform == "Paxful" else IMAGE_API_URL_NOONES
    account_name = account.get("name")
    data = {"trade_hash": trade_hash}

    for attempt in range(max_retries):
        try:
            response = requests.post(chat_url, data=data, headers=headers, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to fetch chat for {trade_hash}: {response.status_code}")
                continue

            chat_data = response.json()
            if chat_data.get("status") != "success":
                logger.error(f"API returned error fetching chat: {chat_data}")
                return False, None, None, []

            messages = chat_data.get("data", {}).get("messages", [])
            if not messages:
                return False, None, None, []

            save_chat_log(trade_hash, messages, account_name)

            # --- Determine new messages FIRST ---
            last_processed_id = LAST_MESSAGE_IDS.get(trade_hash)
            new_messages = []
            if last_processed_id is None:
                # If no record, all messages are new
                new_messages = messages
            else:
                last_index = -1
                for i, msg in enumerate(messages):
                    if str(msg.get("id")) == str(last_processed_id):
                        last_index = i
                        break
                if last_index != -1:
                    new_messages = messages[last_index + 1:]
                else:
                    # This can happen if chat history is pruned by the platform.
                    # To be safe, we don't process anything to avoid spamming.
                    logger.warning(f"Last processed message ID {last_processed_id} not found for trade {trade_hash}. Not processing chat.")
                    new_messages = []

            if not new_messages:
                return False, None, None, []

            # --- Now process ONLY new messages for attachments and text ---
            attachment_found = False
            author = None
            new_paths = []
            
            for msg in new_messages:
                # Process new attachments
                if msg.get("type") == "trade_attach_uploaded":
                    attachment_found = True
                    author = msg.get("author", "Unknown")
                    files = msg.get("text", {}).get("files", [])
                    for file_info in files:
                        image_url_path = file_info.get("url")
                        if not image_url_path:
                            continue

                        image_url = f"{image_api_url}{image_url_path}"
                        try:
                            s = requests.Session()
                            image_response = s.get(image_url, headers=headers, stream=True, timeout=15)
                            if image_response.status_code == 200:
                                os.makedirs(ATTACHMENT_PATH, exist_ok=True)
                                file_extension = os.path.splitext(image_url_path)[1] or '.jpg'
                                sanitized_hash = "".join(c for c in trade_hash if c.isalnum())
                                timestamp = int(time.time())
                                file_name = f"{sanitized_hash}_{timestamp}{file_extension}"
                                file_path = os.path.join(ATTACHMENT_PATH, file_name)
                                with open(file_path, 'wb') as f:
                                    f.write(image_response.content)
                                new_paths.append(file_path)
                                logger.info(f"New attachment for trade {trade_hash} downloaded to {file_path}")
                            else:
                                logger.error(f"Failed to download attachment from {image_url}. Status: {image_response.status_code}")
                        except requests.exceptions.RequestException as e:
                            logger.error(f"Error downloading attachment for trade {trade_hash}: {e}")

                # Process new text messages
                elif msg.get("author") not in ["davidvs", "JoeWillgang", None]:
                    message_text = msg.get("text")
                    if isinstance(message_text, dict): message_text = str(message_text)
                    if message_text:
                        msg_author = msg.get("author", "Unknown")
                        send_chat_message_alert(message_text, trade_hash, account["name"], msg_author)
                        create_chat_message_embed(trade_hash, msg_author, message_text)

            # Update the last message ID with the latest one from the full message list
            latest_message_id = messages[-1].get("id")
            if latest_message_id:
                save_last_message_id(trade_hash, latest_message_id)
                LAST_MESSAGE_IDS[trade_hash] = latest_message_id

            # Find the timestamp of the last message from the buyer for inactivity checks
            last_buyer_ts = None
            for msg in reversed(messages):
                if msg.get("author") not in ["davidvs", "JoeWillgang", None]:
                    last_buyer_ts = msg.get("timestamp")
                    break
            
            return attachment_found, author, last_buyer_ts, new_paths

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {trade_hash}: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    return False, None, None, []