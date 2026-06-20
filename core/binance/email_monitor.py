"""
Binance P2P Gmail Notification Monitor
Periodically polls Gmail accounts for emails from Binance and sends alerts.
"""

import os
import json
import logging
import glob
from datetime import datetime, timezone, timedelta

from config import (
    BINANCE_EMAIL_ALERTS_ENABLED,
    BINANCE_MONITORED_GMAIL_ACCOUNTS,
    BINANCE_EMAIL_SEARCH_QUERY,
    BINANCE_PROCESSED_EMAILS_FILE,
    GMAIL_CREDENTIALS_DIR
)
from core.validation.email import get_gmail_service
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
                    return data
        except Exception as e:
            logger.error(f"Failed to load processed Binance emails state: {e}")
    return {"processed_ids": {}, "recent_alerts": []}

def save_processed_emails(state: dict):
    """Saves the processed state dict containing message IDs and history."""
    try:
        os.makedirs(os.path.dirname(BINANCE_PROCESSED_EMAILS_FILE), exist_ok=True)
        with open(BINANCE_PROCESSED_EMAILS_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save processed Binance emails state: {e}")

def prune_old_entries(processed_ids: dict, max_age_days: int = 14):
    """Removes processed email IDs older than max_age_days to keep state file small."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    keys_to_delete = []
    
    for msg_id, timestamp_str in processed_ids.items():
        try:
            ts = datetime.fromisoformat(timestamp_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < cutoff:
                keys_to_delete.append(msg_id)
        except Exception:
            # If timestamp is unparseable, queue for deletion to be safe
            keys_to_delete.append(msg_id)
            
    for key in keys_to_delete:
        del processed_ids[key]
    
    if keys_to_delete:
        logger.info(f"Pruned {len(keys_to_delete)} old/corrupted message ID entries from state.")

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

                # Send alerts to Telegram and Discord
                try:
                    send_tg(
                        account_name=account,
                        subject=subject,
                        sender=sender,
                        date_str=date_str,
                        snippet=snippet
                    )
                except Exception as e:
                    logger.error(f"Failed to send Telegram alert for Binance email: {e}")

                try:
                    send_ds(
                        account_name=account,
                        subject=subject,
                        sender=sender,
                        date_str=date_str,
                        snippet=snippet
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
                    "is_bbva": "bbva" in sender.lower() or "bbvabancomer" in sender.lower()
                }
                recent_alerts.insert(0, alert_item)
                new_emails_processed = True

        except Exception as e:
            logger.error(f"An error occurred while checking emails for account '{account}': {e}", exc_info=True)

    if new_emails_processed:
        prune_old_entries(processed_ids)
        state["recent_alerts"] = recent_alerts[:10]  # Cap history at 10 items
        save_processed_emails(state)
