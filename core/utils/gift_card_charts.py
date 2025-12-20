"""
Gift card-specific chart generation functions for trade history reports.
"""
import logging
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend to prevent threading issues
import matplotlib.pyplot as plt
from datetime import datetime
from  core.utils.gift_card_analytics import filter_gift_card_trades, GIFT_CARD_NAMES

logger = logging.getLogger(__name__)


def plot_gift_card_trades_by_type(all_trades, output_path):
    """Generate a bar chart showing gift card trade counts by card type."""
    gift_card_trades = filter_gift_card_trades(all_trades)
    
    if not gift_card_trades:
        logger.info("No gift card trades found for chart generation.")
        return
    
    # Count trades by card type
    card_type_counts = {}
    for trade in gift_card_trades:
        if trade.get('status') == 'successful':
            payment_method = trade.get('payment_method_name', '').lower()
            # Determine card type
            for slug, name in GIFT_CARD_NAMES.items():
                if slug in payment_method or slug.replace('-', ' ') in payment_method:
                    card_type_counts[name] = card_type_counts.get(name, 0) + 1
                    break
    
    if not card_type_counts:
        logger.info("No successful gift card trades to plot.")
        return
    
    # Create bar chart
    card_types = list(card_type_counts.keys())
    counts = list(card_type_counts.values())
    
    plt.figure(figsize=(10, 6))
    plt.bar(card_types, counts, color='purple')
    plt.title("Gift Card Trades by Type")
    plt.xlabel("Card Type")
    plt.ylabel("Number of Trades")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Gift card trades by type chart saved to {output_path}")


def plot_gift_card_volume_trends(all_trades, output_path):
    """Generate a line chart showing gift card trade volume over time."""
    gift_card_trades = filter_gift_card_trades(all_trades)
    
    if not gift_card_trades:
        logger.info("No gift card trades found for volume trends chart.")
        return
    
    # Filter to successful trades with valid dates
    successful_trades = []
    for trade in gift_card_trades:
        if trade.get('status') == 'successful' and trade.get('completed_at'):
            try:
                completed_at = trade.get('completed_at')
                if isinstance(completed_at, str):
                    trade_date = datetime.strptime(completed_at, "%Y-%m-%d %H:%M:%S")
                    trade['parsed_date'] = trade_date
                    successful_trades.append(trade)
            except Exception as e:
                logger.warning(f"Could not parse date {completed_at}: {e}")
    
    if not successful_trades:
        logger.info("No valid successful gift card trades for volume trends.")
        return
    
    # Group by month
    monthly_volume = {}
    for trade in successful_trades:
        month_key = trade['parsed_date'].strftime('%Y-%m')
        volume = trade.get('fiat_amount_requested', 0) or 0
        monthly_volume[month_key] = monthly_volume.get(month_key, 0) + volume
    
    # Sort by date
    sorted_months = sorted(monthly_volume.keys())
    volumes = [monthly_volume[month] for month in sorted_months]
    
    plt.figure(figsize=(12, 6))
    plt.plot(sorted_months, volumes, marker='o', linewidth=2, markersize=8, color='purple')
    plt.title("Gift Card Trade Volume Over Time")
    plt.xlabel("Month")
    plt.ylabel("Total Volume (MXN)")
    plt.xticks(rotation=45, ha="right")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    logger.info(f"Gift card volume trends chart saved to {output_path}")
