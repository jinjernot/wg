"""
Binance Fiat Orders Fetching
Fetches pure fiat deposit/withdrawal orders from Binance API (SPEI, bank transfers)
This is different from fiat/payments which is for fiat-to-crypto purchases
"""
import time
import requests
from requests.exceptions import RequestException, ConnectionError
from http.client import RemoteDisconnected
from urllib3.exceptions import ProtocolError

from core.binance.auth import generate_auth_headers
import binance_config


def fetch_fiat_orders_for_user(user, api_key, api_secret, start_time=None, end_time=None, max_retries=5, backoff_factor=1.5):
    """
    Fetch pure fiat deposit/withdrawal orders for a Binance user account
    This endpoint captures SPEI bank transfers and other direct fiat deposits
    
    Args:
        user: Username identifier
        api_key: Binance API key
        api_secret: Binance API secret
        start_time: Optional - start timestamp in milliseconds
        end_time: Optional - end timestamp in milliseconds
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
    
    Returns:
        List of fiat order records
    """
    endpoint = '/sapi/v1/fiat/orders'
    url = binance_config.BASE_URL + endpoint
    
    all_orders = []
    page = 1
    rows = 500  # Max allowed by Binance
    
    print(f"\nFetching fiat orders (SPEI/bank transfers) for {user}...")
    
    while True:
        # Build query parameters
        params = {
            'transactionType': 0,  # 0 = deposit, 1 = withdrawal
            'page': page,
            'rows': rows
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
            print(f"⚠️ WARNING: Failed to fetch fiat orders after {max_retries} retries for user {user}.")
            return []
        
        # Parse response
        data = response.json()
        
        # Response structure: {"code": "000000", "message": "success", "data": [...], "total": N}
        if data.get('code') != '000000':
            print(f"API error for {user}: {data.get('message', 'Unknown error')}")
            break
        
        orders = data.get('data', [])
        total_records = data.get('total', 0)
        
        if not orders or len(orders) == 0:
            print(f"No more fiat orders found for {user}.")
            break
        
        all_orders.extend(orders)
        print(f"Fetched {len(orders)} fiat orders (total: {len(all_orders)}/{total_records})")
        
        # Check if we've fetched all records
        if len(all_orders) >= total_records:
            print(f"All fiat orders retrieved for {user}.")
            break
        
        page += 1
    
    print(f"Total fiat orders fetched for {user}: {len(all_orders)}")
    return all_orders
