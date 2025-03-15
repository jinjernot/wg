import requests

def send_welcome_message(trade_hash, headers):
    url = "https://api.noones.com/noones/v1/trade-chat/post"
    
    # Correct request body format
    body = {
        "trade_hash": trade_hash,
        "message": "Welcome to WillGang Trading"
    }

    # Ensure the correct content type is set
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    
    response = requests.post(url, data=body, headers=headers)

    if response.status_code == 200:
        print(f"Welcome message sent for trade {trade_hash}")
    else:
        print(f"Failed to send welcome message for trade {trade_hash}. Status Code: {response.status_code} - {response.text}")
