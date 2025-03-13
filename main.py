import requests
from config import *

token_url = 'https://auth.noones.com/oauth2/token'
token_data = {
    'grant_type': 'client_credentials',
    'client_id': NOONES_API_KEY,
    'client_secret': NOONES_SECRET_KEY
}

# Get the token
response = requests.post(token_url, data=token_data)
if response.status_code == 200:
    access_token = response.json()['access_token']
    #print(f"Access Token: {access_token}")

    api_url_userinfo = 'https://auth.noones.com/oauth2/userinfo'
    headers = {'Authorization': f'Bearer {access_token}'}
    
    api_response_userinfo = requests.get(api_url_userinfo, headers=headers)
    if api_response_userinfo.status_code == 200:
        print(f"User Info: {api_response_userinfo.json()}")
    else:
        print(f"Error fetching user info: {api_response_userinfo.status_code} - {api_response_userinfo.text}")

    api_url_trades = 'https://api.noones.com/noones/v1/trade/completed'
    
    data = {
        'page': 1,
        'count': 1,
        'limit': 10 
    }

    api_response_trades = requests.post(api_url_trades, headers=headers, data=data)

    if api_response_trades.status_code == 200:
        print(f"Completed Trades: {api_response_trades.json()}")
    else:
        print(f"Error fetching trades: {api_response_trades.status_code} - {api_response_trades.text}")
else:
    print(f"Error fetching token: {response.status_code} - {response.text}")
