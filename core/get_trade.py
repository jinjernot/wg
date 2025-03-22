import requests
from config import GET_TRADE_URL_NOONES, GET_TRADE_URL_PAXFUL

def get_trade(account, headers, trade_hash):
    # Determine which API URL to use
    if "_Paxful" in account["name"].upper():
        trade_url = GET_TRADE_URL_PAXFUL
    else:
        trade_url = GET_TRADE_URL_NOONES

    body = {
        "data": {
            "trade": {
                "trade_hash": trade_hash
            }
        }
    }

    try:
        api_response_trade = requests.post(trade_url, headers=headers, json=body, timeout=10)

        if api_response_trade.status_code == 200:
            trade_data = api_response_trade.json()

            if trade_data.get("status") == "success" and trade_data.get("data"):
                return trade_data["data"].get("trade", "Trade data not found.")
            else:
                return "Trade not found or error in response."
        else:
            return f"Error fetching trade: {api_response_trade.status_code} - {api_response_trade.text}"

    except requests.exceptions.RequestException as e:
        return f"Request failed: {e}"
