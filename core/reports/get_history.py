import requests
import csv
import logging
import threading
import os
from datetime import datetime, timezone
from dateutil.parser import isoparse

from api.auth import fetch_token_with_retry
from config import ACCOUNTS, GET_TRADE_URL_NOONES, GET_TRADE_URL_PAXFUL, TRADE_HISTORY

# Silence urllib3 connection logs
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)

def get_all_trades_for_today(account, limit=100):
    """
    Fetch every trade (regardless of status) and collect those
    whose started_at or completed_at is today.
    """
    # pick the right endpoint
    platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
    base_url = GET_TRADE_URL_PAXFUL if platform == "Paxful" else GET_TRADE_URL_NOONES

    token = fetch_token_with_retry(account)
    if not token:
        logging.error(f"{account['name']}: could not fetch token.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    today = datetime.now(timezone.utc).date()

    collected = []
    offset = 0
    total = None

    while True:
        payload = {
            "limit": limit,
            "offset": offset,
            "status": "all"            # ask for every status
        }

        try:
            resp = requests.post(base_url, headers=headers, data=payload, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logging.error(f"{account['name']}: error fetching offset {offset}: {e}")
            break

        data = resp.json().get("data", {})
        trades = data.get("trades", [])
        if total is None:
            total = data.get("totalCount", 0)

        if not trades:
            break

        for t in trades:
            # parse both dates
            added = False
            for field in ("started_at", "completed_at"):
                dt_str = t.get(field)
                if dt_str:
                    try:
                        if isoparse(dt_str).date() == today:
                            collected.append(t)
                            added = True
                            break
                    except Exception:
                        pass
            # (no early exit — we need to see all trades to catch completed‑today ones)

        offset += limit
        if total is not None and offset >= total:
            break

    if not collected:
        logging.info(f"{account['name']}: no trades for today.")
        return

    # write CSV
    
    os.makedirs(TRADE_HISTORY, exist_ok=True)
    date_str = today.strftime("%Y%m%d")
    fname = f"{account['name'].lower()}_trades_{date_str}.csv"
    path = os.path.join(TRADE_HISTORY, fname)

    csv_headers = [
        "Trade Status", "Trade Hash", "Offer Hash", "Location", "Fiat Amount Requested",
        "Payment Method", "Crypto Amount Requested", "Started At", "Seller", "Buyer",
        "Fiat Currency", "Ended At", "Completed At", "Offer Type", "Seller Avatar URL",
        "Buyer Avatar URL", "Status", "Crypto Currency"
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        for t in collected:
            writer.writerow([
                t.get("trade_status", "N/A"),
                t.get("trade_hash", "N/A"),
                t.get("offer_hash", "N/A"),
                t.get("location_iso", "N/A"),
                t.get("fiat_amount_requested", "N/A"),
                t.get("payment_method_name", "N/A"),
                t.get("crypto_amount_requested", "N/A"),
                t.get("started_at", "N/A"),
                t.get("seller", "N/A"),
                t.get("buyer", "N/A"),
                t.get("fiat_currency_code", "N/A"),
                t.get("ended_at", "N/A"),
                t.get("completed_at", "N/A"),
                t.get("offer_type", "N/A"),
                t.get("seller_avatar_url", "N/A"),
                t.get("buyer_avatar_url", "N/A"),
                t.get("status", "N/A"),
                t.get("crypto_currency_code", "N/A"),
            ])

    logging.info(f"✅ Saved {len(collected)} trades for today to {path}")


if __name__ == "__main__":
    threads = []
    for acct in ACCOUNTS:
        t = threading.Thread(target=get_all_trades_for_today, args=(acct,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
