"""
New module for client profitability analysis
"""

import logging
import threading
import csv
import os
from datetime import datetime

from core.utils.trade_history import fetch_completed_trades
from config import PLATFORM_ACCOUNTS, TRADE_HISTORY_DIR

logger = logging.getLogger(__name__)


def generate_client_profitability_report(output_dir=None):
    """
    Generates a comprehensive CSV report showing profitability metrics per client (buyer).
    Includes: total trades, total volume (MXN), average trade size, payment methods used.
    Returns the filepath and filename of the generated CSV.
    """
    logger.info("Generating client profitability report...")
    
    if output_dir is None:
        output_dir = TRADE_HISTORY
    
    # Fetch all trades from all accounts
    all_trades = []
    threads = []
    
    def fetch_and_append(account):
        trades = fetch_completed_trades(account)
        if trades:
            all_trades.extend(trades)
    
    for account in ACCOUNTS:
        t = threading.Thread(target=fetch_and_append, args=(account,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    if not all_trades:
        logger.warning("No trades found to generate profitability report.")
        return None, None
    
    # Filter for current month only
    from datetime import timezone as tz
    from dateutil.parser import isoparse
    
    now = datetime.now(tz.utc)
    current_month_start = datetime(now.year, now.month, 1, tzinfo=tz.utc)
    
    current_month_trades = []
    for trade in all_trades:
        completed_at = trade.get('completed_at')
        if completed_at:
            try:
                completed_date = isoparse(completed_at)
                if completed_date >= current_month_start:
                    current_month_trades.append(trade)
            except:
                pass
    
    if not current_month_trades:
        logger.warning(f"No trades found for current month ({now.strftime('%B %Y')}).")
        return None, None
    
    logger.info(f"Analyzing {len(current_month_trades)} trades from {now.strftime('%B %Y')}")
    all_trades = current_month_trades  # Use filtered trades
    
    # Analyze by buyer (client)
    buyer_stats = {}
    
    for trade in all_trades:
        if trade.get('status') != 'successful':
            continue
            
        buyer = trade.get('buyer')
        if not buyer:
            continue
        
        fiat_amount = trade.get('fiat_amount_requested')
        if not fiat_amount or fiat_amount == 'N/A':
            continue
            
        try:
            fiat_amount = float(fiat_amount)
        except (ValueError, TypeError):
            continue
        
        # Initialize buyer stats if first time seeing this buyer
        if buyer not in buyer_stats:
            buyer_stats[buyer] = {
                'buyer': buyer,
                'total_trades': 0,
                'total_volume_mxn': 0.0,
                'payment_methods': set(),
                'crypto_currencies': set(),
                'account_names': set()
            }
        
        # Update stats
        buyer_stats[buyer]['total_trades'] += 1
        buyer_stats[buyer]['total_volume_mxn'] += fiat_amount
        
        if trade.get('payment_method_name'):
            buyer_stats[buyer]['payment_methods'].add(trade['payment_method_name'])
        if trade.get('crypto_currency_code'):
            buyer_stats[buyer]['crypto_currencies'].add(trade['crypto_currency_code'])
        if trade.get('account_name'):
            buyer_stats[buyer]['account_names'].add(trade['account_name'])
    
    if not buyer_stats:
        logger.warning("No buyer statistics to export.")
        return None, None
    
    # Convert to list and sort by total volume (descending)
    buyer_list = []
    for buyer, stats in buyer_stats.items():
        buyer_list.append({
            'buyer': buyer,
            'total_trades': stats['total_trades'],
            'total_volume_mxn': round(stats['total_volume_mxn'], 2),
            'average_trade_size_mxn': round(stats['total_volume_mxn'] / stats['total_trades'], 2),
            'payment_methods': ', '.join(sorted(stats['payment_methods'])),
            'crypto_currencies': ', '.join(sorted(stats['crypto_currencies'])),
            'accounts': ', '.join(sorted(stats['account_names']))
        })
    
    # Sort by total volume (highest first)
    buyer_list.sort(key=lambda x: x['total_volume_mxn'], reverse=True)
    
    # Generate CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    month_year = datetime.now().strftime('%B_%Y')
    filename = f"client_profitability_{month_year}_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)
    
    fieldnames = [
        'buyer', 
        'total_trades', 
        'total_volume_mxn', 
        'average_trade_size_mxn',
        'payment_methods',
        'crypto_currencies',
        'accounts'
    ]
    
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(buyer_list)
        
        logger.info(f"Successfully generated client profitability report: {filepath}")
        logger.info(f"Total unique clients: {len(buyer_list)}")
        if buyer_list:
            logger.info(f"Top client: {buyer_list[0]['buyer']} with ${buyer_list[0]['total_volume_mxn']:,.2f} MXN")
        
        return filepath, filename
    except IOError as e:
        logger.error(f"Failed to write profitability report CSV: {e}")
        return None, None
