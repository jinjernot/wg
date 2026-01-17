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
    
    # Process Bitso data
    bitso_df = None
    if bitso_data:
        bitso_df = pd.DataFrame(bitso_data)
        bitso_df['created_at'] = pd.to_datetime(bitso_df['created_at'])
        bitso_df['amount'] = pd.to_numeric(bitso_df['amount'])
        bitso_df['created_at'] = bitso_df['created_at'].dt.tz_convert(mexico_tz)
        bitso_df.set_index('created_at', inplace=True)
        bitso_daily = bitso_df['amount'].resample('D').sum()
    
    # Process Binance data
    binance_df = None
    if binance_data:
        binance_list = []
        for item in binance_data:
            timestamp = item.get('insertTime') or item.get('createTime')
            if timestamp:
                try:
                    utc_dt = datetime.fromtimestamp(timestamp / 1000, tz=pytz.UTC)
                    local_dt = utc_dt.astimezone(mexico_tz)
                    amount = float(item.get('amount', 0))
                    binance_list.append({'date': local_dt, 'amount': amount})
                except:
                    pass
        
        if binance_list:
            binance_df = pd.DataFrame(binance_list)
            binance_df.set_index('date', inplace=True)
            binance_daily = binance_df['amount'].resample('D').sum()
    
    # Create chart
    plt.figure(figsize=(14, 8))
    
    if bitso_df is not None:
        bitso_daily.plot(kind='bar', color='#1E90FF', label='Bitso', alpha=0.8, width=0.4, position=0)
    
    if binance_df is not None and binance_list:
        binance_daily.plot(kind='bar', color='#F0B90B', label='Binance', alpha=0.8, width=0.4, position=1)
    
    chart_date = datetime(year, month, 1)
    plt.title(f'Unified Exchange Deposits: {chart_date.strftime("%B %Y")}', fontsize=16, fontweight='bold')
    plt.xlabel('Day of Month', fontsize=12)
    plt.ylabel('Deposit Amount', fontsize=12)
    plt.legend(loc='upper right', fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.gca().xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%d'))
    plt.xticks(rotation=0)
    plt.tight_layout()
    
    plt.savefig(filename)
    print(f"✅ Unified chart saved to: {filename}")
    plt.close()
