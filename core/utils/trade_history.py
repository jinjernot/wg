import matplotlib
matplotlib.use('Agg')
import requests
import logging
import threading
import pytz
import os
import csv
import json
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse
from threading import Lock

import matplotlib.pyplot as plt
from collections import Counter, defaultdict
import pandas as pd

from core.api.auth import fetch_token_with_retry
from config import ACCOUNTS, TRADE_COMPLETED_URL_NOONES, TRADE_COMPLETED_URL_PAXFUL, TRADE_HISTORY

# Silence urllib3 connection logs
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.basicConfig(level=logging.DEBUG)

ALL_TRADES = []
LOCK = Lock()


def fetch_completed_trades(account, limit=1000):
    platform = "Paxful" if "_Paxful" in account["name"] else "Noones"
    base_url = TRADE_COMPLETED_URL_PAXFUL if platform == "Paxful" else TRADE_COMPLETED_URL_NOONES

    token = fetch_token_with_retry(account)
    if not token:
        logging.error(f"{account['name']}: could not fetch token.")
        return

    headers = {"Authorization": f"Bearer {token}"}
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=150)

    logging.debug(f"Cutoff date: {cutoff_date}")

    collected = []
    page = 1
    total = None

    while True:
        payload = {
            "limit": limit,
            "page": page,
        }

        try:
            resp = requests.post(base_url, headers=headers, data=payload, timeout=30)
            resp.raise_for_status()
            json_data = resp.json()
            logging.debug(f"{account['name']} - page {page}: {json_data}")
            save_raw_json_response(account, json_data)
        except Exception as e:
            logging.error(f"{account['name']}: error fetching page {page}: {e}")
            break

        data = json_data.get("data", {})
        trades = data.get("trades", [])
        if total is None:
            total = data.get("count", 0)

        if not trades:
            logging.debug(f"{account['name']}: no trades found on page {page}.")
            break

        for t in trades:
            if t.get("completed_at") is not None:
                normalized = normalize_trade(t, account["name"])
                collected.append(normalized)

        page += 1
        if page * limit >= total:
            logging.debug(f"Finished fetching all trades, reached total count: {total}")
            break

    logging.info(f"{account['name']}: collected {len(collected)} trades in last 150 days.")

    save_normalized_trades(account, collected)
    save_trades_csv(account, collected)

    with LOCK:
        ALL_TRADES.extend(collected)

def normalize_trade(trade, account_name):
    def safe_float(value):
        try:
            if isinstance(value, str) and value.upper() == "N/A":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    def safe_str(value):
        return value if value and value != "N/A" else None

    return {
        "account_name": account_name,
        "trade_hash": trade.get("trade_hash"),
        "offer_hash": trade.get("offer_hash"),
        "payment_method_name": safe_str(trade.get("payment_method_name")),
        "seller": safe_str(trade.get("seller")),
        "buyer": safe_str(trade.get("buyer")),
        "offer_type": trade.get("offer_type"),
        "status": trade.get("status"),
        "fiat_amount_requested": safe_float(trade.get("fiat_amount_requested")),
        "crypto_amount_requested": safe_float(trade.get("crypto_amount_requested")),
        "fiat_currency_code": trade.get("fiat_currency_code"),
        "crypto_currency_code": trade.get("crypto_currency_code"),
        "started_at": trade.get("started_at"),
        "ended_at": trade.get("ended_at"),
        "completed_at": trade.get("completed_at"),
    }


