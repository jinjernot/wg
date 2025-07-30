import requests
import json
import re
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from config_messages.telegram_messages import PAXFUL_ALERT_MESSAGE, NOONES_ALERT_MESSAGE, NEW_CHAT_ALERT_MESSAGE, NEW_ATTACHMENT_ALERT_MESSAGE



def extract_placeholders(message_template):
    """Extracts placeholders from the message template."""
    return re.findall(r"{(.*?)}", message_template)

def send_telegram_alert(trade, platform):
    """Sends a Telegram alert for trade updates and logs it."""
    if isinstance(trade, str):
        try:
            trade = json.loads(trade)
        except json.JSONDecodeError:
            print("Error: Trade data is not a valid JSON string.")
            return
    
    if not isinstance(trade, dict):
        print("Error: Trade data is not a dictionary.")
        return

    message_template = PAXFUL_ALERT_MESSAGE if platform == "Paxful" else NOONES_ALERT_MESSAGE
    placeholders = extract_placeholders(message_template)
    trade_data = {key: trade.get(key, "N/A") for key in placeholders}

    try:
        message = message_template.format(**trade_data)
    except KeyError as e:
        print(f"Error: Missing key {e} in trade data.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Telegram alert sent successfully.")
    else:
        print(f"Failed to send Telegram alert: {response.status_code} - {response.text}")

def send_chat_message_alert(chat_message, trade_hash, platform, author):
    """Sends a Telegram alert for new chat messages and logs it."""
    if not isinstance(chat_message, str) or not isinstance(author, str):
        print("Error: Invalid chat message or author data.")
        return
    
    message_template = NEW_CHAT_ALERT_MESSAGE
    chat_data = { "chat_message": chat_message, "author": author, "trade_hash": trade_hash }

    try:
        message = message_template.format(**chat_data)
    except KeyError as e:
        print(f"Error: Missing key {e} in chat message data.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("New chat message alert sent successfully.")
    else:
        print(f"Failed to send chat alert: {response.status_code} - {response.text}")

def send_attachment_alert(trade_hash, author):
    """Sends a Telegram alert for attachments and logs it."""
    message = NEW_ATTACHMENT_ALERT_MESSAGE.format(trade_hash=trade_hash, author=author)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = { "chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Attachment alert sent successfully.")
    else:
        print(f"Failed to send attachment alert: {response.status_code} - {response.text}")