import requests
import csv

from config import *
# Function to get an access token for an account
def get_access_token(api_key, secret_key):
    token_data = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key
    }

    response = requests.post(TOKEN_URL, data=token_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"Error fetching token: {response.status_code} - {response.text}")
        return None

# Function to fetch completed trade history and save as CSV
def get_trade_history(api_key, secret_key, account_name, limit=10, page=1):
    access_token = get_access_token(api_key, secret_key)
    if not access_token:
        print(f"{account_name}: Failed to get access token.")
        return

    headers = {"Authorization": f"Bearer {access_token}"}
    data = {"page": page, "count": 1, "limit": limit}

    response = requests.post(API_URL, headers=headers, data=data)

    if response.status_code == 200:
        trades_data = response.json()

        if trades_data["status"] == "success" and trades_data["data"]["trades"]:
            trades = trades_data["data"]["trades"]

            # Define CSV file path
            csv_filename = f"{account_name.lower()}_trades.csv"

            # Define CSV headers
            headers = [
                "Trade Status", "Trade Hash", "Offer Hash", "Location", "Fiat Amount Requested",
                "Payment Method", "Crypto Amount Requested", "Started At", "Seller", "Buyer",
                "Fiat Currency", "Ended At", "Completed At", "Offer Type", "Seller Avatar URL",
                "Buyer Avatar URL", "Status", "Crypto Currency"
            ]

            # Write to CSV file
            with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)  # Write header row

                for trade in trades:
                    writer.writerow([
                        trade.get("trade_status", "N/A"),
                        trade.get("trade_hash", "N/A"),
                        trade.get("offer_hash", "N/A"),
                        trade.get("location_iso", "N/A"),
                        trade.get("fiat_amount_requested", "N/A"),
                        trade.get("payment_method_name", "N/A"),
                        trade.get("crypto_amount_requested", "N/A"),
                        trade.get("started_at", "N/A"),
                        trade.get("seller", "N/A"),
                        trade.get("buyer", "N/A"),
                        trade.get("fiat_currency_code", "N/A"),
                        trade.get("ended_at", "N/A"),
                        trade.get("completed_at", "N/A"),
                        trade.get("offer_type", "N/A"),
                        trade.get("seller_avatar_url", "N/A"),
                        trade.get("buyer_avatar_url", "N/A"),
                        trade.get("status", "N/A"),
                        trade.get("crypto_currency_code", "N/A")
                    ])

            print(f"Trade history saved for {account_name} as {csv_filename}.")
        else:
            print(f"{account_name}: No completed trades found.")
    else:
        print(f"{account_name}: Error fetching trades - {response.status_code} - {response.text}")

# Main function to generate CSV reports for Joe and David
def main():
    get_trade_history(NOONES_API_KEY_JOE, NOONES_SECRET_KEY_JOE, "Joe")
    get_trade_history(NOONES_API_KEY_DAVID, NOONES_SECRET_KEY_DAVID, "David")

if __name__ == "__main__":
    main()
