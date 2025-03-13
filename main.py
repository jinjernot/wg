import requests
from config import *
from data.get_history import get_trade_history  # Import trade history
from data.get_trade_list import get_trade_list  # Import trade list function

token_url = 'https://auth.noones.com/oauth2/token'
token_data = {
    'grant_type': 'client_credentials',
    'client_id': NOONES_API_KEY,
    'client_secret': NOONES_SECRET_KEY
}

response = requests.post(token_url, data=token_data)
if response.status_code == 200:
    access_token = response.json()['access_token']

    headers = {'Authorization': f'Bearer {access_token}'}

    api_url_userinfo = 'https://auth.noones.com/oauth2/userinfo'
    api_response_userinfo = requests.get(api_url_userinfo, headers=headers)
    if api_response_userinfo.status_code == 200:
        print(f"User Info: {api_response_userinfo.json()}")
    else:
        print(f"Error fetching user info: {api_response_userinfo.status_code} - {api_response_userinfo.text}")

    # Get completed trades history
    html_content_history = get_trade_history(headers, limit=10, page=1)
    if html_content_history:
        with open('completed_trades.html', 'w') as file:
            file.write(html_content_history)
        print("HTML file 'completed_trades.html' has been generated.")
    else:
        print("No completed trades found.")

    # Get trade list
    html_content_trade_list = get_trade_list(headers)
    if html_content_trade_list:
        with open('trade_list.html', 'w') as file:
            file.write(html_content_trade_list)
        print("HTML file 'trade_list.html' has been generated.")
    else:
        print("No trade list found.")

else:
    print(f"Error fetching token: {response.status_code} - {response.text}")
