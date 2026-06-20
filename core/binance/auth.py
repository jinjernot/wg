"""
Binance API Authentication and Request Wrapper
Generates headers and provides a standardized HTTP request handler.
"""
import hmac
import hashlib
import time
import requests
import logging
from requests.exceptions import RequestException, ConnectionError
from http.client import RemoteDisconnected
from urllib3.exceptions import ProtocolError
import binance_config

logger = logging.getLogger(__name__)

def generate_auth_headers(api_key, api_secret, query_params=None):
    """
    Generate authentication headers for Binance API requests
    
    Args:
        api_key: Binance API key
        api_secret: Binance API secret
        query_params: Dictionary of query parameters (optional)
    
    Returns:
        Dictionary containing headers and signed query string
    """
    timestamp = str(int(time.time() * 1000))
    
    # Build query string
    params = query_params.copy() if query_params else {}
    params['timestamp'] = timestamp
    
    # Sort parameters and create query string
    sorted_params = sorted(params.items())
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
    
    # Generate signature using HMAC SHA256
    signature = hmac.new(
        api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Add signature to query string
    signed_query_string = f"{query_string}&signature={signature}"
    
    return {
        'headers': {
            'X-MBX-APIKEY': api_key,
            'Content-Type': 'application/json'
        },
        'query_string': signed_query_string
    }

def make_binance_request(user, api_key, api_secret, endpoint, params, max_retries=5, backoff_factor=1.5):
    """
    Make an authenticated GET request to Binance API with retry and backoff logic.
    
    Args:
        user: Username identifier
        api_key: Binance API key
        api_secret: Binance API secret
        endpoint: API endpoint (e.g. '/sapi/v1/capital/deposit/hisrec')
        params: Dictionary of query parameters
        max_retries: Maximum retry attempts
        backoff_factor: Exponential backoff multiplier
        
    Returns:
        Parsed JSON response (list or dict), or None on fatal failure
    """
    url = binance_config.BASE_URL + endpoint
    retries = 0
    while retries < max_retries:
        try:
            auth_data = generate_auth_headers(api_key, api_secret, params)
            response = requests.get(
                f"{url}?{auth_data['query_string']}", 
                headers=auth_data['headers'], 
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Binance API error for {user} ({endpoint}): HTTP {response.status_code} - {response.text}")
                raise RequestException(f"Non-200 response: {response.status_code}")
        
        except (ConnectionError, RemoteDisconnected, ProtocolError) as conn_err:
            logger.warning(f"Binance connection error for {user} ({endpoint}): {conn_err}. Retrying...")
        except RequestException as req_err:
            logger.warning(f"Binance request error for {user} ({endpoint}): {req_err}. Retrying...")
        
        retries += 1
        sleep_time = backoff_factor ** retries
        logger.info(f"Retry {retries}/{max_retries} for {user} - sleeping {sleep_time:.1f} seconds...")
        time.sleep(sleep_time)
        
    logger.error(f"Failed to fetch data from Binance endpoint {endpoint} after {max_retries} retries for user {user}.")
    return None
