import requests
import json
import re
import os
import logging
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from config_messages.telegram_messages import (
    PAXFUL_ALERT_MESSAGE,
    NOONES_ALERT_MESSAGE,
    NEW_CHAT_ALERT_MESSAGE,
    NEW_ATTACHMENT_ALERT_MESSAGE,
    NEW_ATTACHMENT_WITH_BANK_ALERT_MESSAGE,
    AMOUNT_VALIDATION_NOT_FOUND_ALERT,
    AMOUNT_VALIDATION_MATCH_ALERT,
    AMOUNT_VALIDATION_MISMATCH_ALERT,
    EMAIL_VALIDATION_SUCCESS_ALERT,
    EMAIL_VALIDATION_FAILURE_ALERT,
    NAME_VALIDATION_SUCCESS_ALERT,
    NAME_VALIDATION_FAILURE_ALERT,
    LOW_BALANCE_ALERT_MESSAGE,
    DUPLICATE_RECEIPT_ALERT_MESSAGE
)

logger = logging.getLogger(__name__)

def escape_markdown(text):
    """Escapes special characters for Telegram's MarkdownV2 parse mode."""
    if not isinstance(text, str):
        text = str(text)
    # Characters to escape for Telegram MarkdownV2.
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    # Use re.sub with a function to handle already escaped characters
    def replace(match):
        char = match.group(1)
        # Check if the character is already escaped (preceded by \)
        if match.start() > 0 and text[match.start()-1] == '\\':
            return char # Already escaped, return as is
        else:
            return '\\' + char # Escape it
    # Use negative lookbehind to avoid double escaping
    return re.sub(f'(?<!\\\\)([{re.escape(escape_chars)}])', r'\\\1', text)


def send_telegram_alert(trade, platform):
    if isinstance(trade, str):
        try:
            trade = json.loads(trade)
        except json.JSONDecodeError:
            logger.error("Error: Trade data is not a valid JSON string.")
            return
    if not isinstance(trade, dict):
        logger.error("Error: Trade data is not a dictionary.")
        return

    message_template = PAXFUL_ALERT_MESSAGE if platform == "Paxful" else NOONES_ALERT_MESSAGE
    # Escape each value before formatting
    formatted_data = {key: escape_markdown(trade.get(key, "N/A")) for key in extract_placeholders(message_template)}
    message = message_template.format(**formatted_data)

    # --- FIX: Escape any remaining unescaped special characters in the final template string ---
    # Escapes ., (, ), -, | - adjust the characters inside [] if more are needed
    message = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', message)
    # --- END FIX ---

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "MarkdownV2", "disable_web_page_preview": True }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Telegram alert sent successfully.")
        else:
            logger.error(f"Failed to send Telegram alert: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram request: {e}")

def extract_placeholders(message_template):
    """Extracts placeholders from the message template."""
    return re.findall(r"{(.*?)}", message_template)

def send_chat_message_alert(chat_message, trade_hash, owner_username, author):
    """Sends a Telegram alert for a new chat message."""
    chat_data = {
        "chat_message": escape_markdown(chat_message),
        "author": escape_markdown(author),
        "trade_hash": escape_markdown(trade_hash),
        "owner_username": escape_markdown(owner_username)
    }
    message = NEW_CHAT_ALERT_MESSAGE.format(**chat_data)

    # --- FIX: Escape any remaining unescaped special characters ---
    message = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', message)
    # --- END FIX ---

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "MarkdownV2", "disable_web_page_preview": True }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("New chat message alert sent successfully.")
        else:
            logger.error(f"Failed to send chat alert: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram request: {e}")

