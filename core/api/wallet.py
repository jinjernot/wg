import logging
import json
import os
from datetime import datetime
from core.api.auth import fetch_token_with_retry
from config import PLATFORM_ACCOUNTS
from core.utils.http_client import get_http_client
from core.utils.response_cache import get_response_cache


logger = logging.getLogger(__name__)

API_LOG_PATH = os.path.join('data', 'logs', 'api_logs')
os.makedirs(API_LOG_PATH, exist_ok=True)

def _log_api_response(account_name, response):
    """Logs the raw API response status for debugging (no disk writes)."""
    try:
        logger.debug(f"[{account_name}] wallet-balances status={response.status_code}")
    except Exception as e:
        logger.error(f"Failed to log API response for {account_name}: {e}")

def get_wallet_balances():
    """Fetches wallet balances for all configured accounts."""
    # Check cache first (5 minute TTL)
    response_cache = get_response_cache()
    cached_balances = response_cache.get("wallet_balances")
    if cached_balances is not None:
        logger.debug("Returning cached wallet balances")
        return cached_balances
    
    all_balances = {}
    http_client = get_http_client()
    for account in PLATFORM_ACCOUNTS:
        token = fetch_token_with_retry(account)
        if not token:
            logger.error(f"Could not authenticate for {account['name']} to fetch wallet balances.")
            all_balances[account['name']] = {"error": "Authentication failed."}
            continue

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        
        try:
            url = "https://api.noones.com/noones/v1/user/wallet-balances"
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            response = http_client.post(url, headers=headers, timeout=15)

            if response:
                _log_api_response(account['name'], response)

            if response.status_code == 200:
                data = response.json().get("data", {})
                balances = {
                    currency['code']: currency['balance']
                    for currency in data.get('cryptoCurrencies', [])
                }
                if 'preferredFiatCurrency' in data and data['preferredFiatCurrency'].get('code'):
                    balances[data['preferredFiatCurrency']['code']] = data['preferredFiatCurrency']['balance']

                all_balances[account['name']] = balances
            else:
                error_message = f"API error (Status: {response.status_code}): {response.text}"
                logger.error(f"Failed to fetch balance for {account['name']}: {error_message}")
                all_balances[account['name']] = {"error": f"API Error {response.status_code}"}

        except Exception as e:
            logger.error(f"An exception occurred fetching balance for {account['name']}: {e}")
            all_balances[account['name']] = {"error": "Request failed"}
    
    # Cache the results for 5 minutes
    response_cache.set("wallet_balances", all_balances, ttl_seconds=300)
    
    return all_balances