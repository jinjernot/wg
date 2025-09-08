# core/utils/profile.py
import os
import json
import logging
from datetime import datetime, timezone
from config import TRADE_STORAGE_DIR
from dateutil import parser

logger = logging.getLogger(__name__)

def generate_user_profile(username):
    """Scans all trade files to generate a trading profile for a specific user."""
    stats = {
        "total_trades": 0,
        "successful_trades": 0,
        "disputed_trades": 0,
        "canceled_trades": 0,
        "total_volume": 0.0,
        "username": username,
        "first_trade_date": None,
        "last_trade_date": None,
        "platforms": {},  # To track trades per platform (e.g., Paxful, Noones)
        "accounts": {}    # To track trades per owner (e.g, davidvs, JoeWillgang)
    }
    
    trade_dates = []

    try:
        if not os.path.exists(TRADE_STORAGE_DIR):
            logger.warning(f"Trade storage directory not found at: {TRADE_STORAGE_DIR}")
            return None

        for filename in os.listdir(TRADE_STORAGE_DIR):
            if not filename.endswith(".json"):
                continue
            
            # Extract owner and platform from the filename (e.g., "davidvs_Paxful.json")
            try:
                file_owner, file_platform = filename.replace(".json", "").split("_")
            except ValueError:
                continue # Skip files that don't match the expected format

            filepath = os.path.join(TRADE_STORAGE_DIR, filename)
            with open(filepath, 'r') as f:
                trades = json.load(f)

            for trade_hash, trade in trades.items():
                if trade.get("responder_username", "").lower() == username.lower():
                    stats["total_trades"] += 1
                    status = trade.get("trade_status")

                    # Use the reliable 'first_seen_utc' for date tracking
                    trade_date_str = trade.get("first_seen_utc")
                    if trade_date_str:
                        trade_dates.append(trade_date_str)

                    # Track which of your accounts handled the trade
                    stats["accounts"][file_owner] = stats["accounts"].get(file_owner, 0) + 1
                    
                    if status == "Successful":
                        stats["successful_trades"] += 1
                        # Use 'fiat_amount_requested' for volume calculation
                        try:
                            volume = float(trade.get("fiat_amount_requested", 0))
                            stats["total_volume"] += volume
                            # Track volume and trades per platform
                            if file_platform not in stats["platforms"]:
                                stats["platforms"][file_platform] = {"trades": 0, "volume": 0.0}
                            stats["platforms"][file_platform]["trades"] += 1
                            stats["platforms"][file_platform]["volume"] += volume
                        except (ValueError, TypeError):
                            pass
                    elif status == "Dispute open":
                        stats["disputed_trades"] += 1
                    elif status == "Cancelled":
                        stats["canceled_trades"] += 1
        
        if stats["total_trades"] == 0:
            return None

        if trade_dates:
            trade_dates.sort()
            stats["first_trade_date"] = parser.isoparse(trade_dates[0]).strftime("%Y-%m-%d")
            stats["last_trade_date"] = parser.isoparse(trade_dates[-1]).strftime("%Y-%m-%d")

        return stats
    except Exception as e:
        logger.error(f"Failed to generate user profile for {username}: {e}")
        return None