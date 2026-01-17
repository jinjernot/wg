"""
Unified Exchange Reports Module
Combines Bitso and Binance deposit reports with clear separation
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import pytz
import os
import calendar
from datetime import datetime
from pathlib import Path

import bitso_config
import binance_config
from core.bitso.bitso_reports import process_user_funding
from core.binance.binance_reports import process_user_deposits
from config import REPORTS_DIR


# Create unified reports directory
UNIFIED_REPORTS_DIR = REPORTS_DIR / "unified"
UNIFIED_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_unified_reports(year: int, month: int):
    """
    Generate unified reports combining Bitso and Binance deposits
    
    Args:
        year: Target year for filtering
        month: Target month for filtering
    """
    print("=" * 80)
    print("GENERATING UNIFIED EXCHANGE REPORTS")
    print("=" * 80)
    print(f"\nPeriod: {year}-{month:02d}")
    
    all_bitso_data = []
    all_binance_data = []
    
    # Process Bitso accounts
    print(f"\n{'='*80}")
    print("PROCESSING BITSO ACCOUNTS")
    print(f"{'='*80}")
    
    bitso_accounts = bitso_config.API_KEYS
    print(f"Configured Bitso accounts: {len(bitso_accounts)}")
    
    for user, (api_key, api_secret) in bitso_accounts.items():
        try:
            if not api_key or not api_secret:
                print(f"Missing credentials for {user}. Skipping...")
                continue
                
            filtered, all_fundings = process_user_funding(
                user=user,
                api_key=api_key,
                api_secret=api_secret,
                year=year,
                month=month
            )
            
            # Add exchange identifier
            for item in filtered:
                item['exchange'] = 'Bitso'
                item['exchange_account'] = user
            
            all_bitso_data.extend(filtered)
            print(f"✅ {user}: {len(filtered)} deposits this month")
            
        except Exception as e:
            print(f"❌ Error processing Bitso {user}: {str(e)}")

    
    # Process Binance accounts
    print(f"\n{'='*80}")
    print("PROCESSING BINANCE ACCOUNTS")
    print(f"{'='*80}")
    
    binance_accounts = binance_config.get_all_configured_accounts()
    print(f"Configured Binance accounts: {len(binance_accounts)}")
    
    for user in binance_accounts:
        account_config = binance_config.get_account_config(user)
        try:
            filtered, all_deposits = process_user_deposits(
                user=user,
                api_key=account_config['api_key'],
                api_secret=account_config['api_secret'],
                year=year,
                month=month
            )
            
            # Add exchange identifier
            for item in filtered:
                item['exchange'] = 'Binance'
                item['exchange_account'] = account_config.get('display_name', user)
            
            all_binance_data.extend(filtered)
            print(f"✅ {user}: {len(filtered)} deposits this month")
            
        except Exception as e:
            print(f"❌ Error processing Binance {user}: {str(e)}")
    
    # Generate unified CSV
    print(f"\n{'='*80}")
    print("GENERATING UNIFIED CSV REPORT")
    print(f"{'='*80}")
    
    csv_filename = UNIFIED_REPORTS_DIR / f"unified_deposits_{year}_{month:02d}.csv"
    _export_unified_csv(all_bitso_data, all_binance_data, csv_filename)
    
    # Generate unified chart
    print(f"\n{'='*80}")
    print("GENERATING UNIFIED CHART")
    print(f"{'='*80}")
    
    chart_filename = UNIFIED_REPORTS_DIR / f"unified_deposits_chart_{year}_{month:02d}.png"
    _generate_unified_chart(all_bitso_data, all_binance_data, year, month, chart_filename)
    
    # Summary
    print(f"\n{'='*80}")
    print("UNIFIED REPORT SUMMARY")
    print(f"{'='*80}")
    print(f"Bitso deposits: {len(all_bitso_data)}")
    print(f"Binance deposits: {len(all_binance_data)}")
    print(f"Total deposits: {len(all_bitso_data) + len(all_binance_data)}")
    print(f"\nFiles generated:")
    print(f"  CSV: {csv_filename}")
    print(f"  Chart: {chart_filename}")
    print(f"{'='*80}\n")


def _export_unified_csv(bitso_data: list, binance_data: list, filename: Path):
    """Export unified CSV with clear section separation"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"UNIFIED EXCHANGE DEPOSIT REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"\n")
        
        # Bitso section
        f.write("=" * 80 + "\n")
        f.write("BITSO DEPOSITS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total deposits: {len(bitso_data)}\n")
        f.write("\n")
        
        if bitso_data:
            # Write CSV headers
            f.write("Account,Date,Currency,Amount,Status,Method,Sender\n")
            
            for item in bitso_data:
                account = item.get('exchange_account', 'N/A')
                created_at = item.get('created_at', 'N/A')
                currency = item.get('currency', 'N/A')
                amount = item.get('amount', 'N/A')
                status = item.get('status', 'N/A')
                method = item.get('method_name', 'N/A')
                sender = item.get('details', {}).get('sender_name', 'N/A')
                
                f.write(f"{account},{created_at},{currency},{amount},{status},{method},{sender}\n")
        else:
            f.write("No Bitso deposits found\n")
        
        f.write("\n\n")
        
        # Binance section
        f.write("=" * 80 + "\n")
        f.write("BINANCE DEPOSITS\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total deposits: {len(binance_data)}\n")
        f.write("\n")
        
        if binance_data:
            # Write CSV headers
            f.write("Account,Date,Type,Currency,Amount,Status,Order ID\n")
            
            for item in binance_data:
                account = item.get('exchange_account', 'N/A')
                
                # Handle different timestamp fields
                timestamp = item.get('insertTime') or item.get('createTime')
                if timestamp:
                    try:
                        utc_dt = datetime.fromtimestamp(timestamp / 1000, tz=pytz.UTC)
                        mexico_tz = pytz.timezone('America/Mexico_City')
                        local_dt = utc_dt.astimezone(mexico_tz)
                        date_str = local_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        date_str = str(timestamp)
                else:
                    date_str = 'N/A'
                
                deposit_type = item.get('deposit_type', 'crypto')
                currency = item.get('coin') or item.get('fiatCurrency', 'N/A')
                amount = item.get('amount', 'N/A')
                status = item.get('status', 'N/A')
                order_id = item.get('orderNo') or item.get('txId', 'N/A')
                
                f.write(f"{account},{date_str},{deposit_type},{currency},{amount},{status},{order_id}\n")
        else:
            f.write("No Binance deposits found\n")
    
    print(f"✅ Unified CSV saved to: {filename}")


