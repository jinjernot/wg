import requests
import json
import time
import logging
import os
from config import *

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def send_welcome_message(trade, account, headers, max_retries=3):
    """Send a welcome message and additional payment details if needed."""
    
    trade_hash = trade.get("trade_hash")
    payment_method_slug = trade.get("payment_method_slug", "").lower()

    # Select API endpoint
    if "_Paxful" in account["name"]:
        chat_url = CHAT_URL_PAXFUL
    else:
        chat_url = CHAT_URL_NOONES

    # Define the welcome message
    message = WELCOME_MESSAGES.get(payment_method_slug, WELCOME_MESSAGES["default"])
    body = {"trade_hash": trade_hash, "message": message}
    headers["Content-Type"] = "application/x-www-form-urlencoded"

    def send_message_with_retry(url, data, headers, max_retries):
        """Send a message with retry logic."""
        for attempt in range(max_retries):
            try:
                logging.debug(f"Attempt {attempt + 1} of {max_retries} to send message for {account['name']}")
                response = requests.post(url, data=data, headers=headers, timeout=10)

                if response.status_code == 200:
                    return True  # Message sent successfully
                else:
                    logging.error(f"Failed to send message for {account['name']}. Status Code: {response.status_code} - {response.text}")
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
    if send_message_with_retry(chat_url, body, headers, max_retries):
        print(f"Welcome message sent for trade {trade_hash} ({account['name']})")
    else:
        print(f"Failed to send welcome message for trade {trade_hash} ({account['name']}) after {max_retries} retries.")
        return

    # Send second message if payment method is OXXO or bank-transfer
    if payment_method_slug in ["oxxo", "bank-transfer"]:
        try:
            # Load the JSON file
            json_filename = f"{payment_method_slug}.json"
            json_path = os.path.join(JSON_PATH, json_filename)

            with open(json_path, "r") as f:
                payment_data = json.load(f)

            print(f"Loaded payment data for {payment_method_slug}: {payment_data}")  # Debugging line

            # Access the correct dictionary level
            payment_method_data = payment_data.get(payment_method_slug, {})
            selected_id = str(payment_method_data.get("selected_id"))

            if not selected_id:
                print(f"Error: selected_id is missing in {json_filename}")
                return

            payment_accounts = payment_method_data.get("accounts", [])

            # Find the account with the matching ID
            selected_account = next((acc for acc in payment_accounts if str(acc["id"]) == selected_id), None)

            if not selected_account:
                print(f"No {payment_method_slug.upper()} account found for selected_id: {selected_id}")
                return

            # Dynamic message formatting based on payment method
            if payment_method_slug == "bank-transfer":
                second_message = f"Payment Details:\n\n" \
                                f"Bank: {selected_account['bank']}\n" \
                                f"Name: {selected_account['name']}\n" \
                                f"SPEI: {selected_account.get('SPEI', 'N/A')}\n\n"
            elif payment_method_slug == "oxxo":
                second_message = f"Payment Details:\n\n" \
                                f"Bank: {selected_account['bank']}\n" \
                                f"Name: {selected_account['name']}\n" \
                                f"Card Number: {selected_account.get('card_number', 'N/A')}\n\n"
            else:
                print(f"Unsupported payment method: {payment_method_slug}")
                return

            # Send the second message
            body = {"trade_hash": trade_hash, "message": second_message}
            if send_message_with_retry(chat_url, body, headers, max_retries):
                print(f"Payment details sent for trade {trade_hash} ({selected_account['name']})")
            else:
                print(f"Failed to send payment details for trade {trade_hash} ({selected_account['name']}) after {max_retries} retries.")

        except Exception as e:
            print(f"Error reading {payment_method_slug.upper()} data: {e}")