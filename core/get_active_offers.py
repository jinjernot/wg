import requests
import logging
import json
import os
import csv
from datetime import datetime
from api.auth import fetch_token_with_retry

logging.basicConfig(level=logging.INFO)

def get_active_offers(account, limit=50):
    """
    Fetch all active offers using the /offer/all endpoint for the given account.
    Saves the active offers to a JSON file and a CSV file per account.
    """
    access_token = fetch_token_with_retry(account)
    if not access_token:
        logging.error(f"❌ Failed to get access token for {account['name']}.")
        return []

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    base_url = account.get("offers_url")
    if not base_url:
        logging.error("❌ No offers_url specified in account config.")
        return []

    all_offers = []
    offset = 0

    while True:
        payload = {
            "type": "sell",  # Change to "buy" if you want buy offers instead
            "currency_code": "MXN",
            "crypto_currency_code": "BTC",
            "limit": limit,
            "offset": offset,
            "verified_only": True,
            "user_country_iso": "WORLDWIDE",
            "visitor_country_iso": "WORLDWIDE"
        }

        try:
            response = requests.post(base_url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json()

            offers = data.get("data", {}).get("offers", [])
            total = data.get("data", {}).get("totalCount", 0)

            active_offers = [offer for offer in offers if offer.get("active") is True]
            logging.info(f"✅ Fetched {len(active_offers)} active offers (offset {offset}) for {account['name']}")

            all_offers.extend(active_offers)
            offset += limit

            if offset >= total:
                break

        except requests.RequestException as e:
            logging.error(f"❌ Error fetching offers for {account['name']}: {e}")
            break

    # Save active offers to JSON and CSV
    if all_offers:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON file
        json_filename = f"{account['name'].lower()}_offers_{timestamp}.json"
        output_dir = "offer_snapshots"
        os.makedirs(output_dir, exist_ok=True)
        json_filepath = os.path.join(output_dir, json_filename)
        
        with open(json_filepath, "w") as f:
            json.dump(all_offers, f, indent=2)
        logging.info(f"📁 Saved {len(all_offers)} offers to {json_filepath}")

        # Save CSV file
        csv_filename = f"{account['name'].lower()}_offers_{timestamp}.csv"
        csv_filepath = os.path.join(output_dir, csv_filename)

        # Prepare CSV fieldnames (columns)
        fields = [
            "offer_id", "offer_link", "offer_type", "payment_window", "currency_code",
            "fiat_currency_code", "crypto_currency_code", "fiat_price_per_btc", "payment_method_name",
            "offer_owner_username", "offer_owner_profile_link", "offer_owner_feedback_positive",
            "offer_owner_feedback_negative", "seller_fee", "fee_percentage", "margin", "is_blocked"
        ]

        # Write to CSV
        with open(csv_filepath, mode="w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)
            writer.writeheader()  # Write header
            for offer in all_offers:
                # Extract relevant data for CSV
                offer_data = {
                    "offer_id": offer.get("offer_id"),
                    "offer_link": offer.get("offer_link"),
                    "offer_type": offer.get("offer_type"),
                    "payment_window": offer.get("payment_window"),
                    "currency_code": offer.get("currency_code"),
                    "fiat_currency_code": offer.get("fiat_currency_code"),
                    "crypto_currency_code": offer.get("crypto_currency_code"),
                    "fiat_price_per_btc": offer.get("fiat_price_per_btc"),
                    "payment_method_name": offer.get("payment_method_name"),
                    "offer_owner_username": offer.get("offer_owner_username"),
                    "offer_owner_profile_link": offer.get("offer_owner_profile_link"),
                    "offer_owner_feedback_positive": offer.get("offer_owner_feedback_positive"),
                    "offer_owner_feedback_negative": offer.get("offer_owner_feedback_negative"),
                    "seller_fee": offer.get("seller_fee"),
                    "fee_percentage": offer.get("fee_percentage"),
                    "margin": offer.get("margin"),
                    "is_blocked": offer.get("is_blocked")
                }
                writer.writerow(offer_data)

        logging.info(f"📁 Saved {len(all_offers)} offers to {csv_filepath}")

    return all_offers