def send_attachment_alert(trade_hash, owner_username, author, image_path, bank_name=None):
    if not os.path.exists(image_path):
        logger.error(f"Error: Image path does not exist: {image_path}")
        return

    caption_text = ""
    if bank_name:
        template = NEW_ATTACHMENT_WITH_BANK_ALERT_MESSAGE
        caption_text = template.format(
            bank_name=escape_markdown(bank_name),
            trade_hash=escape_markdown(trade_hash),
            owner_username=escape_markdown(owner_username),
            author=escape_markdown(author)
        )
    else:
        template = NEW_ATTACHMENT_ALERT_MESSAGE
        caption_text = template.format(
            trade_hash=escape_markdown(trade_hash),
            owner_username=escape_markdown(owner_username),
            author=escape_markdown(author)
        )

    # --- FIX: Escape any remaining unescaped special characters ---
    caption_text = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', caption_text)
    # --- END FIX ---

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption_text,
        "parse_mode": "MarkdownV2"
    }

    try:
        with open(image_path, 'rb') as photo_file:
            files = {'photo': photo_file}
            response = requests.post(url, data=data, files=files, timeout=20) # Increased timeout for file upload

        if response.status_code == 200:
            logger.info("Attachment alert with image sent successfully.")
        else:
            logger.error(f"Failed to send attachment alert with image: {response.status_code} - {response.text}")
    except IOError as e:
        logger.error(f"Error opening image file {image_path}: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram request with image: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending attachment alert: {e}")


def send_amount_validation_alert(trade_hash, owner_username, expected_amount, found_amount, currency):
    message = ""
    try:
        # Ensure expected_amount is float for comparison and formatting
        expected_amount_float = float(expected_amount)
    except (ValueError, TypeError):
        logger.error(f"Invalid expected amount type for trade {trade_hash}: {expected_amount}")
        expected_amount_float = 0.0 # Default or handle error appropriately

    if found_amount is None:
        message = AMOUNT_VALIDATION_NOT_FOUND_ALERT.format(
            trade_hash=escape_markdown(trade_hash),
            owner_username=escape_markdown(owner_username)
        )
    else:
        try:
             # Ensure found_amount is float for comparison and formatting
            found_amount_float = float(found_amount)
            if expected_amount_float == found_amount_float:
                message = AMOUNT_VALIDATION_MATCH_ALERT.format(
                    trade_hash=escape_markdown(trade_hash),
                    owner_username=escape_markdown(owner_username),
                    found_amount=escape_markdown(f"{found_amount_float:.2f}"), # Use float for formatting
                    currency=escape_markdown(currency)
                )
            else:
                message = AMOUNT_VALIDATION_MISMATCH_ALERT.format(
                    trade_hash=escape_markdown(trade_hash),
                    owner_username=escape_markdown(owner_username),
                    expected_amount=escape_markdown(f"{expected_amount_float:.2f}"), # Use float
                    found_amount=escape_markdown(f"{found_amount_float:.2f}"), # Use float
                    currency=escape_markdown(currency)
                )
        except (ValueError, TypeError):
            logger.error(f"Invalid found amount type for trade {trade_hash}: {found_amount}")
            # Optionally send a specific error message or use the not found template
            message = AMOUNT_VALIDATION_NOT_FOUND_ALERT.format( # Fallback message
                trade_hash=escape_markdown(trade_hash),
                owner_username=escape_markdown(owner_username)
            )

    if not message: # If message is still empty due to an error path not setting it
         logger.error(f"Amount validation message could not be formatted for trade {trade_hash}")
         return # Avoid sending empty message

    # --- FIX: Escape any remaining unescaped special characters ---
    message = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', message)
    # --- END FIX ---

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Amount validation alert sent successfully.")
        else:
            logger.error(f"Failed to send amount validation alert: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram request: {e}")

def send_email_validation_alert(trade_hash, success, account_name):
    """Sends a Telegram alert about the email validation result."""
    if success:
        message = EMAIL_VALIDATION_SUCCESS_ALERT.format(trade_hash=escape_markdown(trade_hash), account_name=escape_markdown(account_name))
    else:
        message = EMAIL_VALIDATION_FAILURE_ALERT.format(trade_hash=escape_markdown(trade_hash), account_name=escape_markdown(account_name))

    # --- FIX: Escape any remaining unescaped special characters ---
    message = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', message)
    # --- END FIX ---

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Email validation alert sent successfully.")
        else:
            logger.error(f"Failed to send email validation alert: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram request: {e}")


