import requests
import logging
from core.api_client.auth import fetch_token_with_retry
from config import ACCOUNTS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)

def set_offer_status(turn_on):
    """
    Turns all offers on or off for all configured accounts.
    """
    results = []
    for account in ACCOUNTS:
        token = fetch_token_with_retry(account)
        if not token:
            results.append({"account": account["name"], "success": False, "error": "Could not authenticate."})
            continue

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        platform_url = "https://api.paxful.com/paxful/v1" if "_Paxful" in account["name"] else "https://api.noones.com/noones/v1"
        endpoint = "/offer/turn-on" if turn_on else "/offer/turn-off"
        url = f"{platform_url}{endpoint}"

        try:
            response = requests.post(url, headers=headers)
            if response.status_code == 200 and response.json().get("status") == "success":
                results.append({"account": account["name"], "success": True})
            else:
                error_message = response.json().get("error_description", "Unknown error")
                results.append({"account": account["name"], "success": False, "error": error_message})
        except Exception as e:
            results.append({"account": account["name"], "success": False, "error": str(e)})
    
    return results

def send_scheduled_task_alert(message):
    """
    Sends a simple text alert to Telegram.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Scheduled task alert sent successfully.")
        else:
            logger.error(f"Failed to send scheduled task alert: {response.text}")
    except Exception as e:
        logger.error(f"Exception sending Telegram alert: {e}")