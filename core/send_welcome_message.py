import requests
import time

def send_welcome_message(trade_hash):
    url = "https://api.noones.com/noones/v1/trade-chat/post"
    body = {
        "data": {
            "id": trade_hash,
            "success": True,
            "message": "Welcome to WillGang Trading"
        },
        "status": "success",
        "timestamp": int(time.time())
    }
    
    response = requests.post(url, json=body)
    if response.status_code == 200:
        print(f"Welcome message sent for trade {trade_hash}")
    else:
        print(f"Failed to send welcome message for trade {trade_hash}. Status Code: {response.status_code}")
