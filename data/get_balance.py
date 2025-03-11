import requests
import time
import hmac
import hashlib
import json

from config import *

def generate_signature(api_secret, data):
    return hmac.new(api_secret.encode(), data.encode(), hashlib.sha256).hexdigest()

def get_paxful_wallet_balance():
    url = "https://paxful.com/api/wallet/balance"
    params = {
        "apikey": PAXFUL_API_KEY,
        "nonce": str(int(time.time() * 1000))
    }
    
    signature = generate_signature(PAXFUL_SECRET_KEY, json.dumps(params))
    headers = {"Paxful-Signature": signature}
    
    response = requests.post(url, headers=headers, json=params)
    
    if response.status_code == 200:
        return response.json()
    return response.text


def get_noones_wallet_balance():
    url = "https://noones.com/api/wallet/balance"  
    params = {
        "apikey": NOONES_API_KEY,
        "nonce": str(int(time.time() * 1000))
    }
    
    signature = generate_signature(NOONES_SECRET_KEY, json.dumps(params))
    headers = {"Noones-Signature": signature} 
    
    response = requests.post(url, headers=headers, json=params)
    
    if response.status_code == 200:
        return response.json() 
    return response.text 

def get_wallet_balances():
    paxful_balance = get_paxful_wallet_balance()
    noones_balance = get_noones_wallet_balance()
    
    return {
        "Paxful": paxful_balance,
        "Noones": noones_balance
    }