"""
Binance Deposit Fetching
Fetches deposit history from Binance API with retry logic and pagination
"""
import time
import requests
from requests.exceptions import RequestException, ConnectionError
from http.client import RemoteDisconnected
from urllib3.exceptions import ProtocolError

from core.binance.auth import generate_auth_headers
import binance_config


def fetch_deposit_history_for_user(user, api_key, api_secret, coin=None, start_time=None, end_time=None, max_retries=5, backoff_factor=1.5):
    """
    Fetch deposit history for a Binance user account
    
    Args:
        user: Username identifier
        api_key: Binance API key
        api_secret: Binance API secret
        coin: Optional - filter by specific cryptocurrency
        start_time: Optional - start timestamp in milliseconds
        end_time: Optional - end timestamp in milliseconds
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
    
    Returns:
        List of deposit records
    """
    endpoint = '/sapi/v1/capital/deposit/hisrec'
    url = binance_config.BASE_URL + endpoint
    
    all_deposits = []
    offset = 0
    limit = 1000  # Max allowed by Binance
    
    print(f"\nFetching deposit history for {user}...")
    
    while True:
        # Build query parameters
        params = {'limit': limit, 'offset': offset}
        
        if coin:
            params['coin'] = coin
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
        
        retries = 0
        while retries < max_retries:
            try:
                # Generate authentication
                auth_data = generate_auth_headers(api_key, api_secret, params)
                
                # Make API request
                response = requests.get(
                    f"{url}?{auth_data['query_string']}", 
                    headers=auth_data['headers'], 
                    timeout=10
                )
                
                if response.status_code == 200:
                    break  # Success
                else:
                    print(f"Non-200 status code: {response.status_code} - {response.text}")
                    raise RequestException(f"Non-200 response: {response.status_code}")
            
            except (ConnectionError, RemoteDisconnected, ProtocolError) as conn_err:
                print(f"Connection error: {conn_err}. Retrying...")
            
            except RequestException as req_err:
                print(f"Request error: {req_err}. Retrying...")
            
            retries += 1
            sleep_time = backoff_factor ** retries
            print(f"Retry {retries}/{max_retries} - sleeping {sleep_time:.1f} seconds...")
            time.sleep(sleep_time)
        else:
            print(f"⚠️ WARNING: Failed to fetch data after {max_retries} retries for user {user}.")
            print(f"   This account may be blocked or experiencing issues. Continuing with remaining accounts...")
            return []  # Return empty list to skip this account
        
        # Parse response
        deposits = response.json()
        
        if not deposits or len(deposits) == 0:
            print(f"No more deposits found for {user}.")
            break
        
        all_deposits.extend(deposits)
        print(f"Fetched {len(deposits)} deposits (total: {len(all_deposits)})")
        
        # Check if we got fewer results than the limit (last page)
        if len(deposits) < limit:
            print(f"Final page reached for {user}.")
            break
        
        offset += limit
    
    print(f"Total deposits fetched for {user}: {len(all_deposits)}")
    return all_deposits
