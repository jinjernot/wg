import requests
import json
import re
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PAXFUL_ALERT_MESSAGE, NOONES_ALERT_MESSAGE

def extract_placeholders(message_template):
    """ Extracts placeholders from the message template correctly. """
    return re.findall(r"{(.*?)}", message_template)

def send_telegram_alert(trade, platform):
    if isinstance(trade, str):
        try:
            trade = json.loads(trade)
        except json.JSONDecodeError:
            print("Error: Trade data is not a valid JSON string.")
            return
    
    if not isinstance(trade, dict):
        print("Error: Trade data is not a dictionary.")
        return

    # Choose the correct message template
    if platform == "Paxful":
        message_template = PAXFUL_ALERT_MESSAGE
    elif platform == "Noones":
        message_template = NOONES_ALERT_MESSAGE
    else:
        print("Error: Unsupported platform.")
        return
    
    # Extract placeholders correctly
    placeholders = extract_placeholders(message_template)
    
    # Fill in missing placeholders with "N/A"
    trade_data = {key: trade.get(key, "N/A") for key in placeholders}

    # Format the message safely
    try:
        message = message_template.format(**trade_data)
    except KeyError as e:
        print(f"Error: Missing key {e} in trade data.")
        return

    # Send the Telegram message
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
