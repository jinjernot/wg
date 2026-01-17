"""
Binance Data Filtering
Filter deposit records by time periods
"""
import pytz
from datetime import date
from dateutil import parser


def filter_deposits_by_month(deposits, year, month):
    """
    Filter deposit records to only include those from a specific month
    
    Args:
        deposits: List of deposit records from Binance API
        year: Target year (e.g., 2026)
        month: Target month (1-12)
    
    Returns:
        List of filtered deposit records
    """
    mexico_tz = pytz.timezone('America/Mexico_City')
    
    start_date = date(year, month, 1)
    # Calculate the end of the month
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)
    
    print(f"Filtering deposits from {start_date} to {end_date} (Mexico City time)")
    
    filtered = []
    for deposit in deposits:
        # Binance uses 'insertTime' for when the deposit was created
        insert_time = deposit.get('insertTime')
        if not insert_time:
            continue
        
        try:
            # Convert millisecond timestamp to datetime
            from datetime import datetime
            created_utc = datetime.fromtimestamp(insert_time / 1000, tz=pytz.UTC)
            created_local = created_utc.astimezone(mexico_tz).date()
            
            if start_date <= created_local < end_date:
                filtered.append(deposit)
        except Exception as e:
            print(f"Skipping record with bad timestamp: {insert_time} ({e})")
    
    print(f"Filtered down to {len(filtered)} deposit transactions")
    return filtered
