from core.get_active_offers import get_active_offers
from config import ACCOUNTS_OFFERS

def main():
    for account in ACCOUNTS_OFFERS:
        print(f"🔍 Fetching active offers for {account['name']}...")
        active_offers = get_active_offers(account)
        
        if not active_offers:
            print(f"⚠️  No active offers found for {account['name']}.")
            continue

        for offer in active_offers:
            print(f"✅ Offer ID: {offer['offer_id']}")
            print(f"   ↳ Method: {offer['payment_method_name']}")
            print(f"   ↳ Margin: {offer.get('margin', 'N/A')}%")
            print(f"   ↳ Link: {offer.get('offer_link', 'N/A')}")
            print("")

if __name__ == "__main__":
    main()
