import requests

def get_trade_history(headers, limit=10, page=1):
    api_url_trades = 'https://api.noones.com/noones/v1/trade/completed'
    data = {
        'page': page,
        'count': 1,
        'limit': limit
    }

    api_response_trades = requests.post(api_url_trades, headers=headers, data=data)
    
    if api_response_trades.status_code == 200:
        trades_data = api_response_trades.json()

        # Check if there are trades to display
        if trades_data['status'] == 'success' and trades_data['data']['trades']:
            trades = trades_data['data']['trades']

            # Start building the HTML table
            html_content = '''
            <html>
            <head>
                <title>Completed Trades</title>
                <style>
                    table {border-collapse: collapse; width: 100%;}
                    th, td {border: 1px solid black; padding: 8px; text-align: left;}
                    th {background-color: #f2f2f2;}
                </style>
            </head>
            <body>
                <h1>Completed Trades</h1>
                <table>
                    <tr>
                        <th>Trade Status</th>
                        <th>Trade Hash</th>
                        <th>Offer Hash</th>
                        <th>Location</th>
                        <th>Fiat Amount Requested</th>
                        <th>Payment Method</th>
                        <th>Crypto Amount Requested</th>
                        <th>Started At</th>
                        <th>Seller</th>
                        <th>Buyer</th>
                        <th>Fiat Currency</th>
                        <th>Ended At</th>
                        <th>Completed At</th>
                        <th>Offer Type</th>
                        <th>Seller Avatar</th>
                        <th>Buyer Avatar</th>
                        <th>Status</th>
                        <th>Crypto Currency</th>
                    </tr>'''

            # Add each trade to the table
            for trade in trades:
                html_content += f'''
                    <tr>
                        <td>{trade.get('trade_status', 'N/A')}</td>
                        <td>{trade.get('trade_hash', 'N/A')}</td>
                        <td>{trade.get('offer_hash', 'N/A')}</td>
                        <td>{trade.get('location_iso', 'N/A')}</td>
                        <td>{trade.get('fiat_amount_requested', 'N/A')}</td>
                        <td>{trade.get('payment_method_name', 'N/A')}</td>
                        <td>{trade.get('crypto_amount_requested', 'N/A')}</td>
                        <td>{trade.get('started_at', 'N/A')}</td>
                        <td>{trade.get('seller', 'N/A')}</td>
                        <td>{trade.get('buyer', 'N/A')}</td>
                        <td>{trade.get('fiat_currency_code', 'N/A')}</td>
                        <td>{trade.get('ended_at', 'N/A')}</td>
                        <td>{trade.get('completed_at', 'N/A')}</td>
                        <td>{trade.get('offer_type', 'N/A')}</td>
                        <td><img src="{trade.get('seller_avatar_url', '')}" alt="Seller Avatar" width="50" height="50"></td>
                        <td><img src="{trade.get('buyer_avatar_url', '')}" alt="Buyer Avatar" width="50" height="50"></td>
                        <td>{trade.get('status', 'N/A')}</td>
                        <td>{trade.get('crypto_currency_code', 'N/A')}</td>
                    </tr>'''

            # Close the table and HTML tags
            html_content += '''
                </table>
            </body>
            </html>
            '''

            return html_content
        else:
            return "No completed trades found."
    else:
        return f"Error fetching trades: {api_response_trades.status_code} - {api_response_trades.text}"
