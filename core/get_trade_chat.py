import json
import requests
import logging
import time
import os
from config import GET_CHAT_URL_NOONES, GET_CHAT_URL_PAXFUL, CHAT_LOG_PATH
from core.telegram_alert import send_chat_message_alert

# Store last processed message IDs to avoid duplicate alerts
LAST_MESSAGE_IDS = {}

def save_chat_log(trade_hash, messages):
    """
    Save chat messages to a log file named by the trade_hash.
    """
    # Ensure the log directory exists
    os.makedirs(CHAT_LOG_PATH, exist_ok=True)

    # Set the log file path based on the trade_hash
    log_file_path = os.path.join(CHAT_LOG_PATH, f"{trade_hash}_chat_log.json")

    chat_log_data = {
        "trade_hash": trade_hash,
        "messages": messages,
        "timestamp": time.time()
    }

    # Save messages as JSON in the specified chat log path
    try:
        with open(log_file_path, "w") as log_file:
            json.dump(chat_log_data, log_file, indent=4)
        logging.info(f"Chat log for trade {trade_hash} saved successfully at {log_file_path}.")
    except Exception as e:
        logging.error(f"Failed to save chat log for trade {trade_hash}: {e}")

def fetch_trade_chat_messages(trade_hash, account, headers, max_retries=3):
    """
    Fetch messages from trade chat and send a Telegram alert if a new message is received.
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
                    logging.debug(f"No new messages for trade {trade_hash}.")
                    return False

                # Save the chat log to a file
                save_chat_log(trade_hash, messages)

                latest_message = messages[-1]  # Get the most recent message
                message_id = latest_message.get("id")
                message_text = latest_message.get("text")

                author = latest_message.get("author", "Unknown")

                if author in ["davidvs", "JoeWillgang"]:
                    logging.debug(f"Skipping message from {author} for trade {trade_hash}.")
                    return False

                # Check if this message was already processed
                if trade_hash in LAST_MESSAGE_IDS and LAST_MESSAGE_IDS[trade_hash] == message_id:
                    logging.debug(f"No new messages for trade {trade_hash}. Skipping Telegram alert.")
                    return False

                # Update last processed message
                LAST_MESSAGE_IDS[trade_hash] = message_id

                # Send Telegram alert for new chat message
                send_chat_message_alert(message_text, trade_hash, account["name"], author)

                return True

            elif response.status_code == 404:
                logging.error(f"Trade chat not found for {trade_hash}. API Response: {response.text}")
                return False
            else:
                logging.error(f"Failed to fetch messages for {trade_hash}. Status: {response.status_code} - {response.text}")

            # Retry if needed
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logging.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed on attempt {attempt + 1}: {e}")

    logging.error(f"Max retries reached for fetching chat messages for trade {trade_hash}.")
    return False
