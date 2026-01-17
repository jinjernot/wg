"""
Binance API Authentication
Generates authentication headers for Binance API requests using HMAC SHA256
"""
import hmac
import hashlib
import time

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
