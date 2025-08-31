import json
import requests
import logging
import time
import os
from config import (
    GET_CHAT_URL_NOONES, GET_CHAT_URL_PAXFUL, 
    CHAT_LOG_PATH, ATTACHMENT_PATH,
    IMAGE_API_URL_PAXFUL, IMAGE_API_URL_NOONES # Import new endpoints
)
from core.messaging.telegram_alert import send_chat_message_alert

# Store last processed message IDs to avoid duplicate alerts
LAST_MESSAGE_IDS = {}

def save_chat_log(trade_hash, messages, account_name):
    """
    Save chat messages to a log file named by the trade_hash within an account-specific folder.
    """
    account_log_path = os.path.join(CHAT_LOG_PATH, account_name)
    os.makedirs(account_log_path, exist_ok=True)
    log_file_path = os.path.join(account_log_path, f"{trade_hash}_chat_log.json")

    chat_log_data = {
        "trade_hash": trade_hash,
        "messages": messages,
        "timestamp": time.time()
    }

    try:
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            json.dump(chat_log_data, log_file, indent=4)
        logging.info(f"Chat log for trade {trade_hash} saved successfully at {log_file_path}.")
    except Exception as e:
        logging.error(f"Failed to save chat log for trade {trade_hash}: {e}")

def fetch_trade_chat_messages(trade_hash, account, headers, max_retries=3):
    """
    Fetch messages from trade chat, download attachments using the dedicated API endpoint,
    and send alerts for new messages.
    """
    platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
    chat_url = GET_CHAT_URL_PAXFUL if platform == "Paxful" else GET_CHAT_URL_NOONES
    image_api_url = IMAGE_API_URL_PAXFUL if platform == "Paxful" else IMAGE_API_URL_NOONES
    account_name = account.get("name")
    data = {"trade_hash": trade_hash}

    for attempt in range(max_retries):
        try:
            logging.debug(f"Attempt {attempt + 1} to fetch chat for trade {trade_hash}")
            response = requests.post(chat_url, data=data, headers=headers, timeout=10)

            if response.status_code == 200:
                chat_data = response.json()
                if chat_data.get("status") != "success":
                    logging.error(f"API returned error fetching chat: {chat_data}")
                    return False, None, None

                messages = chat_data.get("data", {}).get("messages", [])
                if not messages:
                    return False, None, None

                save_chat_log(trade_hash, messages, account_name)

                # --- New API-based Attachment Downloading ---
                attachment_found = False
                attachment_author = None
                for message in messages:
                    if message.get("type") == "trade_attach_uploaded":
                        attachment_found = True
                        attachment_author = message.get("author", "Unknown")
                        if message.get("text") and isinstance(message["text"], dict) and "files" in message["text"]:
                            for file_info in message["text"]["files"]:
                                relative_url = file_info.get("url")
                                if relative_url:
                                    try:
                                        # Extract the hash from the URL (e.g., "/trade/attachment/HASH?s=2")
                                        image_hash = relative_url.split('/')[-1].split('?')[0]
                                        
                                        account_attachment_path = os.path.join(ATTACHMENT_PATH, account_name)
                                        trade_attachment_path = os.path.join(account_attachment_path, trade_hash)
                                        os.makedirs(trade_attachment_path, exist_ok=True)
                                        
                                        filepath = os.path.join(trade_attachment_path, f"{image_hash}.png")

                                        if not os.path.exists(filepath):
                                            logging.info(f"New attachment found for trade {trade_hash}. Downloading image hash: {image_hash}...")
                                            
                                            image_data = {"image_hash": image_hash, "size": "1"} # "1" for original size
                                            
                                            image_response = requests.post(image_api_url, headers=headers, data=image_data, timeout=20)
                                            
                                            if image_response.status_code == 200:
                                                # Check if the response is an actual image
                                                if 'image' in image_response.headers.get('Content-Type', ''):
                                                    with open(filepath, 'wb') as f:
                                                        f.write(image_response.content)
                                                    logging.info(f"Attachment for trade {trade_hash} saved to {filepath}")
                                                else:
                                                    logging.error(f"API did not return an image for hash {image_hash}. Content-Type: {image_response.headers.get('Content-Type')}")
                                            else:
                                                logging.error(f"Failed to download image hash {image_hash}. Status: {image_response.status_code}, Response: {image_response.text}")
                                    except Exception as e:
                                        logging.error(f"An unexpected error occurred while processing attachment for {trade_hash}: {e}")

                # --- New Message Alerting Logic ---
                last_buyer_message_ts = None
                for msg in reversed(messages):
                    author = msg.get("author", "Unknown")
                    if author not in ["davidvs", "JoeWillgang", None]:
                        last_buyer_message_ts = msg.get("timestamp")
                        break

                last_processed_id = LAST_MESSAGE_IDS.get(trade_hash)
                new_messages = []
                if last_processed_id is None:
                    new_messages = messages
                else:
                    temp_messages, new_seen = [], False
                    for msg in messages:
                        if str(msg.get("id")) == str(last_processed_id):
                            new_seen = True
                        elif new_seen:
                            temp_messages.append(msg)
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
                            send_chat_message_alert(message_text, trade_hash, account["name"], author)
                    
                    if latest_message_id:
                        LAST_MESSAGE_IDS[trade_hash] = latest_message_id

                return attachment_found, attachment_author, last_buyer_message_ts

            else:
                logging.error(f"Failed to fetch chat for {trade_hash}: {response.status_code}")

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed for {trade_hash}: {e}")

        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    return False, None, None