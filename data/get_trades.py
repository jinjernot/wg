from config import *
import time
import hmac
import hashlib
import json
import requests



def generate_signature(api_secret, data):
    return hmac.new(api_secret.encode(), data.encode(), hashlib.sha256).hexdigest()


def fetch_paxful_trades():
    url = "https://paxful.com/api/trade/list"
    params = {
        "apikey": PAXFUL_API_KEY,
        "nonce": str(int(time.time() * 1000))
    }
    signature = generate_signature(PAXFUL_SECRET_KEY, json.dumps(params))
    headers = {"Paxful-Signature": signature}
    
    response = requests.post(url, headers=headers, json=params)
    if response.status_code == 200:
        return response.json()
    return None

def fetch_noones_trades():
    url = "https://noones.com/api/trade/list"
    params = {
        "apikey": NOONES_API_KEY,
        "nonce": str(int(time.time() * 1000))
    }
    signature = generate_signature(NOONES_SECRET_KEY, json.dumps(params))
    headers = {"Noones-Signature": signature}
    
    response = requests.post(url, headers=headers, json=params)
    if response.status_code == 200:
        return response.json()
    return None


def get_trade_details(trade_hash, platform):
    """Fetch trade details from Paxful or Noones based on the platform."""
    if platform == "paxful":
        url = "https://paxful.com/api/trade/details"
        params = {
            "apikey": PAXFUL_API_KEY,
            "nonce": str(int(time.time() * 1000)),
            "trade_hash": trade_hash
        }
        signature = generate_signature(PAXFUL_SECRET_KEY, json.dumps(params))
        headers = {"Paxful-Signature": signature}
    elif platform == "noones":
        url = "https://noones.com/api/trade/details"
        params = {
            "apikey": NOONES_API_KEY,
            "nonce": str(int(time.time() * 1000)),
            "trade_hash": trade_hash
        }
        signature = generate_signature(NOONES_SECRET_KEY, json.dumps(params))
        headers = {"Noones-Signature": signature}
    
    response = requests.post(url, headers=headers, json=params)
    if response.status_code == 200:
        return response.json()
    return None