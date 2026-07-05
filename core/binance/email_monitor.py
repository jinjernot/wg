"""
Binance P2P Gmail Notification Monitor
Periodically polls Gmail accounts for emails from Binance and sends alerts.
"""

import os
import json
import logging
import glob
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import pytz

from config import (
    BINANCE_EMAIL_ALERTS_ENABLED,
    BINANCE_MONITORED_GMAIL_ACCOUNTS,
    BINANCE_EMAIL_SEARCH_QUERY,
    BINANCE_PROCESSED_EMAILS_FILE,
    GMAIL_CREDENTIALS_DIR
)
from core.validation.email import get_gmail_service, get_email_body
from core.messaging.alerts.telegram_alert import send_binance_email_alert as send_tg
from core.messaging.alerts.discord_alert import send_binance_email_alert as send_ds

logger = logging.getLogger(__name__)

def load_processed_emails() -> dict:
    """Loads the set of processed Gmail message IDs and recent history from state file."""
    if os.path.exists(BINANCE_PROCESSED_EMAILS_FILE):
        try:
            with open(BINANCE_PROCESSED_EMAILS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "processed_ids" not in data:
                        data["processed_ids"] = {}
                    if "recent_alerts" not in data:
                        data["recent_alerts"] = []
                    if "pending_binance_orders" not in data:
                        data["pending_binance_orders"] = []
                    if "pending_banorte_deposits" not in data:
                        data["pending_banorte_deposits"] = []
                    return data
        except Exception as e:
            logger.error(f"Failed to load processed Binance emails state: {e}")
    return {
        "processed_ids": {},
        "recent_alerts": [],
        "pending_binance_orders": [],
        "pending_banorte_deposits": []
    }

def save_processed_emails(state: dict):
    """Saves the processed state dict containing message IDs and history."""
    try:
        os.makedirs(os.path.dirname(BINANCE_PROCESSED_EMAILS_FILE), exist_ok=True)
        with open(BINANCE_PROCESSED_EMAILS_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save processed Binance emails state: {e}")

def prune_old_entries(state: dict, max_age_days: int = 14):
    """Removes processed email IDs and pending matches older than max_age_days/24 hours."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    
    # Prune processed_ids
    processed_ids = state.get("processed_ids", {})
    keys_to_delete = []
    for msg_id, timestamp_str in processed_ids.items():
        try:
            ts = datetime.fromisoformat(timestamp_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                keys_to_delete.append(msg_id)
        except Exception:
            keys_to_delete.append(msg_id)
            
    for key in keys_to_delete:
        del processed_ids[key]
        
    if keys_to_delete:
        logger.info(f"Pruned {len(keys_to_delete)} old/corrupted message ID entries from state.")
        
    # Prune pending binance orders older than 24 hours
    pending_binance = state.get("pending_binance_orders", [])
    pruned_binance = []
    cutoff_pending = now - timedelta(hours=24)
    for order in pending_binance:
        try:
            ts = datetime.fromisoformat(order["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts.astimezone(timezone.utc) >= cutoff_pending:
                pruned_binance.append(order)
        except Exception:
            pass
    state["pending_binance_orders"] = pruned_binance
    
    # Prune pending banorte deposits older than 24 hours
    pending_banorte = state.get("pending_banorte_deposits", [])
    pruned_banorte = []
    for dep in pending_banorte:
        try:
            ts = datetime.fromisoformat(dep["timestamp"])
            if ts.tzinfo is None:
                ts = pytz.timezone('America/Mexico_City').localize(ts)
            if ts.astimezone(timezone.utc) >= cutoff_pending:
                pruned_banorte.append(dep)
        except Exception:
            pass
    state["pending_banorte_deposits"] = pruned_banorte

def parse_banorte_email(html_body):
    """Parses Banorte HTML email to extract transaction details."""
    try:
        soup = BeautifulSoup(html_body, 'html.parser')
        text = soup.get_text()
        
        amount = None
        tds = soup.find_all('td')
        for i, td in enumerate(tds):
            td_text = td.get_text(strip=True)
            if td_text == "Importe:":
                if i + 1 < len(tds):
                    amount_str = tds[i+1].get_text(strip=True)
                    match = re.search(r'\$?([\d,]+\.\d{2})', amount_str)
                    if match:
                        amount = float(match.group(1).replace(',', ''))
                        break
                        
        if amount is None:
            importe_match = re.search(r'Importe:\s*\$?\s*([\d,]+\.\d{2})', text)
            if importe_match:
                amount = float(importe_match.group(1).replace(',', ''))
        
        op_date = None
        op_time = None
        for i, td in enumerate(tds):
            td_text = td.get_text(strip=True)
            if td_text == "Fecha de Operacion:":
                if i + 1 < len(tds):
                    op_date = tds[i+1].get_text(strip=True)
            elif td_text == "Hora de Operacion:":
                if i + 1 < len(tds):
                    op_time = tds[i+1].get_text(strip=True).replace("horas", "").strip()
        
        name = None
        name_match = re.search(r'Estimado\(a\):\s*\n*([^\n<]+)', html_body)
        if name_match:
            name = name_match.group(1).strip()
        else:
            name_match_text = re.search(r'Estimado\(a\):\s*([^\n]+)', text)
            if name_match_text:
                name = name_match_text.group(1).strip()
                
        op_id = None
        for i, td in enumerate(tds):
            td_text = td.get_text(strip=True)
            if td_text == "Operacion:":
                if i + 1 < len(tds):
                    op_id = tds[i+1].get_text(strip=True)
                    
        timestamp = None
        if op_date and op_time:
            months_map = {
                'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr', 'may': 'May', 'jun': 'Jun',
                'jul': 'Jul', 'ago': 'Aug', 'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
            }
            parts = op_date.split('/')
            if len(parts) == 3:
                month_es = parts[1].lower()[:3]
                month_en = months_map.get(month_es, parts[1])
                date_en = f"{parts[0]}/{month_en}/{parts[2]}"
                dt_str = f"{date_en} {op_time}"
                try:
                    local_tz = pytz.timezone('America/Mexico_City')
                    naive_dt = datetime.strptime(dt_str, "%d/%b/%Y %H:%M:%S")
                    timestamp = local_tz.localize(naive_dt)
                except Exception as e:
                    logger.error(f"Error parsing date/time for Banorte: {e}")
                    
        return {
            "amount": amount,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "name": name,
            "operation_id": op_id
        }
    except Exception as e:
        logger.error(f"Error parsing Banorte email: {e}")
        return None

def parse_binance_email(html_body, subject=""):
    """Parses Binance HTML email to extract P2P transaction details."""
    try:
        soup = BeautifulSoup(html_body, 'html.parser')
        text = soup.get_text()
        
        amount = None
        binance_amount_match = re.search(r'in the amount of\s*Mex\$\s*([\d,]+\.?\d*)', text)
        if binance_amount_match:
            amount = float(binance_amount_match.group(1).rstrip('.'))
            
        order_number = None
        order_match = re.search(r'order number:\s*(\d+)', text, re.IGNORECASE)
        if order_match:
            order_number = order_match.group(1)
        elif subject:
            subject_match = re.search(r'Order\s*(\d+)', subject, re.IGNORECASE)
            if subject_match:
                order_number = subject_match.group(1)
                
        order_time = None
        if subject:
            time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*\(UTC\)', subject)
            if time_match:
                try:
                    naive_dt = datetime.strptime(time_match.group(1), "%Y-%m-%d %H:%M:%S")
                    order_time = naive_dt.replace(tzinfo=timezone.utc)
                except Exception as e:
                    logger.error(f"Error parsing time from Binance subject: {e}")
                    
        return {
            "amount": amount,
            "order_number": order_number,
            "timestamp": order_time.isoformat() if order_time else None
        }
    except Exception as e:
        logger.error(f"Error parsing Binance email: {e}")
        return None

def check_and_match_payments(state):
    """
    Checks the pending lists for matches.
    If a match is found, removes it from both pending lists, calls alert functions, and returns True.
    """
    pending_binance = state.get("pending_binance_orders", [])
    pending_banorte = state.get("pending_banorte_deposits", [])
    
    matched_binance_idx = -1
    matched_banorte_idx = -1
    smallest_diff = float('inf')
    
    for i, bin_order in enumerate(pending_binance):
        for j, ban_dep in enumerate(pending_banorte):
            try:
                bin_amt = float(bin_order["amount"])
                ban_amt = float(ban_dep["amount"])
            except (ValueError, TypeError, KeyError):
                continue
                
            if abs(bin_amt - ban_amt) >= 0.01:
                continue
                
            try:
                bin_dt = datetime.fromisoformat(bin_order["timestamp"])
                ban_dt = datetime.fromisoformat(ban_dep["timestamp"])
                
                if bin_dt.tzinfo is None:
                    bin_dt = bin_dt.replace(tzinfo=timezone.utc)
                if ban_dt.tzinfo is None:
                    ban_dt = pytz.timezone('America/Mexico_City').localize(ban_dt)
                    
                bin_dt_utc = bin_dt.astimezone(timezone.utc)
                ban_dt_utc = ban_dt.astimezone(timezone.utc)
                
                diff = abs((bin_dt_utc - ban_dt_utc).total_seconds())
                if diff <= 1800:  # 30 minutes
                    if diff < smallest_diff:
                        smallest_diff = diff
                        matched_binance_idx = i
                        matched_banorte_idx = j
            except Exception as e:
                logger.error(f"Error comparing timestamps in match logic: {e}")
                continue
                
    if matched_binance_idx != -1 and matched_banorte_idx != -1:
        bin_order = pending_binance.pop(matched_binance_idx)
        ban_dep = pending_banorte.pop(matched_banorte_idx)
        
        mins = int(smallest_diff // 60)
        secs = int(smallest_diff % 60)
        time_diff_str = f"{mins}m {secs}s"
        
        logger.info(f"🎉 SUCCESSFUL PAYMENT MATCH FOUND: Binance Order {bin_order['order_number']} matched Banorte Deposit of {ban_dep['name']}. Amount: {bin_order['amount']}. Time diff: {time_diff_str}")
        
        try:
            from core.messaging.alerts.telegram_alert import send_payment_match_alert as tg_match
            tg_match(bin_order, ban_dep, time_diff_str)
        except Exception as e:
            logger.error(f"Failed to send Telegram match alert: {e}")
            
        try:
            from core.messaging.alerts.discord_alert import send_payment_match_alert as ds_match
            ds_match(bin_order, ban_dep, time_diff_str)
        except Exception as e:
            logger.error(f"Failed to send Discord match alert: {e}")
            
        return True
        
    return False


def check_binance_emails():
    """Polls Gmail for new emails matching the Binance query and sends alerts."""
    if not BINANCE_EMAIL_ALERTS_ENABLED:
        logger.debug("Binance email alerts are disabled in configuration.")
        return

    # Resolve account names to scan
    accounts = list(BINANCE_MONITORED_GMAIL_ACCOUNTS)
    if not accounts:
        # Auto-detect from token files
        token_pattern = os.path.join(GMAIL_CREDENTIALS_DIR, "token_*.json")
        for filepath in glob.glob(token_pattern):
            filename = os.path.basename(filepath)
            # Extrapolate name (e.g. token_Juan_Muro.json -> Juan Muro)
            name = filename.replace("token_", "").replace(".json", "").replace("_", " ")
            accounts.append(name)
        
        # Check if generic token.json exists
        generic_token = os.path.join(GMAIL_CREDENTIALS_DIR, "token.json")
        if os.path.exists(generic_token):
            accounts.append("default")
            
    if not accounts:
        logger.warning("No Gmail accounts configured or auto-detected for Binance email monitoring.")
        return

    state = load_processed_emails()
    processed_ids = state["processed_ids"]
    recent_alerts = state["recent_alerts"]
    new_emails_processed = False

    for account in accounts:
        try:
            logger.debug(f"Checking Binance emails for Gmail account: {account}")
            # Request service non-interactively
            service = get_gmail_service(account, interactive=False)
            if not service:
                logger.debug(f"Could not connect to Gmail API for '{account}' (headless context). Skipping.")
                continue

            # Query the inbox
            query = BINANCE_EMAIL_SEARCH_QUERY
            result = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
            messages = result.get("messages", [])

            for msg_ref in messages:
                msg_id = msg_ref.get("id")
                if not msg_id or msg_id in processed_ids:
                    continue

                # Fetch metadata of the message
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date"]
                ).execute()

                headers = msg.get("payload", {}).get("headers", [])
                subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "No Subject")
                sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "Unknown Sender")
                date_str = next((h["value"] for h in headers if h["name"].lower() == "date"), "")
                snippet = msg.get("snippet", "")

                logger.info(f"New email notification detected on account '{account}': {subject} from {sender}")

                is_banorte = "banorte" in sender.lower() or "notificacionesbanorte" in sender.lower()
                is_binance = "binance.com" in sender.lower()

                # Fetch full body if it's Binance or Banorte to parse details for matching
                if is_binance or is_banorte:
                    try:
                        msg_full = service.users().messages().get(
                            userId="me",
                            id=msg_id,
                            format="full"
                        ).execute()
                        email_body = get_email_body(msg_full.get('payload', {}))
                        
                        if is_binance:
                            binance_details = parse_binance_email(email_body, subject)
                            if binance_details and binance_details.get("amount") and binance_details.get("order_number"):
                                if not binance_details.get("timestamp"):
                                    try:
                                        internal_date_ms = int(msg_full.get('internalDate', 0))
                                        if internal_date_ms > 0:
                                            binance_details["timestamp"] = datetime.fromtimestamp(internal_date_ms / 1000.0, tz=timezone.utc).isoformat()
                                    except Exception:
                                        pass
                                if not binance_details.get("timestamp"):
                                    binance_details["timestamp"] = datetime.now(timezone.utc).isoformat()
                                
                                binance_details["email_id"] = msg_id
                                state["pending_binance_orders"].append(binance_details)
                                logger.info(f"Added pending Binance order: {binance_details}")
                                check_and_match_payments(state)
                                
                        elif is_banorte:
                            banorte_details = parse_banorte_email(email_body)
                            if banorte_details and banorte_details.get("amount") and banorte_details.get("name"):
                                if not banorte_details.get("timestamp"):
                                    banorte_details["timestamp"] = datetime.now(timezone.utc).isoformat()
                                banorte_details["email_id"] = msg_id
                                state["pending_banorte_deposits"].append(banorte_details)
                                logger.info(f"Added pending Banorte deposit: {banorte_details}")
                                check_and_match_payments(state)
                    except Exception as parse_err:
                        logger.error(f"Failed to parse email body for matching: {parse_err}")

                # Send alerts to Telegram and Discord
                try:
                    send_tg(
                        account_name=account,
                        subject=subject,
                        sender=sender,
                        date_str=date_str,
                        snippet=snippet,
                        is_banorte=is_banorte
                    )
                except Exception as e:
                    logger.error(f"Failed to send Telegram alert for Binance email: {e}")

                try:
                    send_ds(
                        account_name=account,
                        subject=subject,
                        sender=sender,
                        date_str=date_str,
                        snippet=snippet,
                        is_banorte=is_banorte
                    )
                except Exception as e:
                    logger.error(f"Failed to send Discord alert for Binance email: {e}")

                # Mark as processed and save history
                ts_iso = datetime.now(timezone.utc).isoformat()
                processed_ids[msg_id] = ts_iso
                
                alert_item = {
                    "id": msg_id,
                    "timestamp": ts_iso,
                    "subject": subject,
                    "sender": sender,
                    "account": account,
                    "is_bbva": "bbva" in sender.lower() or "bbvabancomer" in sender.lower(),
                    "is_banorte": is_banorte
                }
                recent_alerts.insert(0, alert_item)
                new_emails_processed = True

        except Exception as e:
            logger.error(f"An error occurred while checking emails for account '{account}': {e}", exc_info=True)

    if new_emails_processed:
        prune_old_entries(state)
        state["recent_alerts"] = recent_alerts[:10]  # Cap history at 10 items
        save_processed_emails(state)

