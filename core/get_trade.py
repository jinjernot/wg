import requests

def get_trade(headers, trade_hash):
    api_url_trade = 'https://api.noones.com/noones/v1/trade/get'
    body = {
        "data": {
            "trade": {
                "trade_hash": trade_hash
            }
        }
    }

    api_response_trade = requests.post(api_url_trade, headers=headers, json=body)

    if api_response_trade.status_code == 200:
        trade_data = api_response_trade.json()

        # Check if the trade is returned successfully
        if trade_data['status'] == 'success' and trade_data['data']:
            trade = trade_data['data']['trade']

            # Return the trade data directly
            return trade
        else:
            return "Trade not found or error in response."
    else:
        return f"Error fetching trade: {api_response_trade.status_code} - {api_response_trade.text}"
