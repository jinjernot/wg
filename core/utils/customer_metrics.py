import os
import json
import logging
from datetime import datetime, timezone
from dateutil import parser
from config import TRADES_STORAGE_DIR
from collections import defaultdict

logger = logging.getLogger(__name__)


def get_new_customers_this_month():
    """
    Identifies new customers for the current month.
    A new customer is defined as someone whose first trade ever was in the current month.
    
    Returns:
        dict: {
            "count": int,  # Number of new customers
            "customers": list,  # List of customer details
            "month": str,  # Current month in format "YYYY-MM"
            "total_volume": float,  # Total volume from new customers
            "platforms": dict  # Breakdown by platform
        }
    """
    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month
    current_month_str = f"{current_year}-{current_month:02d}"
    
    # Track all trades per customer globally
    customer_trades = defaultdict(list)  # {username: [trade_data, ...]}
    
    try:
        if not os.path.exists(TRADES_STORAGE_DIR):
            logger.warning(f"Trade storage directory not found at: {TRADES_STORAGE_DIR}")
            return {
                "count": 0,
                "customers": [],
                "month": current_month_str,
                "total_volume": 0.0,
                "platforms": {}
            }
        
        # First pass: collect ALL trades for ALL customers across all files
        for filename in os.listdir(TRADES_STORAGE_DIR):
            if not filename.endswith(".json"):
                continue
            
            try:
                file_owner, file_platform = filename.replace(".json", "").split("_")
            except ValueError:
                continue
            
            filepath = os.path.join(TRADES_STORAGE_DIR, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    trades = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON in {filename}: {e}")
                continue
            
            for trade_hash, trade in trades.items():
                buyer_username = trade.get("responder_username", "").strip()
                if not buyer_username:
                    continue
                
                trade_date_str = trade.get("first_seen_utc")
                if not trade_date_str:
                    continue
                
                try:
                    trade_date = parser.isoparse(trade_date_str)
                except (ValueError, TypeError):
                    continue
                
                # Store trade info for this customer
                customer_trades[buyer_username.lower()].append({
                    "trade_hash": trade_hash,
                    "date": trade_date,
                    "date_str": trade_date_str,
                    "platform": file_platform,
                    "owner": file_owner,
                    "status": trade.get("trade_status"),
                    "volume": float(trade.get("fiat_amount_requested", 0))
                })
        
        # Second pass: identify new customers (first trade in current month)
        new_customers = []
        total_volume = 0.0
        platform_stats = defaultdict(lambda: {"count": 0, "volume": 0.0})
        
        for username, trades_list in customer_trades.items():
            # Sort trades by date to find the very first trade
            trades_list.sort(key=lambda x: x["date"])
            first_trade = trades_list[0]
            first_trade_date = first_trade["date"]
            
            # Check if the first trade ever was in the current month
            if first_trade_date.year == current_year and first_trade_date.month == current_month:
                # This is a new customer!
                # Calculate stats for this customer in current month only
                month_trades = [t for t in trades_list 
                               if t["date"].year == current_year and t["date"].month == current_month]
                
                customer_volume = sum(t["volume"] for t in month_trades 
                                     if t["status"] in ["Successful", "Paid"])
                
                platforms_used = list(set(t["platform"] for t in month_trades))
                
                new_customers.append({
                    "username": username,
                    "first_trade_date": first_trade_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "trades_count": len(month_trades),
                    "total_volume": round(customer_volume, 2),
                    "platforms": platforms_used
                })
                
                total_volume += customer_volume
                
                # Update platform stats
                for platform in platforms_used:
                    platform_stats[platform]["count"] += 1
                    platform_stats[platform]["volume"] += customer_volume
        
        # Sort customers by first trade date (newest first)
        new_customers.sort(key=lambda x: x["first_trade_date"], reverse=True)
        
        # Round platform volumes
        for platform in platform_stats:
            platform_stats[platform]["volume"] = round(platform_stats[platform]["volume"], 2)
        
        result = {
            "count": len(new_customers),
            "customers": new_customers,
            "month": current_month_str,
            "total_volume": round(total_volume, 2),
            "platforms": dict(platform_stats)
        }
        
        logger.info(f"Found {len(new_customers)} new customers for {current_month_str}")
        return result
        
    except Exception as e:
        logger.error(f"Failed to calculate new customers: {e}")
        return {
            "count": 0,
            "customers": [],
            "month": current_month_str,
            "total_volume": 0.0,
            "platforms": {},
            "error": str(e)
        }


def get_customer_growth_metrics(months_back=6):
    """
    Calculate new customer growth over the past N months.
    
    Args:
        months_back (int): Number of months to include (including current month)
    
    Returns:
        dict: Monthly breakdown of new customers
    """
    now = datetime.now(timezone.utc)
    
    # Track all trades per customer globally
    customer_trades = defaultdict(list)
    
    try:
        if not os.path.exists(TRADES_STORAGE_DIR):
            logger.warning(f"Trade storage directory not found at: {TRADES_STORAGE_DIR}")
            return {"monthly_data": []}
        
        # Collect ALL trades for ALL customers
        for filename in os.listdir(TRADES_STORAGE_DIR):
            if not filename.endswith(".json"):
                continue
            
            try:
                file_owner, file_platform = filename.replace(".json", "").split("_")
            except ValueError:
                continue
            
            filepath = os.path.join(TRADES_STORAGE_DIR, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    trades = json.load(f)
            except json.JSONDecodeError:
                continue
            
            for trade_hash, trade in trades.items():
                buyer_username = trade.get("responder_username", "").strip()
                if not buyer_username:
                    continue
                
                trade_date_str = trade.get("first_seen_utc")
                if not trade_date_str:
                    continue
                
                try:
                    trade_date = parser.isoparse(trade_date_str)
                except (ValueError, TypeError):
                    continue
                
                customer_trades[buyer_username.lower()].append({
                    "date": trade_date,
                    "platform": file_platform,
                    "volume": float(trade.get("fiat_amount_requested", 0)),
                    "status": trade.get("trade_status")
                })
        
        # Count new customers per month
        monthly_data = defaultdict(lambda: {"count": 0, "customers": []})
        
        for username, trades_list in customer_trades.items():
            trades_list.sort(key=lambda x: x["date"])
            first_trade = trades_list[0]
            first_trade_date = first_trade["date"]
            
            month_key = f"{first_trade_date.year}-{first_trade_date.month:02d}"
            monthly_data[month_key]["count"] += 1
            monthly_data[month_key]["customers"].append(username)
        
        # Format output for the last N months
        result = []
        for i in range(months_back - 1, -1, -1):
            target_date = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            # Subtract months
            month = target_date.month - i
            year = target_date.year
            while month <= 0:
                month += 12
                year -= 1
            
            month_key = f"{year}-{month:02d}"
            data = monthly_data.get(month_key, {"count": 0, "customers": []})
            
            result.append({
                "month": month_key,
                "new_customers": data["count"]
            })
        
        return {"monthly_data": result}
        
    except Exception as e:
        logger.error(f"Failed to calculate customer growth metrics: {e}")
        return {"monthly_data": [], "error": str(e)}
