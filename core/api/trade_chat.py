import json
import requests
import logging
import time
import os
import re
from config import (
    GET_CHAT_URL_NOONES, GET_CHAT_URL_PAXFUL,
    CHAT_LOG_PATH, ATTACHMENT_PATH
)
from core.messaging.alerts.telegram_alert import send_chat_message_alert
from core.messaging.alerts.discord_alert import create_chat_message_embed
from core.state.persistent_state import load_last_message_ids, save_last_message_id
from core.api.auth import fetch_token_with_retry

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

def get_new_messages(trade_hash, account, headers, max_retries=3):
    platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
    chat_url = GET_CHAT_URL_PAXFUL if platform == "Paxful" else GET_CHAT_URL_NOONES
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
                return None, None

            messages = chat_data.get("data", {}).get("messages", [])
            if not messages:
                return [], None

            save_chat_log(trade_hash, messages, account_name)

            last_processed_id = LAST_MESSAGE_IDS.get(trade_hash)
            if last_processed_id is None:
                return messages, messages[-1].get("id")

            last_index = -1
            for i, msg in enumerate(messages):
                if str(msg.get("id")) == str(last_processed_id):
                    last_index = i
                    break
            
            if last_index != -1:
                return messages[last_index + 1:], messages[-1].get("id")
            else:
                logger.warning(f"Last processed message ID {last_processed_id} not found for trade {trade_hash}. Not processing chat.")
                return [], None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {trade_hash}: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    return None, None


def download_attachment(image_url_path, image_api_url, trade_hash, headers):
    match = re.search(r'attachment/([^?]+)', image_url_path)
    if not match:
        return None
    image_hash = match.group(1)
    image_payload = {"image_hash": image_hash, "size": "2"}
    image_headers = headers.copy()
    image_headers["Content-Type"] = "application/x-www-form-urlencoded"

    try:
        image_response = requests.post(image_api_url, data=image_payload, headers=image_headers, timeout=15)
        
        if image_response.status_code == 200:
            os.makedirs(ATTACHMENT_PATH, exist_ok=True)
            file_extension = os.path.splitext(image_url_path)[1] or '.jpg'
            sanitized_hash = "".join(c for c in trade_hash if c.isalnum())
            timestamp = int(time.time())
            file_name = f"{sanitized_hash}_{timestamp}{file_extension}"
            file_path = os.path.join(ATTACHMENT_PATH, file_name)
            with open(file_path, 'wb') as f:
                f.write(image_response.content)
            logger.info(f"New attachment for trade {trade_hash} downloaded to {file_path}")
            return file_path
        else:
            logger.error(f"Failed to download attachment with hash {image_hash}. Status: {image_response.status_code} - {image_response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading attachment for trade {trade_hash}: {e}")
    return None

def get_all_messages_from_chat(trade_hash, account, headers, max_retries=3):
    """
    Fetches all messages from a trade chat without considering the last processed message ID.
    This is a read-only operation and does not update the state.
    """
    platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
    chat_url = GET_CHAT_URL_PAXFUL if platform == "Paxful" else GET_CHAT_URL_NOONES
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
                return []

            return chat_data.get("data", {}).get("messages", [])
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {trade_hash}: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)

    return []

def release_trade(trade_hash, account):
    """
    Releases the crypto for a given trade.
    """
    platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
    release_url = f"https://api.{platform.lower()}.com/{platform.lower()}/v1/trade/release"
    
    token = fetch_token_with_retry(account)
    if not token:
        return {"success": False, "error": "Authentication failed."}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"trade_hash": trade_hash}

    try:
        response = requests.post(release_url, data=data, headers=headers, timeout=15)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("status") == "success":
                logger.info(f"Successfully released trade {trade_hash}")
                return {"success": True, "message": "Trade released successfully."}
            else:
                error_message = response_data.get("error_description", "Unknown API error")
                logger.error(f"Failed to release trade {trade_hash}: {error_message}")
                return {"success": False, "error": error_message}
        else:
            logger.error(f"Failed to release trade {trade_hash}: {response.status_code} - {response.text}")
            return {"success": False, "error": f"API Error: {response.status_code}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed for trade release {trade_hash}: {e}")
        return {"success": False, "error": "Request failed"}