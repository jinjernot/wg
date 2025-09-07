# core/get_trade_chat.py
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
from core.messaging.discord_alert import create_chat_message_embed # <-- Import new function

logger = logging.getLogger(__name__)

LAST_MESSAGE_IDS = {}

def save_chat_log(trade_hash, messages, account_name):
    # ... (this function remains the same)
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
    # ... (the first part of this function remains the same)
    platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
    chat_url = GET_CHAT_URL_PAXFUL if platform == "Paxful" else GET_CHAT_URL_NOONES
    image_api_url = IMAGE_API_URL_PAXFUL if platform == "Paxful" else IMAGE_API_URL_NOONES
    account_name = account.get("name")
    data = {"trade_hash": trade_hash}

    for attempt in range(max_retries):
        try:
            response = requests.post(chat_url, data=data, headers=headers, timeout=10)
            if response.status_code == 200:
                chat_data = response.json()
                if chat_data.get("status") != "success":
                    logger.error(f"API returned error fetching chat: {chat_data}")
                    return False, None, None, []

                messages = chat_data.get("data", {}).get("messages", [])
                if not messages:
                    return False, None, None, []

                save_chat_log(trade_hash, messages, account_name)

                attachment_found, author, new_paths = False, None, []
                # ... (attachment processing loop remains the same)

                last_buyer_ts = None
                for msg in reversed(messages):
                    author = msg.get("author", "Unknown")
                    if author not in ["davidvs", "JoeWillgang", None]:
                        last_buyer_ts = msg.get("timestamp")
                        break

                last_processed_id = LAST_MESSAGE_IDS.get(trade_hash)
                new_messages = []
                if last_processed_id is None:
                    new_messages = messages
                else:
                    temp_messages, new_seen = [], False
                    for msg in messages:
                        if str(msg.get("id")) == str(last_processed_id): new_seen = True
                        elif new_seen: temp_messages.append(msg)
                    new_messages = temp_messages

                if new_messages:
                    latest_message_id = messages[-1].get("id") if messages else None
                    for message in new_messages:
                        author = message.get("author", "Unknown")
                        if author in ["davidvs", "JoeWillgang"] or message.get("type") == "trade_attach_uploaded":
                            continue
                        message_text = message.get("text")
                        if isinstance(message_text, dict): message_text = str(message_text)
                        
                        if message_text and author:
                            # Send to both services
                            send_chat_message_alert(message_text, trade_hash, account["name"], author)
                            create_chat_message_embed(trade_hash, author, message_text) # <-- Add this call
                            
                    if latest_message_id: LAST_MESSAGE_IDS[trade_hash] = latest_message_id
                
                return attachment_found, author, last_buyer_ts, new_paths
            else:
                logger.error(f"Failed to fetch chat for {trade_hash}: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {trade_hash}: {e}")

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    return False, None, None, []