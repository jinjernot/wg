import json
import requests
import logging
import time
import os
from config import GET_CHAT_URL_NOONES, GET_CHAT_URL_PAXFUL, CHAT_LOG_PATH
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
        with open(log_file_path, "w") as log_file:
            json.dump(chat_log_data, log_file, indent=4)
        logging.info(f"Chat log for trade {trade_hash} saved successfully at {log_file_path}.")
    except Exception as e:
        logging.error(f"Failed to save chat log for trade {trade_hash}: {e}")

def fetch_trade_chat_messages(trade_hash, account, headers, max_retries=3):
    """
    Fetch messages from trade chat, send alerts, and report new attachments
    and the timestamp of the last buyer message.
    Returns a tuple: (attachment_found, attachment_author, last_buyer_message_timestamp)
    """
    chat_url = GET_CHAT_URL_PAXFUL if "_Paxful" in account["name"] else GET_CHAT_URL_NOONES
    account_name = account.get("name")
    data = {"trade_hash": trade_hash}

    for attempt in range(max_retries):
        try:
            logging.debug(f"Attempt {attempt + 1} to fetch chat for trade {trade_hash}")
            response = requests.post(chat_url, data=data, headers=headers, timeout=10)

            if response.status_code == 200:
                chat_data = response.json()
                if chat_data.get("status") != "success":
                    logging.error(f"API returned error: {chat_data}")
                    return False, None, None

                messages = chat_data.get("data", {}).get("messages", [])
                if not messages:
                    return False, None, None

                save_chat_log(trade_hash, messages, account_name)

                # Find the timestamp of the last message from the buyer
                last_buyer_message_ts = None
                for msg in reversed(messages):
                    author = msg.get("author", "Unknown")
                    if author not in ["davidvs", "JoeWillgang", None]:
                        last_buyer_message_ts = msg.get("timestamp")
                        break

                last_processed_id = LAST_MESSAGE_IDS.get(trade_hash)
                new_messages = []
                new_seen = False
                for msg in messages:
                    if msg.get("id") == last_processed_id:
                        new_seen = True
                        new_messages = []
                    elif new_seen or last_processed_id is None:
                        new_messages.append(msg)

                if last_processed_id is None and messages:
                    new_messages = [messages[-1]]

                if not new_messages:
                    return False, None, last_buyer_message_ts

                attachment_found = False
                attachment_author = None
                latest_message_id = None

                for message in new_messages:
                    latest_message_id = message.get("id")
                    author = message.get("author", "Unknown")

                    if author in ["davidvs", "JoeWillgang"]:
                        continue

                    if message.get("type") == "trade_attach_uploaded":
                        attachment_found = True
                        attachment_author = author
                    else:
                        message_text = message.get("text")
                        if isinstance(message_text, dict):
                            message_text = str(message_text)
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