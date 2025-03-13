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

            # Start building the HTML table for the trade
            html_content = '''
            <html>
            <head>
                <title>Trade Details</title>
                <style>
                    table {border-collapse: collapse; width: 100%;}
                    th, td {border: 1px solid black; padding: 8px; text-align: left;}
                    th {background-color: #f2f2f2;}
                </style>
            </head>
            <body>
                <h1>Trade Details</h1>
                <table>
                    <tr><th>Trade Hash</th><td>{}</td></tr>
                    <tr><th>Trade Status</th><td>{}</td></tr>
                    <tr><th>Buyer Name</th><td>{}</td></tr>
                    <tr><th>Seller Name</th><td>{}</td></tr>
                    <tr><th>Offer Hash</th><td>{}</td></tr>
                    <tr><th>Payment Method</th><td>{}</td></tr>
                    <tr><th>Fiat Amount Requested</th><td>{}</td></tr>
                    <tr><th>Crypto Amount Requested</th><td>{}</td></tr>
                    <tr><th>Completed At</th><td>{}</td></tr>
                    <tr><th>Cancelled At</th><td>{}</td></tr>
                    <tr><th>Dispute Reason</th><td>{}</td></tr>
                    <tr><th>Fee Percentage</th><td>{}</td></tr>
                    <tr><th>Crypto Currency</th><td>{}</td></tr>
                    <tr><th>Fiat Currency Code</th><td>{}</td></tr>
                </table>
            </body>
            </html>
            '''.format(
                trade.get('trade_hash', 'N/A'),
                trade.get('trade_status', 'N/A'),
                trade.get('buyer_name', 'N/A'),
                trade.get('seller_name', 'N/A'),
                trade.get('offer_hash', 'N/A'),
                trade.get('payment_method_name', 'N/A'),
                trade.get('fiat_amount_requested', 'N/A'),
                trade.get('crypto_amount_requested', 'N/A'),
                trade.get('completed_at', 'N/A'),
                trade.get('cancelled_at', 'N/A'),
                trade.get('dispute', {}).get('reason', 'N/A'),
                trade.get('fee_percentage', 'N/A'),
                trade.get('crypto_currency_code', 'N/A'),
                trade.get('fiat_currency_code', 'N/A')
            )

            return html_content
        else:
            return "Trade not found or error in response."
    else:
        return f"Error fetching trade: {api_response_trade.status_code} - {api_response_trade.text}"