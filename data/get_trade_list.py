import requests
import certifi
import logging
import time
from config import TRADE_LIST_URL

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def get_trade_list(headers, limit=10, page=1, max_retries=3):
    data = {
        "page": page,
        "count": 1,
        "limit": limit
    }
    
    for attempt in range(max_retries):
        try:
            logging.debug(f"Attempt {attempt + 1} of {max_retries}")
            response = requests.post(
                TRADE_LIST_URL,
                headers=headers,
                json=data,
                verify=certifi.where(),  # Use certifi's CA bundle
                timeout=10  # Set a timeout to avoid hanging
            )
            
            if response.status_code == 200:
                trades_data = response.json()
                if trades_data.get("status") == "success" and trades_data["data"].get("trades"):
                    return trades_data["data"]["trades"]
                else:
                    logging.warning("No trades found.")
                    return []
            else:
                logging.error(f"Error fetching trade list: {response.status_code} - {response.text}")
                return []
        
        except requests.exceptions.SSLError as e:
            logging.error(f"SSL Error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logging.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                logging.error("Max retries reached. Giving up.")
                return []
        
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logging.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                logging.error("Max retries reached. Giving up.")
                return []
    
    return []  # Return an empty list if all retries fail