import requests
from config import TRADE_LIST_URL


def get_trade_list(headers, limit=10, page=1):
    data = {
        "page": page,
        "count": 1,
        "limit": limit  # Modify as needed
    }
    
    response = requests.post(TRADE_LIST_URL, headers=headers, json=data)
    
    if response.status_code == 200:
        trades_data = response.json()

        if trades_data.get("status") == "success" and trades_data["data"].get("trades"):
            return trades_data["data"]["trades"]  # Return the list of trades
        else:
            print("No trades found.")
            return []
    else:
        print(f"Error fetching trade list: {response.status_code} - {response.text}")
        return []
