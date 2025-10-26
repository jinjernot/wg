import requests
import logging
from core.api.auth import fetch_token_with_retry
from config import ACCOUNTS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from core.messaging.alerts.telegram_alert import escape_markdown

logger = logging.getLogger(__name__)

def get_all_offers():
    """Fetches all of a user's own offers using the correct /offer/list endpoint."""
    all_offers_data = []
    for account in ACCOUNTS:
        # --- ADDED TEMPORARY CHECK ---
        if "_Paxful" in account.get("name", ""):
            logger.warning(f"Temporarily skipping offer fetching for Paxful account: {account.get('name')}")
            continue
        # --- END OF CHECK ---

        token = fetch_token_with_retry(account)
        if not token:
            logger.error(f"Could not authenticate for {account['name']} to fetch offers.")
            continue

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        platform_url = "https://api.paxful.com/paxful/v1" if "_Paxful" in account["name"] else "https://api.noones.com/noones/v1"
        url = f"{platform_url}/offer/list"
        
        try:
            response = requests.post(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    offers = response_data.get("data", {}).get("offers", [])
                    
                    if not offers and "data" in response_data and isinstance(response_data["data"], list):
                         offers = response_data["data"]

                    active_offers = [o for o in offers if o.get("active")]

                    for offer in active_offers:
                        offer['account_name'] = account["name"]
                        offer['enabled'] = offer['active']
                    
                    all_offers_data.extend(active_offers)
                    logger.info(f"Successfully fetched {len(active_offers)} active offers for {account['name']}.")

                except requests.exceptions.JSONDecodeError:
                    logger.error(f"Failed to decode JSON for {account['name']} from /offer/list. Response: {response.text}")
            else:
                error_message = f"API error for {account['name']} from /offer/list (Status: {response.status_code})"
                try:
                    error_desc = response.json().get("error", {}).get("message", response.text)
                    error_message += f": {error_desc}"
                except requests.exceptions.JSONDecodeError:
                     error_message += f". Response body: {response.text}"
                logger.error(error_message)

        except Exception as e:
            logger.error(f"An exception occurred fetching offers for {account['name']}: {e}")
            
    return all_offers_data

def toggle_single_offer(account_name, offer_hash, turn_on):
    """Activates or deactivates a single offer."""
    # --- ADDED TEMPORARY CHECK ---
    if "_Paxful" in account_name:
         logger.warning(f"Temporarily skipping single offer toggle for Paxful account: {account_name}")
         return {"success": False, "error": "Paxful actions are temporarily disabled."}
    # --- END OF CHECK ---

    target_account = next((acc for acc in ACCOUNTS if acc["name"] == account_name), None)
    if not target_account:
        return {"success": False, "error": f"Account '{account_name}' not found."}

    token = fetch_token_with_retry(target_account)
    if not token:
        return {"success": False, "error": "Could not authenticate."}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    platform_url = "https://api.paxful.com/paxful/v1" if "_Paxful" in target_account["name"] else "https://api.noones.com/noones/v1"
    
    # --- CORRECTED ENDPOINT AND DATA ---
    endpoint = "/offer/activate" if turn_on else "/offer/deactivate"
    url = f"{platform_url}{endpoint}"
    data = {"offer_hash": offer_hash} # Pass hash in the body
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=15)
        
        if response.status_code == 200 and response.json().get("status") == "success":
            return {"success": True}
        else:
            error_message = response.json().get("error_description", "Unknown API error")
            return {"success": False, "error": error_message}
    except Exception as e:
        return {"success": False, "error": str(e)}

def set_offer_status(turn_on):
    """
    Turns all offers on or off for all configured accounts using the correct endpoints.
    """
    results = []
    for account in ACCOUNTS:
        # --- ADDED TEMPORARY CHECK ---
        if "_Paxful" in account.get("name", ""):
            logger.warning(f"Temporarily skipping offer status change for Paxful account: {account.get('name')}")
            continue
        # --- END OF CHECK ---

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
        "text": escape_markdown(message),
        "parse_mode": "MarkdownV2"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Scheduled task alert sent successfully.")
        else:
            logger.error(f"Failed to send scheduled task alert: {response.text}")
    except Exception as e:
        logger.error(f"Exception sending Telegram alert: {e}")