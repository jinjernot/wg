from data.get_trades import *
from config import *
from data.get_trades import *  
import time

def generate_signature(api_secret, data):
    return hmac.new(api_secret.encode(), data.encode(), hashlib.sha256).hexdigest()

def send_noones_chat_message(trade_hash, message):
    
    url = "https://noones.com/api/trade/send_message"
    
    params = {
        "apikey": NOONES_API_KEY,  
        "nonce": str(int(time.time() * 1000)),  
        "trade_hash": trade_hash,  
        "message": message
    }
    
    signature = generate_signature(NOONES_SECRET_KEY, json.dumps(params))
    headers = {"Noones-Signature": signature}
    response = requests.post(url, headers=headers, json=params)
    
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get("status") == "success":
            print(f"Message sent successfully to trade {trade_hash} on Noones")
        else:
            print(f"Failed to send message to trade {trade_hash}: {response_data.get('message')}")
    else:
        print(f"Error sending message: {response.status_code} - {response.text}")


def send_paxful_chat_message(trade_hash, message):
    
    url = "https://paxful.com/api/trade/send_message"
    
    params = {
        "apikey": PAXFUL_API_KEY,
        "nonce": str(int(time.time() * 1000)),
        "trade_hash": trade_hash,
        "message": message
    }
    
    signature = generate_signature(PAXFUL_SECRET_KEY, json.dumps(params))
    headers = {"Paxful-Signature": signature}
    
    response = requests.post(url, headers=headers, json=params)
    
    # Handle the response
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get("status") == "success":
            print(f"Message sent successfully to trade {trade_hash}")
        else:
            print(f"Failed to send message to trade {trade_hash}: {response_data.get('message')}")
    else:
        print(f"Error sending message: {response.status_code} - {response.text}")


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


def send_custom_welcome_message(trade_hash, platform):
    trade_details = get_trade_details(trade_hash, platform)
    
    if trade_details and "data" in trade_details:
        offer_hash = trade_details["data"].get("offer_hash", "")
        message = OFFER_MESSAGES.get(offer_hash, "👋 Welcome to the trade! Let me know if you have any questions.")
        
        if platform == 'paxful':
            send_paxful_chat_message(trade_hash, message)
            send_noones_chat_message(trade_hash, message)


def monitor_new_trades():
    seen_trades = set()

    while True:
        paxful_trades = fetch_paxful_trades()
        if paxful_trades and "data" in paxful_trades:
            for trade in paxful_trades["data"]:
                trade_hash = trade["trade_hash"]
                trade_status = trade["status"]

                if trade_status == "new" and trade_hash not in seen_trades:
                    send_custom_welcome_message(trade_hash, 'paxful')
                    seen_trades.add(trade_hash)

        noones_trades = fetch_noones_trades()
        if noones_trades and "data" in noones_trades:
            for trade in noones_trades["data"]:
                trade_hash = trade["trade_hash"]
                trade_status = trade["status"]

                if trade_status == "new" and trade_hash not in seen_trades:
                    send_custom_welcome_message(trade_hash, 'noones')
                    seen_trades.add(trade_hash)

        time.sleep(60)
