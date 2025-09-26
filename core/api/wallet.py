# core/api/wallet.py
import requests
import logging
import json
import os
from datetime import datetime
from core.api.auth import fetch_token_with_retry
from config import ACCOUNTS

logger = logging.getLogger(__name__)

API_LOG_PATH = os.path.join('data', 'logs', 'api_logs')
os.makedirs(API_LOG_PATH, exist_ok=True)

def _save_api_response(account_name, response):
    """Saves the raw API response to a file for debugging."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{account_name}_balance_{timestamp}.json"
        filepath = os.path.join(API_LOG_PATH, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            try:
                json.dump(response.json(), f, indent=4)
            except json.JSONDecodeError:
                f.write(response.text)
        logger.info(f"Saved API response for {account_name} to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save API response for {account_name}: {e}")


def get_wallet_balances():
    """Fetches wallet balances for all configured accounts."""
    all_balances = {}
    for account in ACCOUNTS:
        token = fetch_token_with_retry(account)
        if not token:
            logger.error(f"Could not authenticate for {account['name']} to fetch wallet balances.")
            all_balances[account['name']] = {"error": "Authentication failed."}
            continue

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
        
        response = None
        try:
            if platform == "Paxful":
                url = "https://api.paxful.com/paxful/v1/wallet/balance"
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                response = requests.post(url, headers=headers, timeout=15)
            else: # Noones
                url = "https://api.noones.com/noones/v1/user/wallet-balances"
                # --- CORRECTED CONTENT-TYPE AS PER THE ERROR MESSAGE ---
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                response = requests.post(url, headers=headers, timeout=15)

            if response:
                _save_api_response(account['name'], response)

            if response.status_code == 200:
                data = response.json().get("data", {})
                if platform == "Paxful":
                    if data and 'crypto_currency_code' in data and 'balance' in data:
                        all_balances[account['name']] = {
                            data['crypto_currency_code']: data['balance']
                        }
                    else:
                         all_balances[account['name']] = {"error": "Unexpected Paxful data structure"}
                else: # Noones
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

        except requests.exceptions.RequestException as e:
            logger.error(f"An exception occurred fetching balance for {account['name']}: {e}")
            all_balances[account['name']] = {"error": "Request failed"}
            
    return all_balances