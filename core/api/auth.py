import time
import logging
from config import TOKEN_URL_NOONES, TOKEN_URL_PAXFUL
from core.utils.token_cache import get_token_cache
from core.utils.http_client import get_http_client

logger = logging.getLogger(__name__)

def fetch_token_with_retry(account, max_retries=3, force_refresh=False):
    """
    Fetch authentication token with caching and retry logic.
    
    Args:
        account: Account configuration dict
        max_retries: Maximum retry attempts
        force_refresh: If True, bypass cache and fetch new token
        
    Returns:
        Access token string or None on failure
    """
    account_name = account["name"]
    
    # Check cache first unless force refresh
    if not force_refresh:
        token_cache = get_token_cache()
        cached_token = token_cache.get(account_name)
        if cached_token:
            return cached_token
    
    # Token not in cache or expired, fetch new one
    token_url = TOKEN_URL_PAXFUL if "_Paxful" in account_name else TOKEN_URL_NOONES
    token_data = {
        "grant_type": "client_credentials",
        "client_id": account["api_key"],
        "client_secret": account["secret_key"]
    }
    
    http_client = get_http_client()

    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1} of {max_retries} to fetch token for {account_name} using {token_url}")
            response = http_client.post(token_url, data=token_data, timeout=20)

            if response.status_code == 200:
                token = response.json().get("access_token")
                
                # Cache the token (default 55 minute TTL)
                token_cache = get_token_cache()
                token_cache.set(account_name, token)
                
                return token
            else:
                logger.error(f"Failed to fetch token for {account_name}. Status Code: {response.status_code} - {response.text}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt 
                logger.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Request failed on attempt {attempt + 1}: {e}")

        if attempt == max_retries - 1:
            logger.error(f"Max retries reached for {account_name}. Giving up.")
            return None

    return None