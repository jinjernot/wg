"""
Binance Fiat Deposit Fetching
Fetches fiat deposit/payment history from Binance API (SPEI, bank transfers, etc.)
"""
import time
import requests
from requests.exceptions import RequestException, ConnectionError
from http.client import RemoteDisconnected
from urllib3.exceptions import ProtocolError

from core.binance.auth import generate_auth_headers
import binance_config


def fetch_fiat_deposit_history_for_user(user, api_key, api_secret, start_time=None, end_time=None, max_retries=5, backoff_factor=1.5):
    """
    Fetch fiat deposit/payment history for a Binance user account
    
    Args:
        user: Username identifier
        api_key: Binance API key
        api_secret: Binance API secret
        start_time: Optional - start timestamp in milliseconds
        end_time: Optional - end timestamp in milliseconds
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
    
    Returns:
        List of fiat deposit records
    """
    # NOTE: Binance has two fiat endpoints:
    # - /sapi/v1/fiat/orders: Pure fiat deposits/withdrawals (bank transfers, SPEI)
    # - /sapi/v1/fiat/payments: Fiat-to-crypto purchases (buying crypto with fiat)
    # This function uses 'payments' to track crypto purchases made with fiat currency
    endpoint = '/sapi/v1/fiat/payments'
    url = binance_config.BASE_URL + endpoint
    
    all_deposits = []
    page = 1  # Binance fiat API uses 1-based pagination
    rows = 500  # Max allowed by Binance for fiat payments
    
    print(f"\nFetching fiat deposit history for {user}...")
    
    while True:
        # Build query parameters
        params = {
            'transactionType': 0,  # 0 = deposit, 1 = withdrawal (integer, not string)
            'page': page,  # Integer page number
            'rows': rows   # Integer rows per page
        }
        
        if start_time:
            params['beginTime'] = int(start_time)
        if end_time:
            params['endTime'] = int(end_time)
        
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
            print(f"⚠️ WARNING: Failed to fetch fiat data after {max_retries} retries for user {user}.")
            print(f"   This account may be blocked or experiencing issues. Continuing with remaining accounts...")
            return []  # Return empty list to skip this account
        
        # Parse response
        data = response.json()
        
        # The response structure is: {"code": "000000", "message": "success", "data": [...], "total": N}
        if data.get('code') != '000000':
            print(f"API error for {user}: {data.get('message', 'Unknown error')}")
            break
        
        deposits = data.get('data', [])
        total_records = data.get('total', 0)
        
        if not deposits or len(deposits) == 0:
            print(f"No more fiat deposits found for {user}.")
            break
        
        all_deposits.extend(deposits)
        print(f"Fetched {len(deposits)} fiat deposits (total: {len(all_deposits)}/{total_records})")
        
        # Check if we've fetched all records
        if len(all_deposits) >= total_records:
            print(f"All fiat deposits retrieved for {user}.")
            break
        
        page += 1
    
    print(f"Total fiat deposits fetched for {user}: {len(all_deposits)}")
    return all_deposits