def save_raw_json_response(account, raw_data):
    os.makedirs(TRADE_HISTORY, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    fname = f"{account['name'].lower()}_raw_trades_{date_str}.json"
    path = os.path.join(TRADE_HISTORY, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved raw JSON response for {account['name']} to {path}")


def save_normalized_trades(account, trades):
    os.makedirs(TRADE_HISTORY, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    fname = f"{account['name'].lower()}_normalized_trades_{date_str}.json"
    path = os.path.join(TRADE_HISTORY, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)
    logging.info(f"Saved normalized trades for {account['name']} to {path}")


def save_trades_csv(account, trades):
    os.makedirs(TRADE_HISTORY, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    fname = f"{account['name'].lower()}_normalized_trades_{date_str}.csv"
    path = os.path.join(TRADE_HISTORY, fname)

    if not trades:
        logging.info(f"No trades to save to CSV for {account['name']}")
        return

    excluded_fields = {"trade_status", "location_iso", "seller_avatar_url", "buyer_avatar_url"}
    fieldnames = [key for key in trades[0].keys() if key not in excluded_fields]

    try:
        with open(path, mode="w", encoding="utf-8", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in trades:
                filtered_row = {k: v for k, v in row.items() if k in fieldnames}
                writer.writerow(filtered_row)
        logging.info(f"Saved filtered CSV trades for {account['name']} to {path}")
    except Exception as e:
        logging.error(f"Error saving CSV for {account['name']}: {e}")


def plot_successful_trades_per_account(all_trades, output_path):
    account_success_counts = {}
    for trade in all_trades:
        if trade['status'] == 'successful':
            account_name = trade['account_name']
            account_success_counts[account_name] = account_success_counts.get(account_name, 0) + 1

    accounts = list(account_success_counts.keys())
    success_counts = list(account_success_counts.values())

    plt.figure(figsize=(10, 6))
    plt.bar(accounts, success_counts, color='green')
    plt.title("Trades por plataforma")
    plt.xlabel("Cuentas")
    plt.ylabel("Número de trades armados")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_top_10_buyers(all_trades, output_path):
    buyer_counts = Counter()
    for trade in all_trades:
        if trade['status'] == 'successful':
            buyer = trade.get("buyer")
            if buyer:
                buyer_counts[buyer] += 1

    top_buyers = buyer_counts.most_common(10)
    if not top_buyers:
        logging.info("No buyers found for plotting.")
        return

    buyers = [buyer for buyer, count in top_buyers]
    counts = [count for _, count in top_buyers]

    plt.figure(figsize=(12, 6))
    plt.bar(buyers, counts, color='green')
    plt.title("Top 10 Negros rifados")
    plt.xlabel("Negros")
    plt.ylabel("Número de trades")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_crypto_currency_distribution(all_trades, output_path):
    from collections import defaultdict

    account_crypto_counts = defaultdict(lambda: defaultdict(int))

    for trade in all_trades:
        if trade['status'] == 'successful':
            account = trade.get("account_name")
            crypto = trade.get("crypto_currency_code")
            if account and crypto:
                account_crypto_counts[account][crypto] += 1

    accounts = list(account_crypto_counts.keys())
    cryptos = list({crypto for sub in account_crypto_counts.values() for crypto in sub})
    data = [[account_crypto_counts[acc].get(crypto, 0) for acc in accounts] for crypto in cryptos]

    plt.figure(figsize=(12, 7))
    bottom = [0] * len(accounts)

    for i, crypto_counts in enumerate(data):
        plt.bar(accounts, crypto_counts, label=cryptos[i], bottom=bottom)
        bottom = [sum(x) for x in zip(bottom, crypto_counts)]

    plt.title("Distribución de trades por cuenta y crypto")
    plt.xlabel("Cuentas")
    plt.ylabel("Número de trades")
    plt.xticks(rotation=45)
    plt.legend(title="Criptomoneda")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def plot_trades_by_payment_method(all_trades, output_path):
    """Generates a stacked bar chart of trades by payment method and account."""
    if not all_trades:
        logging.info("No trade data for payment method chart.")
        return

    # Use a DataFrame for easier manipulation
    df = pd.DataFrame(all_trades)
    successful_trades = df[df['status'] == 'successful']

    if successful_trades.empty:
        logging.info("No successful trades for payment method chart.")
        return

    # Group by payment method and account, then count the trades
    trade_counts = successful_trades.groupby(['payment_method_name', 'account_name']).size().unstack(fill_value=0)

    if trade_counts.empty:
        logging.info("No data to plot for payment methods.")
        return

    # Create the stacked bar chart
    ax = trade_counts.plot(kind='bar', stacked=True, figsize=(14, 8), colormap='viridis')

    plt.title("Trades por Método de Pago y Cuenta")
    plt.xlabel("Método de Pago")
    plt.ylabel("Número de Trades")
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="Cuenta")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def save_all_trades_csv(trades, output_dir):
    if not trades:
        logging.info("No combined trades to save.")
        return

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    fname = f"all_accounts_trades_{date_str}.csv"
    path = os.path.join(output_dir, fname)

    fieldnames = trades[0].keys()
    try:
        with open(path, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(trades)
        logging.info(f"Saved all trades (combined CSV) to {path}")
    except Exception as e:
        logging.error(f"Error saving combined CSV: {e}")


def plot_trades_per_time_of_day(all_trades, output_path):
    from collections import Counter
    
    time_of_day_counts = Counter()
    mexico_tz = pytz.timezone('America/Mexico_City')

    for trade in all_trades:
        if trade['status'] == 'successful':
            started_at = trade.get("started_at")
            if started_at:
                try:
                    # The timestamps from the API are not in ISO 8601 format
                    # so we need to parse them differently.
                    dt = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                    dt_utc = dt.replace(tzinfo=timezone.utc)
                    dt_mexico = dt_utc.astimezone(mexico_tz)
                    hour = dt_mexico.hour
                    time_of_day_counts[hour] += 1
                except Exception as e:
                    logging.warning(f"Invalid started_at date: {started_at} -> {e}")

    if not time_of_day_counts:
        logging.info("No valid started_at dates for plotting trades per time of day.")
        return

    hours = list(range(24))
    counts = [time_of_day_counts.get(hour, 0) for hour in hours]

    plt.figure(figsize=(10, 6))
    plt.bar(hours, counts, color='green')
    plt.title("Número de trades por hora del día")
    plt.xlabel("Hora del día")
    plt.ylabel("Número de trades")
    plt.xticks(hours)
    plt.grid(True, axis='y')
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def main():
    threads = []
    for account in ACCOUNTS:
        thread = threading.Thread(target=fetch_completed_trades, args=(account,))
        thread.start()
        threads.append(thread)

    for t in threads:
        t.join()

    logging.info(f"Fetched {len(ALL_TRADES)} total trades.")

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=150)

    filtered_trades = [
        trade for trade in ALL_TRADES
        if trade['completed_at'] and
        isoparse(trade['completed_at']).replace(tzinfo=timezone.utc) > cutoff_date and
        trade['status'] == 'successful'
    ]

    logging.info(f"Filtered to {len(filtered_trades)} successful trades from the last 150 days.")

    date_folder = datetime.now().strftime('%Y-%m-%d')
    output_dir = os.path.join(TRADE_HISTORY, date_folder)
    os.makedirs(output_dir, exist_ok=True)
    
    plot_paths = {
        "trades_per_account": os.path.join(output_dir, "trades_per_account.png"),
        "top_10_buyers": os.path.join(output_dir, "top_10_buyers.png"),
        "crypto_distribution": os.path.join(output_dir, "crypto_distribution.png"),
        "trades_per_time": os.path.join(output_dir, "trades_per_time.png"),
        "trades_by_payment_method": os.path.join(output_dir, "trades_by_payment_method.png")
    }

    plot_trades_per_time_of_day(filtered_trades, plot_paths["trades_per_time"])
    plot_successful_trades_per_account(filtered_trades, plot_paths["trades_per_account"])
    plot_top_10_buyers(filtered_trades, plot_paths["top_10_buyers"])
    plot_crypto_currency_distribution(filtered_trades, plot_paths["crypto_distribution"])
    plot_trades_by_payment_method(filtered_trades, plot_paths["trades_by_payment_method"])

    save_all_trades_csv(filtered_trades, output_dir)

    return plot_paths

if __name__ == "__main__":
    main()