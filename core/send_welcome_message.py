import requests
import json
import time
import logging
from config import *

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def send_welcome_message(trade, headers, max_retries=3):
    trade_hash = trade.get("trade_hash")
    payment_method_slug = trade.get("payment_method_slug", "").lower()

    # Define the welcome message
    message = WELCOME_MESSAGES.get(payment_method_slug, WELCOME_MESSAGES["default"])
    body = {"trade_hash": trade_hash, "message": message}
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    # Function to send a message with retry logic
    def send_message_with_retry(url, data, headers, max_retries):
        for attempt in range(max_retries):
            try:
                logging.debug(f"Attempt {attempt + 1} of {max_retries} to send message")
                response = requests.post(url, data=data, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    return True  # Message sent successfully
                else:
                    logging.error(f"Failed to send message. Status Code: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logging.debug(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        logging.error("Max retries reached. Giving up.")
                        return False
            except requests.exceptions.RequestException as e:
                logging.error(f"Request failed on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logging.debug(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    logging.error("Max retries reached. Giving up.")
                    return False
        return False

    # Send the welcome message
    if send_message_with_retry(CHAT_URL, body, headers, max_retries):
        print(f"Welcome message sent for trade {trade_hash}")
    else:
        print(f"Failed to send welcome message for trade {trade_hash} after {max_retries} retries.")
        return

    # Send second message if payment method is OXXO
    if payment_method_slug == "oxxo":
        try:
            with open(DB_PATH, "r") as f:
                oxxo_data = json.load(f)

            selected_id = oxxo_data["oxxo"].get("selected_id")
            oxxo_accounts = oxxo_data["oxxo"].get("accounts", [])

            # Find the account with the matching ID
            selected_account = next((acc for acc in oxxo_accounts if acc["id"] == selected_id), None)

            if not selected_account:
                print(f"No OXXO account found for selected_id: {selected_id}")
                return

            second_message = f"Payment Details:\n\n" \
                            f"Bank: {selected_account['bank']}\n" \
                            f"Name: {selected_account['name']}\n" \
                            f"Card Number: {selected_account['card_number']}\n\n"

            # Send the second message
            body = {"trade_hash": trade_hash, "message": second_message}
            if send_message_with_retry(CHAT_URL, body, headers, max_retries):
                print(f"Payment details sent for trade {trade_hash}")
            else:
                print(f"Failed to send payment details for trade {trade_hash} after {max_retries} retries.")

        except Exception as e:
            print(f"Error reading OXXO data: {e}")