def send_name_validation_alert(trade_hash, success, account_name):
    """Sends a Telegram alert about the OCR name validation result."""
    if success:
        message = NAME_VALIDATION_SUCCESS_ALERT.format(trade_hash=escape_markdown(trade_hash), account_name=escape_markdown(account_name))
    else:
        message = NAME_VALIDATION_FAILURE_ALERT.format(trade_hash=escape_markdown(trade_hash), account_name=escape_markdown(account_name))

    # --- FIX: Escape any remaining unescaped special characters ---
    message = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', message)
    # --- END FIX ---

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Name validation alert sent successfully.")
        else:
            logger.error(f"Failed to send name validation alert: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram request: {e}")

def send_low_balance_alert(account_name, total_balance_usd, threshold, balance_details_raw):
    """Builds and sends a Telegram alert for low wallet balance using a template."""
    balance_details_formatted = []
    for amount, currency, usd_value in balance_details_raw:
        # Format amount and usd_value safely
        try:
            amount_str = f"{float(amount):,.8f}".rstrip('0').rstrip('.') # Handle potential float conversion issues and format nicely
        except ValueError:
             amount_str = str(amount) # Fallback to string if conversion fails
        usd_str = f"{usd_value:,.2f}"
        # Escape currency code just in case it contains special characters unexpectedly
        currency_escaped = escape_markdown(currency)
        line = f"- `{amount_str} {currency_escaped}` (approx. ${usd_str})"
        balance_details_formatted.append(line)

    details_str = "\n".join(balance_details_formatted) if balance_details_formatted else "No balance details available."

    message = LOW_BALANCE_ALERT_MESSAGE.format(
        account_name=escape_markdown(account_name),
        total_balance_usd=escape_markdown(f"{total_balance_usd:,.2f}"),
        threshold=escape_markdown(f"{threshold:,.2f}"),
        balance_details=details_str # This is already formatted with markdown and escaped parts, so we don't escape the whole block.
    )

    # --- FIX: Escape any remaining unescaped special characters ---
    # This should be safe for the code blocks (`...`) as dots inside them are not parsed by Telegram.
    message = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', message)
    # --- END FIX ---

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "MarkdownV2"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Low balance alert for {account_name} sent successfully.")
        else:
            logger.error(f"Failed to send low balance alert for {account_name}: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram request: {e}")

def send_duplicate_receipt_alert(trade_hash, owner_username, image_path, previous_trade_info):
    """Sends a Telegram alert for a duplicate receipt."""
    # Provide default values if keys might be missing
    previous_trade_hash = previous_trade_info.get('trade_hash', 'N/A')
    previous_owner = previous_trade_info.get('owner_username', 'N/A')

    caption_text = DUPLICATE_RECEIPT_ALERT_MESSAGE.format(
        trade_hash=escape_markdown(trade_hash),
        owner_username=escape_markdown(owner_username),
        previous_trade_hash=escape_markdown(previous_trade_hash),
        previous_owner=escape_markdown(previous_owner)
    )

    # --- FIX: Escape any remaining unescaped special characters including ., (, ) in the final template string ---
    caption_text = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', caption_text)
    # --- END FIX ---

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption_text, "parse_mode": "MarkdownV2"}

    try:
        # Check if image path exists before opening
        if not os.path.exists(image_path):
             logger.error(f"Image file not found for duplicate receipt alert: {image_path}")
             # Optionally send a text message alert instead
             text_message = f"🚨 DUPLICATE RECEIPT DETECTED 🚨\nTrade: {trade_hash}\nOwner: {owner_username}\nDetected duplicate of receipt from trade {previous_trade_hash} (Owner: {previous_owner}).\n*Image file was not found at path: {image_path}*"
             text_payload = {"chat_id": TELEGRAM_CHAT_ID, "text": escape_markdown(text_message), "parse_mode": "MarkdownV2"}
             requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json=text_payload, timeout=10)
             return

        with open(image_path, 'rb') as photo_file:
            files = {'photo': photo_file}
            response = requests.post(url, data=data, files=files, timeout=20) # Increased timeout

        if response.status_code == 200:
            logger.info("Duplicate receipt alert with image sent successfully.")
        else:
            logger.error(f"Failed to send duplicate receipt alert with image: {response.status_code} - {response.text}")
    except IOError as e:
        logger.error(f"Error opening image file {image_path}: {e}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram request with image: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending duplicate receipt alert: {e}")