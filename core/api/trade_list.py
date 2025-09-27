import requests
import certifi
import logging
import json
import time
import os 
from config import TRADE_LIST_URL_NOONES, TRADE_LIST_URL_PAXFUL, ACTIVE_TRADES_DIR

logger = logging.getLogger(__name__)


def get_trade_list(account, headers, limit=10, page=1, max_retries=3):
    if "_Paxful" in account["name"]:
        trade_list_url = TRADE_LIST_URL_PAXFUL
    else:
        trade_list_url = TRADE_LIST_URL_NOONES

    data = {
        "page": page,
        "count": 1,
        "limit": limit
    }
    
    headers_paxful = headers.copy()
    if "_Paxful" in account["name"]:
        headers_paxful["Content-Type"] = "application/x-www-form-urlencoded"
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1} of {max_retries} for {account['name']}")
            response = requests.post(
                trade_list_url,
                headers=headers_paxful,
                json=data if "_Paxful" not in account["name"] else data,  
                verify=certifi.where(),
                timeout=10
            )
            
            if response.status_code == 200:
                trades_data = response.json()
                filename = f"{account['name'].replace(' ', '_')}_trades.json"
                filepath = os.path.join(ACTIVE_TRADES_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as json_file:
                    json.dump(trades_data, json_file, indent=4)
                logger.info(f"Saved raw trade data to {filepath}")

                if trades_data.get("status") == "success" and trades_data["data"].get("trades"):
                    return trades_data["data"]["trades"]
                else:
                    logger.warning(f"No trades found for {account['name']}.")
                    return []
            else:
                logger.error(f"Error fetching trade list for {account['name']}: {response.status_code} - {response.text}")
                return []
        
        except requests.exceptions.SSLError as e:
            logger.error(f"SSL Error on attempt {attempt + 1} for {account['name']}: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                logger.error("Max retries reached. Giving up.")
                return []
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed on attempt {attempt + 1} for {account['name']}: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                logger.error("Max retries reached. Giving up.")
                return []
    
    return []