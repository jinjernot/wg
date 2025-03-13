import requests

def get_trade_list(headers):
    api_url_trade_list = 'https://api.noones.com/noones/v1/trade/list'
    
    # Define the request payload
    body = {
        "data": {
            "count": 1
        }
    }

    # Make a POST request
    api_response = requests.post(api_url_trade_list, headers=headers, json=body)

    if api_response.status_code == 200:
        trade_data = api_response.json()

        # Check if there are trades in response
        if trade_data['status'] == 'success' and 'data' in trade_data and 'trades' in trade_data['data']:
            trades = trade_data['data']['trades']

            # Generate HTML content
            html_content = '''
            <html>
            <head>
                <title>Trade List</title>
                <style>
                    table {border-collapse: collapse; width: 100%;}
                    th, td {border: 1px solid black; padding: 8px; text-align: left;}
                    th {background-color: #f2f2f2;}
                </style>
            </head>
            <body>
                <h1>Trade List</h1>
                <table>
                    <tr>
                        <th>Trade Hash</th>
                        <th>Offer Type</th>
                        <th>Trade Status</th>
                        <th>Payment Method</th>
                        <th>Fiat Amount</th>
                        <th>Crypto Amount</th>
                        <th>Fiat Currency</th>
                        <th>Crypto Currency</th>
                        <th>Started At</th>
                        <th>Completed At</th>
                        <th>Cancelled At</th>
                        <th>Owner</th>
                        <th>Responder</th>
                        <th>Location</th>
                    </tr>'''

            # Add trade data to the table
            for trade in trades:
                html_content += f'''
                    <tr>
                        <td>{trade.get('trade_hash', 'N/A')}</td>
                        <td>{trade.get('offer_type', 'N/A')}</td>
                        <td>{trade.get('trade_status', 'N/A')}</td>
                        <td>{trade.get('payment_method_name', 'N/A')}</td>
                        <td>{trade.get('fiat_amount_requested', 'N/A')}</td>
                        <td>{trade.get('crypto_amount_requested', 'N/A')}</td>
                        <td>{trade.get('fiat_currency_code', 'N/A')}</td>
                        <td>{trade.get('crypto_currency_code', 'N/A')}</td>
                        <td>{trade.get('started_at', 'N/A')}</td>
                        <td>{trade.get('completed_at', 'N/A')}</td>
                        <td>{trade.get('cancelled_at', 'N/A')}</td>
                        <td>{trade.get('owner_username', 'N/A')}</td>
                        <td>{trade.get('responder_username', 'N/A')}</td>
                        <td>{trade.get('location_iso', 'N/A')}</td>
                    </tr>'''

            html_content += '''
                </table>
            </body>
            </html>
            '''

            return html_content
        else:
            return "No trades found."
    else:
        return f"Error fetching trade list: {api_response.status_code} - {api_response.text}"