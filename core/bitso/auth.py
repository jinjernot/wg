import hmac
import hashlib
import time

def generate_auth_headers_for_user(endpoint, method='GET', query_params=None, api_key=None, api_secret=None):
    nonce = str(int(time.time() * 1000))

    query_string = ''
    if query_params:
        sorted_params = sorted(query_params.items())
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        endpoint_with_query = f"{endpoint}?{query_string}"
    else:
        endpoint_with_query = endpoint

    message = nonce + method + endpoint_with_query
    signature = hmac.new(
        api_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return {
        'Authorization': f'Bitso {api_key}:{nonce}:{signature}',
        'Content-Type': 'application/json'
    }
