import requests
import time
import logging
from config import TOKEN_URL_NOONES, TOKEN_URL_PAXFUL

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def fetch_token_with_retry(account, max_retries=3):
    """Fetch an access token with retry logic, handling different APIs for Noones and Paxful."""
    
    # Determine API URL
    token_url = TOKEN_URL_PAXFUL if "_Paxful" in account["name"] else TOKEN_URL_NOONES
    token_data = {
        "grant_type": "client_credentials",
        "client_id": account["api_key"],
        "client_secret": account["secret_key"]
    }

    for attempt in range(max_retries):
        try:
            logging.debug(f"Attempt {attempt + 1} of {max_retries} to fetch token for {account['name']} using {token_url}")
            response = requests.post(token_url, data=token_data, timeout=10)

            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                logging.error(f"Failed to fetch token for {account['name']}. Status Code: {response.status_code} - {response.text}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logging.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed on attempt {attempt + 1}: {e}")

        if attempt == max_retries - 1:
            logging.error("Max retries reached. Giving up.")
            return None

    return None