def _generate_unified_chart(bitso_data: list, binance_data: list, year: int, month: int, filename: Path):
    """Generate unified chart with both exchanges"""
    
    if not bitso_data and not binance_data:
        print("No data available to generate chart")
        return
    
    mexico_tz = pytz.timezone('America/Mexico_City')
    
    # Determine the date range for the month
    start_date = datetime(year, month, 1, tzinfo=mexico_tz)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=mexico_tz)
    
    # Create a complete date range for the month (normalized to start of day)
    date_range = pd.date_range(start=start_date.replace(hour=0, minute=0, second=0), 
                                end=end_date.replace(hour=0, minute=0, second=0), 
                                freq='D', 
                                tz=mexico_tz)
    
    # Initialize dictionary to store daily totals
    bitso_daily_dict = {d: 0.0 for d in date_range}
    binance_daily_dict = {d: 0.0 for d in date_range}
    
    # Process Bitso data
    if bitso_data:
        for item in bitso_data:
            try:
                # Parse the created_at timestamp
                created_at = pd.to_datetime(item['created_at'])
                if created_at.tzinfo is None:
                    created_at = created_at.tz_localize(pytz.UTC)
                created_at = created_at.tz_convert(mexico_tz)
                
                # Normalize to start of day for grouping
                day_key = created_at.normalize()
                
                # Find matching day in our date range
                for d in date_range:
                    if d.date() == day_key.date():
                        amount = float(item.get('amount', 0))
                        bitso_daily_dict[d] += amount
                        break
            except Exception as e:
                print(f"Error processing Bitso item: {e}")
                continue
    
    # Process Binance data
    if binance_data:
        for item in binance_data:
            try:
                timestamp = item.get('insertTime') or item.get('createTime')
                if timestamp:
                    utc_dt = datetime.fromtimestamp(timestamp / 1000, tz=pytz.UTC)
                    local_dt = utc_dt.astimezone(mexico_tz)
                    
                    # Normalize to start of day for grouping
                    day_key = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                    
                    # Find matching day in our date range
                    for d in date_range:
                        if d.date() == day_key.date():
                            amount = float(item.get('amount', 0))
                            binance_daily_dict[d] += amount
                            break
            except Exception as e:
                print(f"Error processing Binance item: {e}")
                continue
    
    # Debug output - check what data we're receiving
    print(f"\n=== CHART DEBUG INFO ===")
    print(f"Received {len(bitso_data)} Bitso deposits")
    print(f"Received {len(binance_data)} Binance deposits")
    
    # Sample first few Bitso items
    if bitso_data:
        print(f"\nSample Bitso deposits:")
        for i, item in enumerate(bitso_data[:3]):
            print(f"  {i+1}. Date: {item.get('created_at')}, Amount: {item.get('amount')}, Account: {item.get('exchange_account')}")
    
    # Convert to Series
    bitso_daily = pd.Series(bitso_daily_dict)
    binance_daily = pd.Series(binance_daily_dict)
    
    # Combine into a single DataFrame
    combined_df = pd.DataFrame({
        'Bitso': bitso_daily,
        'Binance': binance_daily
    })
    
    # Debug output
    print(f"\nBitso total: {bitso_daily.sum()}")
    print(f"Binance total: {binance_daily.sum()}")
    print(f"Days with Bitso data: {(bitso_daily > 0).sum()}")
    print(f"Days with Binance data: {(binance_daily > 0).sum()}")
    
    # Show daily breakdown for days with data
    print(f"\nBitso daily breakdown:")
    for date, amount in bitso_daily.items():
        if amount > 0:
            print(f"  {date.strftime('%Y-%m-%d')}: {amount:,.2f}")
    
    print(f"\nBinance daily breakdown:")
    for date, amount in binance_daily.items():
        if amount > 0:
            print(f"  {date.strftime('%Y-%m-%d')}: {amount:,.2f}")
    print(f"=========================\n")
    
    # Create chart
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot grouped bar chart
    combined_df.plot(
        kind='bar',
        ax=ax,
        color=['#1E90FF', '#F0B90B'],
        alpha=0.8,
        width=0.8
    )
    
    chart_date = datetime(year, month, 1)
    ax.set_title(f'Unified Exchange Deposits: {chart_date.strftime("%B %Y")}', fontsize=16, fontweight='bold')
    ax.set_xlabel('Day of Month', fontsize=12)
    ax.set_ylabel('Deposit Amount', fontsize=12)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Format x-axis to show day numbers
    ax.set_xticklabels([d.day for d in date_range], rotation=0)
    
    plt.tight_layout()
    plt.savefig(filename)
    print(f"✅ Unified chart saved to: {filename}")
    plt.close()
