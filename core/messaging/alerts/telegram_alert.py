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
    AMOUNT_VALIDATION_NOT_FOUND_ALERT,
    AMOUNT_VALIDATION_MATCH_ALERT,
    AMOUNT_VALIDATION_MISMATCH_ALERT,
    EMAIL_VALIDATION_SUCCESS_ALERT,
    EMAIL_VALIDATION_FAILURE_ALERT,
    NAME_VALIDATION_SUCCESS_ALERT,
    NAME_VALIDATION_FAILURE_ALERT
)

logger = logging.getLogger(__name__)

def escape_markdown(text):
    """Escapes special characters for Telegram's MarkdownV2 parse mode."""
    if not isinstance(text, str):
        text = str(text)
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def extract_placeholders(message_template):
    """Extracts placeholders from the message template."""
    return re.findall(r"{(.*?)}", message_template)

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
    placeholders = extract_placeholders(message_template)
    trade_data = {key: escape_markdown(trade.get(key, "N/A")) for key in placeholders}

    try:
        message = message_template.format(**trade_data)
    except KeyError as e:
        logger.error(f"Error: Missing key {e} in trade data.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "MarkdownV2", "disable_web_page_preview": True }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("Telegram alert sent successfully.")
    else:
        logger.error(f"Failed to send Telegram alert: {response.status_code} - {response.text}")

def send_chat_message_alert(chat_message, trade_hash, owner_username, author):
    if not isinstance(chat_message, str) or not isinstance(author, str):
        logger.error("Error: Invalid chat message or author data.")
        return
        
    message_template = NEW_CHAT_ALERT_MESSAGE
    chat_data = { 
        "chat_message": escape_markdown(chat_message), 
        "author": escape_markdown(author), 
        "trade_hash": escape_markdown(trade_hash),
        "owner_username": escape_markdown(owner_username)
    }
    
    try:
        message = message_template.format(**chat_data)
    except KeyError as e:
        logger.error(f"Error: Missing key {e} in chat message data.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "MarkdownV2", "disable_web_page_preview": True }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("New chat message alert sent successfully.")
    else:
        logger.error(f"Failed to send chat alert: {response.status_code} - {response.text}")

def send_attachment_alert(trade_hash, owner_username, author, image_path):
    if not os.path.exists(image_path):
        logger.error(f"Error: Image path does not exist: {image_path}")
        return

    caption = NEW_ATTACHMENT_ALERT_MESSAGE.format(
        trade_hash=escape_markdown(trade_hash), 
        owner_username=escape_markdown(owner_username),
        author=escape_markdown(author)
    )
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "MarkdownV2"
    }

    try:
        with open(image_path, 'rb') as photo_file:
            files = {'photo': photo_file}
            response = requests.post(url, data=data, files=files)
        
        if response.status_code == 200:
            logger.info("Attachment alert with image sent successfully.")
        else:
            logger.error(f"Failed to send attachment alert with image: {response.status_code} - {response.text}")
    except IOError as e:
        logger.error(f"Error opening image file {image_path}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending attachment alert: {e}")
        
def send_amount_validation_alert(trade_hash, owner_username, expected_amount, found_amount, currency):
    if found_amount is None:
        message = AMOUNT_VALIDATION_NOT_FOUND_ALERT.format(
            trade_hash=escape_markdown(trade_hash),
            owner_username=escape_markdown(owner_username)
        )
    elif float(expected_amount) == float(found_amount):
        message = AMOUNT_VALIDATION_MATCH_ALERT.format(
            trade_hash=escape_markdown(trade_hash),
            owner_username=escape_markdown(owner_username),
            found_amount=escape_markdown(f"{found_amount:.2f}"),
            currency=escape_markdown(currency)
        )
    else:
        message = AMOUNT_VALIDATION_MISMATCH_ALERT.format(
            trade_hash=escape_markdown(trade_hash),
            owner_username=escape_markdown(owner_username),
            expected_amount=escape_markdown(f"{float(expected_amount):.2f}"),
            found_amount=escape_markdown(f"{float(found_amount):.2f}"),
            currency=escape_markdown(currency)
        )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("Amount validation alert sent successfully.")
    else:
        logger.error(f"Failed to send amount validation alert: {response.status_code} - {response.text}")

def send_email_validation_alert(trade_hash, success, account_name):
    """Sends a Telegram alert about the email validation result."""
    if success:
        message = EMAIL_VALIDATION_SUCCESS_ALERT.format(
            trade_hash=escape_markdown(trade_hash), 
            account_name=escape_markdown(account_name)
        )
    else:
        message = EMAIL_VALIDATION_FAILURE_ALERT.format(
            trade_hash=escape_markdown(trade_hash), 
            account_name=escape_markdown(account_name)
        )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("Email validation alert sent successfully.")
    else:
        logger.error(f"Failed to send email validation alert: {response.status_code} - {response.text}")

def send_name_validation_alert(trade_hash, success, account_name):
    """Sends a Telegram alert about the OCR name validation result."""
    if success:
        message = NAME_VALIDATION_SUCCESS_ALERT.format(
            trade_hash=escape_markdown(trade_hash),
            account_name=escape_markdown(account_name)
        )
    else:
        message = NAME_VALIDATION_FAILURE_ALERT.format(
            trade_hash=escape_markdown(trade_hash),
            account_name=escape_markdown(account_name)
        )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("Name validation alert sent successfully.")
    else:
        logger.error(f"Failed to send name validation alert: {response.status_code} - {response.text}")
