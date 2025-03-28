import requests
import json
import re
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PAXFUL_ALERT_MESSAGE, NOONES_ALERT_MESSAGE, NEW_CHAT_ALERT_MESSAGE

def extract_placeholders(message_template):
    """
    Extract placeholders from the message template.
    """
    return re.findall(r"{(.*?)}", message_template)

def send_telegram_alert(trade, platform):
    """
    Send a Telegram alert for trade updates.
    """
    if isinstance(trade, str):
        try:
            trade = json.loads(trade)  # Convert string to dictionary if it's a string
        except json.JSONDecodeError:
            print("Error: Trade data is not a valid JSON string.")
            return
    
    if not isinstance(trade, dict):
        print("Error: Trade data is not a dictionary.")
        return

    # Select message template based on platform
    if platform == "Paxful":
        message_template = PAXFUL_ALERT_MESSAGE
    elif platform == "Noones":
        message_template = NOONES_ALERT_MESSAGE
    else:
        print("Error: Unsupported platform.")
        return
    
    placeholders = extract_placeholders(message_template)
    
    trade_data = {key: trade.get(key, "N/A") for key in placeholders}

    try:
        message = message_template.format(**trade_data)
    except KeyError as e:
        print(f"Error: Missing key {e} in trade data.")
        return

    # Send Telegram message
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True 
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Telegram alert sent successfully.")
    else:
        print(f"Failed to send Telegram alert: {response.status_code} - {response.text}")

def send_chat_message_alert(chat_message, trade_hash, platform, author):
    """
    Send a Telegram alert for new chat messages.
    """
    if not isinstance(chat_message, str) or not isinstance(author, str):
        print("Error: Invalid chat message or author data.")
        return
    
    # Select message template for new chat message
    message_template = NEW_CHAT_ALERT_MESSAGE  # Define the template for new chat messages

    placeholders = extract_placeholders(message_template)
    
    chat_data = {
        "chat_message": chat_message,
        "author": author, 
        "trade_hash": trade_hash
    }

    try:
        message = message_template.format(**chat_data)
    except KeyError as e:
        print(f"Error: Missing key {e} in chat message data.")
        return

    # Send Telegram message for new chat alert
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True 
    }
    
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("New chat message alert sent successfully.")
    else:
        print(f"Failed to send chat alert: {response.status_code} - {response.text}")
