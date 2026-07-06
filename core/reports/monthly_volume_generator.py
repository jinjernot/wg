import sys
import os
import json
import logging
import certifi
import calendar
from datetime import datetime, timezone
from dateutil import parser as date_parser

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.api.auth import fetch_token_with_retry
from config import PLATFORM_ACCOUNTS, TRADE_COMPLETED_URL_NOONES, TRADES_STORAGE_DIR, REPORTS_DIR
from core.api.offers import get_all_offers
from core.utils.http_client import get_http_client
from core.messaging.alerts.telegram_alert import escape_markdown

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def fetch_completed_trades_for_period(account, start_utc):
    token = fetch_token_with_retry(account)
    if not token:
        print(f"Failed to fetch auth token for {account['name']}")
        return []
        
    headers = {
        "Accept": "application/json; version=1",
        "Authorization": f"Bearer {token}"
    }
    
    http_client = get_http_client()
    all_trades = []
    
    for page in range(1, 15):  # Fetch up to 15 pages (1500 trades)
        data = {
            "page": page,
            "limit": 100
        }
        try:
            res = http_client.post(
                TRADE_COMPLETED_URL_NOONES,
                headers=headers,
                data=data,
                verify=certifi.where(),
                timeout=15
            )
            if res.status_code == 200:
                res_data = res.json()
                if res_data.get("status") == "success" and res_data["data"].get("trades"):
                    trades = res_data["data"]["trades"]
                    all_trades.extend(trades)
                    
                    last_trade = trades[-1]
                    last_trade_date_str = last_trade.get("completed_at") or last_trade.get("ended_at")
                    if last_trade_date_str:
                        try:
                            last_trade_date = date_parser.isoparse(last_trade_date_str.replace("Z", "+00:00"))
                            if last_trade_date.tzinfo is None:
                                last_trade_date = last_trade_date.replace(tzinfo=timezone.utc)
                            if last_trade_date < start_utc:
                                break
                        except:
                            pass
                            
                    if len(trades) < 100:
                        break
                else:
                    break
            else:
                break
        except Exception as e:
            break
            
    return all_trades

