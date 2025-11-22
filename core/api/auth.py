import requests
import time
import logging
from config import TOKEN_URL_NOONES, TOKEN_URL_PAXFUL

logger = logging.getLogger(__name__)

def fetch_token_with_retry(account, max_retries=3):
    token_url = TOKEN_URL_PAXFUL if "_Paxful" in account["name"] else TOKEN_URL_NOONES
    token_data = {
        "grant_type": "client_credentials",
        "client_id": account["api_key"],
        "client_secret": account["secret_key"]
    }

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1} of {max_retries} to fetch token for {account['name']} using {token_url}")
            response = requests.post(token_url, data=token_data, timeout=20)

            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                logger.error(f"Failed to fetch token for {account['name']}. Status Code: {response.status_code} - {response.text}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt 
                logger.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed on attempt {attempt + 1}: {e}")

        if attempt == max_retries - 1:
            logger.error(f"Max retries reached for {account['name']}. Giving up.")
            return None

    return None