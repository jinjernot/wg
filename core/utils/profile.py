import os
import json
import logging
from datetime import datetime, timezone
from config import TRADES_STORAGE_DIR
from dateutil import parser

logger = logging.getLogger(__name__)

def generate_user_profile(username):
    """Scans all trade files to generate a trading profile for a specific user for the current month."""
    stats = {
        "total_trades": 0,
        "successful_trades": 0,
        "disputed_trades": 0,
        "canceled_trades": 0,
        "total_volume": 0.0,
        "username": username,
        "first_trade_date": None,
        "last_trade_date": None,
        "platforms": {},
        "accounts": {}
    }
    
    trade_dates = []
    
    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month

    try:
        if not os.path.exists(TRADES_STORAGE_DIR):
            logger.warning(f"Trade storage directory not found at: {TRADES_STORAGE_DIR}")
            return None

        for filename in os.listdir(TRADES_STORAGE_DIR):
            if not filename.endswith(".json"):
                continue
            
            try:
                file_owner, file_platform = filename.replace(".json", "").split("_")
            except ValueError:
                continue 

            filepath = os.path.join(TRADES_STORAGE_DIR, filename)
            with open(filepath, 'r') as f:
                trades = json.load(f)

            for trade_hash, trade in trades.items():
                if trade.get("responder_username", "").lower() == username.lower():
                    trade_date_str = trade.get("first_seen_utc")
                    if not trade_date_str:
                        continue

                    try:
                        trade_date = parser.isoparse(trade_date_str)
                    except (ValueError, TypeError):
                        continue
                        
                    if trade_date.year != current_year or trade_date.month != current_month:
                        continue

                    stats["total_trades"] += 1
                    status = trade.get("trade_status")

                    trade_dates.append(trade_date_str)

                    stats["accounts"][file_owner] = stats["accounts"].get(file_owner, 0) + 1
                    
                    if status in ["Successful", "Paid"]:
                        stats["successful_trades"] += 1
                        try:
                            volume = float(trade.get("fiat_amount_requested", 0))
                            stats["total_volume"] += volume
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