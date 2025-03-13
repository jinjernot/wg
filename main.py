import requests
from config import *
from data.get_history import get_trade_history  # Import the function

# Define token and API URLs
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

    # Define headers for the API requests
    headers = {'Authorization': f'Bearer {access_token}'}

    # Step 1: Fetch User Info
    api_url_userinfo = 'https://auth.noones.com/oauth2/userinfo'
    api_response_userinfo = requests.get(api_url_userinfo, headers=headers)
    if api_response_userinfo.status_code == 200:
        print(f"User Info: {api_response_userinfo.json()}")
    else:
        print(f"Error fetching user info: {api_response_userinfo.status_code} - {api_response_userinfo.text}")

    # Step 2: Fetch Completed Trades
    html_content = get_trade_history(headers, limit=10, page=1)

    if html_content:
        # Save the HTML to a file
        with open('completed_trades.html', 'w') as file:
            file.write(html_content)
        print("HTML file 'completed_trades.html' has been generated.")
    else:
        print("No completed trades found.")
else:
    print(f"Error fetching token: {response.status_code} - {response.text}")
