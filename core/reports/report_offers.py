import json
import os
from core.get_active_offers import get_active_offers
from config import ACCOUNTS_OFFERS

OUTPUT_DIR = "sorted_offers"

def save_sorted_offers_by_margin(offers, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sorted_offers = sorted(offers, key=lambda offer: offer.get("margin", 0), reverse=True)
    path = os.path.join(OUTPUT_DIR, filename)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sorted_offers, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved sorted offers to {path}")
    except Exception as e:
        print(f"❌ Error saving offers to {path}: {e}")

def main():
    for account in ACCOUNTS_OFFERS:
        print(f"\nFetching active offers for {account['name']}...")
        active_offers = get_active_offers(account)
        
        if not active_offers:
            print(f"No active offers found for {account['name']}.")
            continue

        for offer in active_offers:
            print(f"Offer ID: {offer['offer_id']}")
            print(f"   ↳ Method: {offer['payment_method_name']}")
            print(f"   ↳ Margin: {offer.get('margin', 'N/A')}%")
            print(f"   ↳ Link: {offer.get('offer_link', 'N/A')}")
            print("")

        filename = f"{account['name'].lower().replace(' ', '_')}_sorted_offers.json"
        save_sorted_offers_by_margin(active_offers, filename)

if __name__ == "__main__":
    main()
