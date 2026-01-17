"""
Binance Deposit Reports Generator
Main module for generating deposit reports and charts for multiple Binance accounts
"""
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend to prevent threading issues
import matplotlib.pyplot as plt
import binance_config
import pandas as pd
import pytz
import os

from core.binance.fetch_deposits import fetch_deposit_history_for_user
from core.binance.fetch_fiat_deposits import fetch_fiat_deposit_history_for_user
from core.binance.fetch_fiat_orders import fetch_fiat_orders_for_user
from core.binance.export import export_to_csv, export_failed_to_csv, export_combined_to_csv
from core.binance.filter_data import filter_deposits_by_month

from datetime import datetime
from config import BINANCE_REPORTS_DIR

os.makedirs(BINANCE_REPORTS_DIR, exist_ok=True)


def process_user_deposits(user: str, api_key: str, api_secret: str, year: int, month: int) -> tuple[list, list]:
    """
    Process crypto, fiat payments, and fiat orders deposit history for a single user account
    
    Args:
        user: Username identifier
        api_key: Binance API key
        api_secret: Binance API secret
        year: Target year for filtering
        month: Target month for filtering
    
    Returns:
        Tuple of (filtered_deposits_combined, all_deposits_combined)
    """
    print(f"\nProcessing user: {user}")
    
    if not api_key or not api_secret:
        print(f"Missing credentials for {user}. Skipping...")
        return [], []
    
    # Fetch crypto deposits
    crypto_deposits = fetch_deposit_history_for_user(user, api_key, api_secret)
    
    # Fetch fiat payments (fiat-to-crypto purchases)
    fiat_payments = fetch_fiat_deposit_history_for_user(user, api_key, api_secret)
    
    # Fetch fiat orders (pure SPEI/bank transfers)
    fiat_orders = fetch_fiat_orders_for_user(user, api_key, api_secret)
    
    # Add account user to each deposit record
    for deposit in crypto_deposits:
        deposit['account_user'] = user
    for deposit in fiat_payments:
        deposit['account_user'] = user
        deposit['deposit_type'] = 'fiat_payment'
    for deposit in fiat_orders:
        deposit['account_user'] = user
        deposit['deposit_type'] = 'fiat_order'
    
    # Filter crypto deposits by the specified month
    filtered_crypto = filter_deposits_by_month(crypto_deposits, year, month)
    
    # Filter fiat payments by the specified month (they use createTime, not insertTime)
    filtered_fiat_payments = []
    for deposit in fiat_payments:
        create_time = deposit.get('createTime')
        if create_time:
            try:
                utc_dt = datetime.fromtimestamp(create_time / 1000, tz=pytz.UTC)
                mexico_tz = pytz.timezone('America/Mexico_City')
                local_dt = utc_dt.astimezone(mexico_tz)
                if local_dt.year == year and local_dt.month == month:
                    filtered_fiat_payments.append(deposit)
            except Exception as e:
                print(f"Error filtering fiat payment: {e}")
    
    # Filter fiat orders by the specified month (they use createTime)
    filtered_fiat_orders = []
    for deposit in fiat_orders:
        create_time = deposit.get('createTime')
        if create_time:
            try:
                utc_dt = datetime.fromtimestamp(create_time / 1000, tz=pytz.UTC)
                mexico_tz = pytz.timezone('America/Mexico_City')
                local_dt = utc_dt.astimezone(mexico_tz)
                if local_dt.year == year and local_dt.month == month:
                    filtered_fiat_orders.append(deposit)
            except Exception as e:
                print(f"Error filtering fiat order: {e}")
    
    print(f"Filtering deposits from {year}-{month:02d}-01 to {year}-{month+1 if month < 12 else 1:02d}-01 (Mexico City time)")
    print(f"Filtered down to {len(filtered_crypto)} crypto + {len(filtered_fiat_payments)} fiat payments + {len(filtered_fiat_orders)} fiat orders = {len(filtered_crypto) + len(filtered_fiat_payments) + len(filtered_fiat_orders)} total deposit transactions")
    
    # Export to CSV files using combined export
    deposits_filename = os.path.join(BINANCE_REPORTS_DIR, f'binance_deposits_{user}.csv')
    failed_filename = os.path.join(BINANCE_REPORTS_DIR, f'binance_failed_deposits_{user}.csv')
    
    # Combine all filtered deposits for export
    all_filtered = filtered_crypto + filtered_fiat_payments + filtered_fiat_orders
    export_combined_to_csv(filtered_crypto, filtered_fiat_payments + filtered_fiat_orders, filename=deposits_filename)
    export_failed_to_csv(crypto_deposits, filename=failed_filename)  # Keep crypto-only for failed
    
    # Combine all deposits for return
    all_combined = crypto_deposits + fiat_payments + fiat_orders
    filtered_combined = all_filtered
    
    return filtered_combined, all_combined



def generate_growth_chart(all_deposits: list, year: int, month: int, filename: str = 'binance_this_month_income.png'):
    """
    Generates and saves a bar chart of daily deposit income for a specific month
    
    Args:
        all_deposits: List of all deposit records
        year: Target year
        month: Target month
        filename: Output filename for the chart
    """
    print(f"\nGenerating daily deposit income bar chart for {year}-{month}...")
    
    if not all_deposits:
        print("No deposit data available to generate a bar chart.")
        return
    
    # Filter for successful deposits only (status = 1)
    successful_deposits = [
        d for d in all_deposits 
        if d.get('status') == 1
    ]
    
    if not successful_deposits:
        print("No successful deposit data found to generate a bar chart.")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(successful_deposits)
    
    # Convert timestamps to datetime
    df['insertTime'] = pd.to_datetime(df['insertTime'], unit='ms', utc=True)
    df['amount'] = pd.to_numeric(df['amount'])
    
    # Convert to Mexico timezone
    mexico_tz = pytz.timezone('America/Mexico_City')
    df['insertTime'] = df['insertTime'].dt.tz_convert(mexico_tz)
    
    # Filter for the specific month
    month_df = df[(df['insertTime'].dt.year == year) & 
                   (df['insertTime'].dt.month == month)]
    
    if month_df.empty:
        print(f"No deposit data found for {year}-{month}. Bar chart not generated.")
        return
    
    # Resample by day and sum amounts
    month_df.set_index('insertTime', inplace=True)
    daily_income = month_df['amount'].resample('D').sum()
    
    # Create bar chart
    plt.figure(figsize=(12, 7))
    daily_income.plot(kind='bar', color='#F0B90B', edgecolor='black')  # Binance yellow
    
    chart_date = datetime(year, month, 1)
    plt.title(f'Binance Deposits: {chart_date.strftime("%B %Y")}', fontsize=16, fontweight='bold')
    plt.xlabel('Day of Month', fontsize=12)
    plt.ylabel('Deposit Amount', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%d'))
    plt.xticks(rotation=0)
    plt.tight_layout()
    
    # Save chart to the reports directory
    chart_filepath = os.path.join(BINANCE_REPORTS_DIR, filename)
    plt.savefig(chart_filepath)
    print(f"Success! Daily deposit income bar chart saved to {chart_filepath}")
    plt.close()
