import requests
import json
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, PAXFUL_ALERT_MESSAGE, NOONES_ALERT_MESSAGE

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
        message = PAXFUL_ALERT_MESSAGE.format(**{k: trade.get(k, "N/A") for k in PAXFUL_ALERT_MESSAGE.split("{") if "}" in k})
    elif platform == "Noones":
        message = NOONES_ALERT_MESSAGE.format(**{k: trade.get(k, "N/A") for k in NOONES_ALERT_MESSAGE.split("{") if "}" in k})
    else:
        print("Error: Unsupported platform.")
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