def run_monthly_report():
    # Parse inputs (default to current month)
    now = datetime.now(timezone.utc)
    if len(sys.argv) >= 3:
        try:
            target_year = int(sys.argv[1])
            target_month = int(sys.argv[2])
        except ValueError:
            print("Invalid arguments. Usage: python monthly_volume_generator.py <year> <month>")
            return
    else:
        target_year = now.year
        target_month = now.month
        
    start_date = datetime(target_year, target_month, 1, tzinfo=timezone.utc)
    last_day = calendar.monthrange(target_year, target_month)[1]
    end_date = datetime(target_year, target_month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    
    print(f"Generating Split Report for: {start_date.strftime('%B %Y')}")
    
    # 1. Fetch live offers mapping
    live_offers = get_all_offers()
    offer_map = {}
    if live_offers:
        for offer in live_offers:
            ohash = offer.get("offer_id") or offer.get("offer_hash")
            if ohash:
                offer_map[ohash] = {
                    "margin": offer.get("margin"),
                    "payment_method": offer.get("payment_method_slug"),
                    "payment_name": offer.get("payment_method_name")
                }
                
    # 2. Load Local Trade Cache Fallback
    local_trades = {}
    for fname in ["JoeWillgang_Noones.json", "davidvs_Noones.json"]:
        fpath = os.path.join(TRADES_STORAGE_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    local_trades.update(json.load(f))
            except:
                pass
                
    # 3. Fetch completed trades from API
    all_completed = []
    for account in PLATFORM_ACCOUNTS:
        trades = fetch_completed_trades_for_period(account, start_date)
        owner = account['name'].split("_")[0]
        for t in trades:
            t["owner_username"] = owner
            all_completed.append(t)
            
    if not all_completed:
        print("No completed trades found.")
        return
        
    first_half_trades = []
    second_half_trades = []
    first_half_groups = {}
    second_half_groups = {}
    
    for trade in all_completed:
        status = str(trade.get("trade_status") or trade.get("status")).lower()
        if status not in ["released", "successful", "successful / released"]:
            continue
            
        completed_at_str = trade.get("completed_at") or trade.get("ended_at")
        if not completed_at_str:
            continue
            
        try:
            completed_at = date_parser.isoparse(completed_at_str.replace("Z", "+00:00"))
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
        except:
            continue
            
        if completed_at < start_date or completed_at > end_date:
            continue
            
        trade_hash = trade.get("trade_hash")
        offer_hash = trade.get("offer_hash")
        
        margin = 0.0
        payment_method = "unknown"
        resolved_method_name = trade.get("payment_method_name") or "Unknown Method"
        
        if trade_hash in local_trades:
            margin = float(local_trades[trade_hash].get("margin", 0.0))
            payment_method = local_trades[trade_hash].get("payment_method_slug") or "unknown"
            resolved_method_name = local_trades[trade_hash].get("payment_method_name") or resolved_method_name
        elif offer_hash in offer_map:
            margin = float(offer_map[offer_hash]["margin"] or 0.0)
            payment_method = offer_map[offer_hash]["payment_method"] or "unknown"
            resolved_method_name = offer_map[offer_hash]["payment_name"] or resolved_method_name
        else:
            payment_method = trade.get("payment_method_name") or "unknown"
            
        if margin == 0.0:
            if "spei" in str(payment_method).lower() or "spei" in resolved_method_name.lower():
                margin = 12.0
                payment_method = "spei-sistema-de-pagos-electronicos-interbancarios"
            elif "bank" in str(payment_method).lower() or "transferencia" in resolved_method_name.lower():
                margin = 11.0
                payment_method = "bank-transfer"
            elif "oxxo" in str(payment_method).lower():
                margin = 13.0
                payment_method = "oxxo"
            elif "amazon" in str(payment_method).lower():
                margin = 88.8
                payment_method = "amazon-gift-card"
                
        crypto = trade.get("crypto_currency_code", "BTC")
        fiat = trade.get("fiat_currency_code", "MXN")
        volume = float(trade.get("fiat_amount_requested") or trade.get("fiat_amount") or 0.0)
        owner = trade.get("owner_username")
        
        trade_entry = {
            "trade_hash": trade_hash,
            "owner": owner,
            "crypto": crypto,
            "payment_name": resolved_method_name,
            "fiat": fiat,
            "margin": margin,
            "volume": volume,
            "completed_at": completed_at
        }
        
        key = (crypto, resolved_method_name, margin, fiat)
        
        if completed_at.day <= 15:
            first_half_trades.append(trade_entry)
            if key not in first_half_groups:
                first_half_groups[key] = []
            first_half_groups[key].append(volume)
        else:
            second_half_trades.append(trade_entry)
            if key not in second_half_groups:
                second_half_groups[key] = []
            second_half_groups[key].append(volume)
            
    # Format markdown
    md = []
    md.append(f"# Monthly Volume Report: {start_date.strftime('%B %Y')}")
    md.append(f"**Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n")
    
    # Section 1
    md.append(f"## 📅 Period 1: Days 1 to 15 ({start_date.strftime('%B')} 1 - 15)")
    md.append(f"Total successful trades in this period: **{len(first_half_trades)}**\n")
    if not first_half_trades:
        md.append("_No successful trades recorded in this period._\n")
    else:
        md.append("| Crypto | Payment Method | Margin % | Trades Count | Total Volume (Fiat) |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")
        first_grand_totals = {}
        for key in sorted(first_half_groups.keys(), key=lambda x: (x[0], x[1], x[2])):
            crypto, pm_name, margin, fiat = key
            vols = first_half_groups[key]
            total_vol = sum(vols)
            first_grand_totals[fiat] = first_grand_totals.get(fiat, 0.0) + total_vol
            md.append(f"| {crypto} | `{pm_name}` | **{margin}%** | {len(vols)} | {total_vol:,.2f} {fiat} |")
        md.append("\n**Period 1 Totals:**")
        for fiat, vol in first_grand_totals.items():
            md.append(f"- Total {fiat} Volume: `{vol:,.2f} {fiat}`")
            
    md.append("\n" + "---" * 10 + "\n")
    
    # Section 2
    md.append(f"## 📅 Period 2: Days 16 to End (Days 16 - {last_day})")
    md.append(f"Total successful trades in this period: **{len(second_half_trades)}**\n")
    if not second_half_trades:
        md.append("_No successful trades recorded in this period._\n")
    else:
        md.append("| Crypto | Payment Method | Margin % | Trades Count | Total Volume (Fiat) |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")
        second_grand_totals = {}
        for key in sorted(second_half_groups.keys(), key=lambda x: (x[0], x[1], x[2])):
            crypto, pm_name, margin, fiat = key
            vols = second_half_groups[key]
            total_vol = sum(vols)
            second_grand_totals[fiat] = second_grand_totals.get(fiat, 0.0) + total_vol
            md.append(f"| {crypto} | `{pm_name}` | **{margin}%** | {len(vols)} | {total_vol:,.2f} {fiat} |")
        md.append("\n**Period 2 Totals:**")
        for fiat, vol in second_grand_totals.items():
            md.append(f"- Total {fiat} Volume: `{vol:,.2f} {fiat}`")
            
    # Save Report
    report_filename = REPORTS_DIR / f"monthly_volume_report_{target_year}_{target_month:02d}.md"
    with open(report_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print(f"Success! Report saved to: {report_filename}")

if __name__ == "__main__":
    run_monthly_report()
