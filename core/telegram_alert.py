import requests
import json
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

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

    # Different message formats based on the platform
    if platform == "Paxful":
        message = f"""
🚀 *New Paxful Trade Alert* 🚀

🔹 *Trade Status:* {trade.get('trade_status', 'N/A')}
🔹 *Trade Hash:* `{trade.get('trade_hash', 'N/A')}`
🔹 *Fiat Amount:* {trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency', 'N/A')}
🔹 *Payment Method:* {trade.get('payment_method_name', 'N/A')}
🔹 *Started At:* {trade.get('started_at', 'N/A')}

💸 *Seller:* {trade.get('owner_username', 'N/A')}
🐵 *Buyer:* {trade.get('responder_username', 'N/A')}

🔗 [View Trade Details](https://www.paxful.com/trade/{trade.get('trade_hash', '')})
        """
    elif platform == "Noones":
        message = f"""
🚀 *New Noones Trade Alert* 🚀

🔹 *Trade Status:* {trade.get('trade_status', 'N/A')}
🔹 *Trade Hash:* `{trade.get('trade_hash', 'N/A')}`
🔹 *Fiat Amount:* {trade.get('fiat_amount_requested', 'N/A')} {trade.get('fiat_currency_code', 'N/A')}
🔹 *Payment Method:* {trade.get('payment_method_name', 'N/A')}
🔹 *Started At:* {trade.get('started_at', 'N/A')}

💸 *Seller:* {trade.get('owner_username', 'N/A')}
🐵 *Buyer:* {trade.get('responder_username', 'N/A')}

🔗 [View Trade Details](https://noones.com/es/trade/{trade.get('trade_hash', '')})
        """
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
