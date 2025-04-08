import json
import requests
import logging
import time
import os
from config import GET_CHAT_URL_NOONES, GET_CHAT_URL_PAXFUL, CHAT_LOG_PATH
from core.messaging.telegram_alert import send_chat_message_alert, send_attachment_alert
from core.messaging.attachment_message import send_attachment_message

# Store last processed message IDs to avoid duplicate alerts
LAST_MESSAGE_IDS = {}

def save_chat_log(trade_hash, messages):
    """
    Save chat messages to a log file named by the trade_hash.
    """
    os.makedirs(CHAT_LOG_PATH, exist_ok=True)
    log_file_path = os.path.join(CHAT_LOG_PATH, f"{trade_hash}_chat_log.json")

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
    Fetch messages from trade chat and send Telegram alerts or attachment messages
    for all new messages since last check.
    """
    chat_url = GET_CHAT_URL_PAXFUL if "_Paxful" in account["name"] else GET_CHAT_URL_NOONES
    data = {"trade_hash": trade_hash}

    for attempt in range(max_retries):
        try:
            logging.debug(f"Attempt {attempt + 1} to fetch chat messages for trade {trade_hash} ({account['name']})")

            response = requests.post(chat_url, data=data, headers=headers, timeout=10)

            if response.status_code == 200:
                chat_data = response.json()

                if chat_data.get("status") != "success":
                    logging.error(f"API returned error: {chat_data}")
                    return False

                messages = chat_data.get("data", {}).get("messages", [])

                if not messages:
                    logging.debug(f"No messages found for trade {trade_hash}.")
                    return False

                save_chat_log(trade_hash, messages)

                # Get last processed message ID for this trade
                last_processed_id = LAST_MESSAGE_IDS.get(trade_hash)

                # Process all unprocessed messages (oldest to newest)
                new_messages = []
                new_seen = False
                for msg in messages:
                    if msg.get("id") == last_processed_id:
                        new_seen = True
                        new_messages = []
                    elif new_seen or last_processed_id is None:
                        new_messages.append(msg)

                # If we’ve never processed this trade, take last 1 message only to avoid flooding
                if last_processed_id is None and messages:
                    new_messages = [messages[-1]]

                if not new_messages:
                    logging.debug(f"No new messages to process for trade {trade_hash}.")
                    return False

                for message in new_messages:
                    message_id = message.get("id")
                    message_type = message.get("type")
                    author = message.get("author", "Unknown")

                    if author in ["davidvs", "JoeWillgang"]:
                        continue

                    if message_type == "trade_attach_uploaded":
                        send_attachment_message(trade_hash, chat_url, headers, max_retries)
                        send_attachment_alert(trade_hash, author)
                    else:
                        message_text = message.get("text")
                        if isinstance(message_text, dict):
                            message_text = str(message_text)
                        send_chat_message_alert(message_text, trade_hash, account["name"], author)

                    # Always update the last message ID after processing
                    LAST_MESSAGE_IDS[trade_hash] = message_id

                return True

            elif response.status_code == 404:
                logging.error(f"Trade chat not found for {trade_hash}. API Response: {response.text}")
                return False
            else:
                logging.error(f"Failed to fetch messages for {trade_hash}. Status: {response.status_code} - {response.text}")

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logging.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed on attempt {attempt + 1}: {e}")

    logging.error(f"Max retries reached for fetching chat messages for trade {trade_hash}.")
    return False
