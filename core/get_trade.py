import requests
from config import GET_TRADE_URL

def get_trade(headers, trade_hash):
    body = {
        "data": {
            "trade": {
                "trade_hash": trade_hash
            }
        }
    }

    api_response_trade = requests.post(GET_TRADE_URL, headers=headers, json=body)

    if api_response_trade.status_code == 200:
        trade_data = api_response_trade.json()

        if trade_data['status'] == 'success' and trade_data['data']:
            trade = trade_data['data']['trade']

            return trade
        else:
            return "Trade not found or error in response."
    else:
        return f"Error fetching trade: {api_response_trade.status_code} - {api_response_trade.text}"
