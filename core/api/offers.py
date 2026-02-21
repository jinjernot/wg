import logging
import json
import os
from datetime import datetime
from core.api.auth import fetch_token_with_retry
from config import PLATFORM_ACCOUNTS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from core.messaging.alerts.telegram_alert import escape_markdown
from core.utils.http_client import get_http_client
from core.utils.response_cache import get_response_cache


logger = logging.getLogger(__name__)

MARKET_SEARCH_LOG_DIR = os.path.join('data', 'logs', 'market_search')
os.makedirs(MARKET_SEARCH_LOG_DIR, exist_ok=True)

def search_public_offers(crypto_code: str, fiat_code: str, payment_method_slug: str, trade_direction: str = "buy", payment_method_country_iso: str = None, country_code: str = None):
    """
    Fetches public offers from the Noones /offer/all endpoint.
    This REQUIRES authentication, so it uses the first account in config.
    """
    # Check cache first (2 minute TTL)
    response_cache = get_response_cache()
    cache_params = {"crypto": crypto_code, "fiat": fiat_code, "payment": payment_method_slug}
    cached_result = response_cache.get("public_offers", params=cache_params)
    if cached_result is not None:
        logger.debug(f"Returning cached public offers for {crypto_code}/{fiat_code}/{payment_method_slug}")
        return cached_result
    
    if not PLATFORM_ACCOUNTS:
        logger.error("Cannot search public offers, no accounts configured in PLATFORM_ACCOUNTS.")
        return None # <-- MODIFIED: Return None on failure

    auth_account = PLATFORM_ACCOUNTS[0]
    token = fetch_token_with_retry(auth_account)
    if not token:
        logger.error(f"Could not authenticate for {auth_account['name']} to search public offers.")
        return None # <-- MODIFIED: Return None on failure

    url = "https://api.noones.com/noones/v1/offer/all"
    
    payload = {
        "crypto_currency_code": crypto_code.upper(),
        "fiat_currency_code": fiat_code.upper(),
        "payment_method_slug": payment_method_slug,
        "offer_type": trade_direction,
        "sort_by": "best_price",
        "limit": 50
    }
    
    if payment_method_country_iso:
        payload["payment_method_country_iso"] = payment_method_country_iso.upper()
    
    if country_code:
        payload["country_code"] = country_code.upper()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    logger.info(f"Sending public offer search payload: {json.dumps(payload, indent=2)}")

    http_client = get_http_client()
    try:
        response = http_client.post(url, headers=headers, json=payload, timeout=15)
        
        # --- Save log regardless of API success (for debugging) ---
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_filename = f"{crypto_code}_{fiat_code}_{payment_method_slug}_{timestamp}.json"
            log_filepath = os.path.join(MARKET_SEARCH_LOG_DIR, log_filename)
            
            with open(log_filepath, 'w', encoding='utf-8') as f:
                try:
                    json.dump(response.json(), f, indent=4)
                    logger.info(f"Saved market search JSON response to {log_filepath}")
                except json.JSONDecodeError:
                    f.write(response.text)
                    logger.info(f"Saved market search TEXT response to {log_filepath}")
        except Exception as e:
            logger.error(f"Failed to save market search log: {e}")

        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                # --- START OF NEW FILTER LOGIC ---
                
                # 1. Get the 'data' payload, which can be a dict or a list
                payload_data = data.get("data", {})
                
                # 2. Extract the list of offers, handling both API response types
                all_offers = []
                if isinstance(payload_data, dict):
                    all_offers = payload_data.get("offers", [])
                elif isinstance(payload_data, list):
                    all_offers = payload_data
                
                if not all_offers:
                     logger.warning("API search returned success but no offers.")
                     return [] # Return an empty list

                logger.info(f"Received {len(all_offers)} offers from API. Filtering for fiat_currency_code='{fiat_code.upper()}'...")

                # 3. Manually filter the list for the correct fiat currency
                filtered_offers = [
                    offer for offer in all_offers 
                    if offer.get("fiat_currency_code") == fiat_code.upper()
                ]
                
                logger.info(f"Found {len(filtered_offers)} matching offers after filtering.")

                # 4. Always return the filtered list, regardless of payload structure
                return filtered_offers
                # --- END OF NEW FILTER LOGIC ---

            else:
                logger.error(f"Error in public offer search response: {response.text}")
                return None # <-- MODIFIED: Return None on failure
        else:
            logger.error(f"Failed to fetch public offers (Status: {response.status_code}): {response.text}")
            return None # <-- MODIFIED: Return None on failure
            
    except Exception as e:
        logger.error(f"An exception occurred fetching public offers: {e}")
        return None # <-- MODIFIED: Return None on failure
    finally:
        # Cache successful results only (2 minute TTL)
        # Check if either filtered_offers or payload_data was successfully populated
        result = None
        if 'filtered_offers' in locals():
            result = locals()['filtered_offers']
        elif 'payload_data' in locals() and isinstance(locals()['payload_data'], dict) and 'offers' in locals()['payload_data']:
            result = locals()['payload_data']

        if result is not None:
            response_cache.set("public_offers", result, ttl_seconds=120, params=cache_params)


def get_all_offers():
    """Fetches all of a user's own offers using the correct /offer/list endpoint."""
    all_offers_data = []
    http_client = get_http_client()
    for account in PLATFORM_ACCOUNTS:
        token = fetch_token_with_retry(account)
        if not token:
            logger.error(f"Could not authenticate for {account['name']} to fetch offers.")
            continue

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

        url = "https://api.noones.com/noones/v1/offer/list"
        
        try:
            response = http_client.post(url, headers=headers, timeout=15)
            
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

                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON for {account['name']} from /offer/list. Response: {response.text}")
            else:
                error_message = f"API error for {account['name']} from /offer/list (Status: {response.status_code})"
                try:
                    error_desc = response.json().get("error", {}).get("message", response.text)
                    error_message += f": {error_desc}"
                except json.JSONDecodeError:
                     error_message += f". Response body: {response.text}"
                logger.error(error_message)

        except Exception as e:
            logger.error(f"An exception occurred fetching offers for {account['name']}: {e}")
            
    return all_offers_data

def toggle_single_offer(account_name, offer_hash, turn_on):
    """Activates or deactivates a single offer."""
    target_account = next((acc for acc in PLATFORM_ACCOUNTS if acc["name"] == account_name), None)
    if not target_account:
        return {"success": False, "error": f"Account '{account_name}' not found."}

    token = fetch_token_with_retry(target_account)
    if not token:
        return {"success": False, "error": "Could not authenticate."}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    endpoint = "/offer/activate" if turn_on else "/offer/deactivate"
    url = f"https://api.noones.com/noones/v1{endpoint}"
    data = {"offer_hash": offer_hash}
    
    http_client = get_http_client()
    try:
        response = http_client.post(url, headers=headers, data=data, timeout=15)
        
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
    http_client = get_http_client()
    for account in PLATFORM_ACCOUNTS:
        token = fetch_token_with_retry(account)
        if not token:
            results.append({"account": account["name"], "success": False, "error": "Could not authenticate."})
            continue

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        endpoint = "/offer/turn-on" if turn_on else "/offer/turn-off"
        url = f"https://api.noones.com/noones/v1{endpoint}"

        try:
            response = http_client.post(url, headers=headers)
            
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
    http_client = get_http_client()
    try:
        response = http_client.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Scheduled task alert sent successfully.")
        else:
            logger.error(f"Failed to send scheduled task alert: {response.text}")
    except Exception as e:
        logger.error(f"Exception sending Telegram alert: {e}")