import os
import json
import logging
from datetime import date
from config import TRADE_STORAGE_DIR

logger = logging.getLogger(__name__)

def generate_daily_summary():
    """Reads all trade files and generates a daily performance summary."""
    today_str = date.today().isoformat()
    stats = {
        "total_trades": 0,
        "successful_trades": 0,
        "paid_trades": 0,
        "active_trades": 0,
        "total_volume": 0.0,
    }

    try:
        if not os.path.exists(TRADE_STORAGE_DIR):
            logger.warning(f"Trade storage directory not found at: {TRADE_STORAGE_DIR}")
            return stats

        for filename in os.listdir(TRADE_STORAGE_DIR):
            if not filename.endswith(".json"):
                continue
            
            filepath = os.path.join(TRADE_STORAGE_DIR, filename)
            with open(filepath, 'r') as f:
                trades = json.load(f)

            for trade_hash, trade in trades.items():
                if trade.get("start_date", "").startswith(today_str):
                    stats["total_trades"] += 1
                    status = trade.get("trade_status")

                    if status == "Successful":
                        stats["successful_trades"] += 1
                        try:
                            stats["total_volume"] += float(trade.get("fiat_amount_requested", 0))
                        except (ValueError, TypeError):
                            pass
                    elif status == "Paid":
                        stats["paid_trades"] += 1
                    elif status and status.startswith("Active"):
                        stats["active_trades"] += 1
        return stats
    except Exception as e:
        logger.error(f"Failed to generate daily summary: {e}")
        return None