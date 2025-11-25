import logging
import csv
import os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Gift card payment method slugs
GIFT_CARD_SLUGS = [
    "amazon-gift-card",
    "uber-gift-card",
    "uber-eats",
    "google-play-gift-card"
]

# Human-readable names for display
GIFT_CARD_NAMES = {
    "amazon-gift-card": "Amazon Gift Card",
    "uber-gift-card": "Uber Gift Card",
    "uber-eats": "Uber Eats",
    "google-play-gift-card": "Google Play Gift Card"
}


def filter_gift_card_trades(all_trades: List[Dict]) -> List[Dict]:
    """
    Filter trades to only include gift card transactions.
    
    Args:
        all_trades: List of normalized trade dictionaries
        
    Returns:
        List of trades that use gift card payment methods
    """
    gift_card_trades = []
    
    for trade in all_trades:
        payment_method = trade.get("payment_method_name", "").lower()
        
        # Check if the payment method matches any gift card slug
        for slug in GIFT_CARD_SLUGS:
            if slug in payment_method or slug.replace("-", " ") in payment_method:
                gift_card_trades.append(trade)
                break
    
    logger.info(f"Filtered {len(gift_card_trades)} gift card trades from {len(all_trades)} total trades")
    return gift_card_trades


def calculate_gift_card_stats(trades: List[Dict]) -> Dict:
    """
    Calculate comprehensive statistics for gift card trades.
    
    Args:
        trades: List of gift card trade dictionaries
        
    Returns:
        Dictionary containing various statistics
    """
    if not trades:
        return {
            "total_trades": 0,
            "total_volume": 0.0,
            "by_card_type": {},
            "by_account": {},
            "top_buyers": [],
            "average_trade_size": 0.0
        }
    
    # Initialize counters
    total_volume = 0.0
    card_type_stats = defaultdict(lambda: {"count": 0, "volume": 0.0, "crypto_volume": 0.0})
    account_stats = defaultdict(lambda: {"count": 0, "volume": 0.0})
    buyer_stats = defaultdict(int)
    
    for trade in trades:
        # Only count successful trades
        if trade.get("status") != "successful":
            continue
            
        fiat_amount = trade.get("fiat_amount_requested") or 0.0
        crypto_amount = trade.get("crypto_amount_requested") or 0.0
        payment_method = trade.get("payment_method_name", "").lower()
        account = trade.get("account_name", "Unknown")
        buyer = trade.get("buyer")
        
        # Determine card type
        card_type = "other"
        for slug in GIFT_CARD_SLUGS:
            if slug in payment_method or slug.replace("-", " ") in payment_method:
                card_type = slug
                break
        
        # Update statistics
        total_volume += fiat_amount
        card_type_stats[card_type]["count"] += 1
        card_type_stats[card_type]["volume"] += fiat_amount
        card_type_stats[card_type]["crypto_volume"] += crypto_amount
        
        account_stats[account]["count"] += 1
        account_stats[account]["volume"] += fiat_amount
        
        if buyer:
            buyer_stats[buyer] += 1
    
    # Get top 10 buyers
    top_buyers = sorted(buyer_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    top_buyers_list = [{"username": buyer, "trade_count": count} for buyer, count in top_buyers]
    
    # Calculate average trade size
    successful_count = sum(stats["count"] for stats in card_type_stats.values())
    average_trade_size = total_volume / successful_count if successful_count > 0 else 0.0
    
    # Convert defaultdicts to regular dicts for JSON serialization
    card_type_dict = {
        GIFT_CARD_NAMES.get(k, k.title()): {
            "count": v["count"],
            "volume": round(v["volume"], 2),
            "crypto_volume": round(v["crypto_volume"], 8)
        }
        for k, v in card_type_stats.items()
    }
    
    account_dict = {
        k: {
            "count": v["count"],
            "volume": round(v["volume"], 2)
        }
        for k, v in account_stats.items()
    }
    
    return {
        "total_trades": successful_count,
        "total_volume": round(total_volume, 2),
        "by_card_type": card_type_dict,
        "by_account": account_dict,
        "top_buyers": top_buyers_list,
        "average_trade_size": round(average_trade_size, 2)
    }


def get_gift_card_summary(all_trades: List[Dict], days: Optional[int] = None) -> Dict:
    """
    Generate a summary of gift card trades, optionally filtered by date range.
    
    Args:
        all_trades: List of all normalized trades
        days: Optional number of days to look back (None = all time)
        
    Returns:
        Dictionary with summary statistics
    """
    # Filter to gift card trades only
    gift_card_trades = filter_gift_card_trades(all_trades)
    
    # Apply date filter if specified
    if days is not None:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        filtered_trades = []
        
        for trade in gift_card_trades:
            completed_at = trade.get("completed_at")
            if completed_at:
                try:
                    # Parse the date string
                    if isinstance(completed_at, str):
                        trade_date = datetime.strptime(completed_at, "%Y-%m-%d %H:%M:%S")
                        trade_date = trade_date.replace(tzinfo=timezone.utc)
                    else:
                        trade_date = completed_at
                    
                    if trade_date >= cutoff_date:
                        filtered_trades.append(trade)
                except Exception as e:
                    logger.warning(f"Could not parse date {completed_at}: {e}")
        
        gift_card_trades = filtered_trades
        logger.info(f"Filtered to {len(gift_card_trades)} trades in last {days} days")
    
    # Calculate statistics
    stats = calculate_gift_card_stats(gift_card_trades)
    stats["date_range"] = f"Last {days} days" if days else "All time"
    stats["raw_trade_count"] = len(gift_card_trades)
    
    return stats


def generate_gift_card_csv(trades: List[Dict], output_path: str) -> str:
    """
    Export gift card trades to a CSV file.
    
    Args:
        trades: List of gift card trade dictionaries
        output_path: Directory path to save the CSV
        
    Returns:
        Full path to the generated CSV file
    """
    if not trades:
        logger.warning("No gift card trades to export")
        return None
    
    # Ensure output directory exists
    os.makedirs(output_path, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"gift_card_trades_{timestamp}.csv"
    filepath = os.path.join(output_path, filename)
    
    # Define CSV columns
    fieldnames = [
        "trade_hash",
        "account_name",
        "payment_method_name",
        "buyer",
        "seller",
        "status",
        "fiat_amount_requested",
        "crypto_amount_requested",
        "fiat_currency_code",
        "crypto_currency_code",
        "started_at",
        "completed_at",
        "offer_hash"
    ]
    
    try:
        with open(filepath, "w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(trades)
        
        logger.info(f"Exported {len(trades)} gift card trades to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Failed to export gift card trades to CSV: {e}")
        return None


def get_gift_card_trades_by_type(all_trades: List[Dict], card_type: str) -> List[Dict]:
    """
    Filter gift card trades by specific card type.
    
    Args:
        all_trades: List of all normalized trades
        card_type: Gift card type slug (e.g., "amazon-gift-card")
        
    Returns:
        List of trades matching the card type
    """
    gift_card_trades = filter_gift_card_trades(all_trades)
    
    filtered = []
    for trade in gift_card_trades:
        payment_method = trade.get("payment_method_name", "").lower()
        if card_type.lower() in payment_method or card_type.lower().replace("-", " ") in payment_method:
            filtered.append(trade)
    
    logger.info(f"Found {len(filtered)} trades for card type: {card_type}")
    return filtered
