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
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

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
    # Format first, then escape the entire result.
    unformatted_data = {key: trade.get(key, "N/A") for key in extract_placeholders(message_template)}
    message = message_template.format(**unformatted_data)
    escaped_message = escape_markdown(message)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": escaped_message, "parse_mode": "MarkdownV2", "disable_web_page_preview": True }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("Telegram alert sent successfully.")
    else:
        logger.error(f"Failed to send Telegram alert: {response.status_code} - {response.text}")

def extract_placeholders(message_template):
    """Extracts placeholders from the message template."""
    return re.findall(r"{(.*?)}", message_template)

def send_chat_message_alert(chat_message, trade_hash, owner_username, author):
    """Sends a Telegram alert for a new chat message."""
    chat_data = {
        "chat_message": chat_message,
        "author": author,
        "trade_hash": trade_hash,
        "owner_username": owner_username
    }
    # Format first, then escape the entire result.
    message = NEW_CHAT_ALERT_MESSAGE.format(**chat_data)
    escaped_message = escape_markdown(message)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": escaped_message, "parse_mode": "MarkdownV2", "disable_web_page_preview": True }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("New chat message alert sent successfully.")
    else:
        logger.error(f"Failed to send chat alert: {response.status_code} - {response.text}")

def send_attachment_alert(trade_hash, owner_username, author, image_path, bank_name=None):
    if not os.path.exists(image_path):
        logger.error(f"Error: Image path does not exist: {image_path}")
        return

    if bank_name:
        template = NEW_ATTACHMENT_WITH_BANK_ALERT_MESSAGE
        caption_text = template.format(
            bank_name=bank_name,
            trade_hash=trade_hash,
            owner_username=owner_username,
            author=author
        )
    else:
        template = NEW_ATTACHMENT_ALERT_MESSAGE
        caption_text = template.format(
            trade_hash=trade_hash,
            owner_username=owner_username,
            author=author
        )

    escaped_caption = escape_markdown(caption_text)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": escaped_caption,
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
            trade_hash=trade_hash,
            owner_username=owner_username
        )
    elif float(expected_amount) == float(found_amount):
        message = AMOUNT_VALIDATION_MATCH_ALERT.format(
            trade_hash=trade_hash,
            owner_username=owner_username,
            found_amount=f"{found_amount:.2f}",
            currency=currency
        )
    else:
        message = AMOUNT_VALIDATION_MISMATCH_ALERT.format(
            trade_hash=trade_hash,
            owner_username=owner_username,
            expected_amount=f"{float(expected_amount):.2f}",
            found_amount=f"{float(found_amount):.2f}",
            currency=currency
        )

    escaped_message = escape_markdown(message)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": escaped_message, "parse_mode": "MarkdownV2"}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("Amount validation alert sent successfully.")
    else:
        logger.error(f"Failed to send amount validation alert: {response.status_code} - {response.text}")

def send_email_validation_alert(trade_hash, success, account_name):
    """Sends a Telegram alert about the email validation result."""
    if success:
        message = EMAIL_VALIDATION_SUCCESS_ALERT.format(trade_hash=trade_hash, account_name=account_name)
    else:
        message = EMAIL_VALIDATION_FAILURE_ALERT.format(trade_hash=trade_hash, account_name=account_name)

    escaped_message = escape_markdown(message)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": escaped_message, "parse_mode": "MarkdownV2"}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("Email validation alert sent successfully.")
    else:
        logger.error(f"Failed to send email validation alert: {response.status_code} - {response.text}")

def send_name_validation_alert(trade_hash, success, account_name):
    """Sends a Telegram alert about the OCR name validation result."""
    if success:
        message = NAME_VALIDATION_SUCCESS_ALERT.format(trade_hash=trade_hash, account_name=account_name)
    else:
        message = NAME_VALIDATION_FAILURE_ALERT.format(trade_hash=trade_hash, account_name=account_name)

    escaped_message = escape_markdown(message)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": escaped_message, "parse_mode": "MarkdownV2"}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info("Name validation alert sent successfully.")
    else:
        logger.error(f"Failed to send name validation alert: {response.status_code} - {response.text}")

def send_low_balance_alert(account_name, total_balance_usd, threshold, balance_details_raw):
    """Builds and sends a Telegram alert for low wallet balance using a template."""
    balance_details_formatted = []
    for amount, currency, usd_value in balance_details_raw:
        usd_str = f"{usd_value:,.2f}"
        line = f"- `{amount} {currency}` (approx. `${usd_str}`)"
        balance_details_formatted.append(line)
    
    details_str = "\n".join(balance_details_formatted)
    
    message = LOW_BALANCE_ALERT_MESSAGE.format(
        account_name=account_name,
        total_balance_usd=f"{total_balance_usd:,.2f}",
        threshold=f"{threshold:,.2f}",
        balance_details=details_str
    )
    
    escaped_message = escape_markdown(message)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": escaped_message, "parse_mode": "MarkdownV2"}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logger.info(f"Low balance alert for {account_name} sent successfully.")
    else:
        logger.error(f"Failed to send low balance alert for {account_name}: {response.status_code} - {response.text}")

def send_duplicate_receipt_alert(trade_hash, owner_username, image_path, previous_trade_info):
    """Sends a Telegram alert for a duplicate receipt."""
    previous_trade_hash = previous_trade_info['trade_hash']
    previous_owner = previous_trade_info['owner_username']
    
    caption_text = DUPLICATE_RECEIPT_ALERT_MESSAGE.format(
        trade_hash=trade_hash,
        owner_username=owner_username,
        previous_trade_hash=previous_trade_hash,
        previous_owner=previous_owner
    )
    
    escaped_caption = escape_markdown(caption_text)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {"chat_id": TELEGRAM_CHAT_ID, "caption": escaped_caption, "parse_mode": "MarkdownV2"}

    try:
        with open(image_path, 'rb') as photo_file:
            files = {'photo': photo_file}
            response = requests.post(url, data=data, files=files)
        
        if response.status_code == 200:
            logger.info("Duplicate receipt alert with image sent successfully.")
        else:
            logger.error(f"Failed to send duplicate receipt alert with image: {response.status_code} - {response.text}")
    except IOError as e:
        logger.error(f"Error opening image file {image_path}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while sending duplicate receipt alert: {e}")