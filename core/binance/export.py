"""
Binance CSV Export
Export deposit records to CSV files with timezone conversion
"""
import pandas as pd
import pytz
from datetime import datetime


def export_to_csv(deposits, filename='binance_deposits.csv'):
    """
    Export deposit records to CSV file
    
    Args:
        deposits: List of deposit records from Binance API
        filename: Output CSV filename
    """
    data = []
    mexico_tz = pytz.timezone('America/Mexico_City')
    
    for deposit in deposits:
        insert_time = deposit.get('insertTime')
        
        # Convert timestamp to readable format
        try:
            utc_dt = datetime.fromtimestamp(insert_time / 1000, tz=pytz.UTC)
            local_dt = utc_dt.astimezone(mexico_tz)
            utc_dt_str = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
            local_dt_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            utc_dt_str = ''
            local_dt_str = ''
        
        # Map Binance status codes to readable format
        status_code = deposit.get('status', 0)
        status_map = {
            0: 'pending',
            6: 'credited', 
            1: 'success'
        }
        status = status_map.get(status_code, str(status_code))
        
        data.append({
            'Date (UTC)': utc_dt_str,
            'Date (Mexico City)': local_dt_str,
            'Coin': deposit.get('coin'),
            'Amount': deposit.get('amount'),
            'Status': status,
            'Status Code': status_code,
            'Address': deposit.get('address'),
            'Address Tag': deposit.get('addressTag'),
            'Transaction ID': deposit.get('txId'),
            'Network': deposit.get('network'),
            'Transfer Type': deposit.get('transferType'),
            'Confirm Times': deposit.get('confirmTimes'),
            'Unlock Confirm': deposit.get('unlockConfirm'),
            'Wallet Type': deposit.get('walletType'),
        })
    
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"Deposit summary saved to {filename}")


def export_failed_to_csv(deposits, filename='binance_failed_deposits.csv'):
    """
    Export failed/pending deposit records to CSV file
    
    Args:
        deposits: List of all deposit records from Binance API
        filename: Output CSV filename
    """
    # Filter for failed or pending deposits (status != 1)
    failed_deposits = [d for d in deposits if d.get('status') != 1]
    
    if not failed_deposits:
        print("No failed/pending deposits to export.")
        return
    
    data = []
    mexico_tz = pytz.timezone('America/Mexico_City')
    
    for deposit in failed_deposits:
        insert_time = deposit.get('insertTime')
        
        try:
            utc_dt = datetime.fromtimestamp(insert_time / 1000, tz=pytz.UTC)
            local_dt = utc_dt.astimezone(mexico_tz)
            utc_dt_str = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
            local_dt_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            utc_dt_str = ''
            local_dt_str = ''
        
        status_code = deposit.get('status', 0)
        status_map = {
            0: 'pending',
            6: 'credited',
            1: 'success'
        }
        status = status_map.get(status_code, str(status_code))
        
        data.append({
            'Date (UTC)': utc_dt_str,
            'Date (Mexico City)': local_dt_str,
            'Coin': deposit.get('coin'),
            'Amount': deposit.get('amount'),
            'Status': status,
            'Status Code': status_code,
            'Address': deposit.get('address'),
            'Address Tag': deposit.get('addressTag'),
            'Transaction ID': deposit.get('txId'),
            'Network': deposit.get('network'),
            'Transfer Type': deposit.get('transferType'),
            'Confirm Times': deposit.get('confirmTimes'),
            'Unlock Confirm': deposit.get('unlockConfirm'),
            'Wallet Type': deposit.get('walletType'),
        })
    
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"Failed/pending deposit summary saved to {filename}")


def export_combined_to_csv(crypto_deposits, fiat_deposits, filename='binance_deposits.csv'):
    """
    Export combined crypto and fiat deposit records to CSV file
    
    Args:
        crypto_deposits: List of crypto deposit records
        fiat_deposits: List of fiat deposit records
        filename: Output CSV filename
    """
    data = []
    mexico_tz = pytz.timezone('America/Mexico_City')
    
    # Process crypto deposits
    for deposit in crypto_deposits:
        insert_time = deposit.get('insertTime')
        
        # Convert timestamp to readable format
        try:
            utc_dt = datetime.fromtimestamp(insert_time / 1000, tz=pytz.UTC)
            local_dt = utc_dt.astimezone(mexico_tz)
            utc_dt_str = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
            local_dt_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            utc_dt_str = ''
            local_dt_str = ''
        
        # Map Binance status codes to readable format
        status_code = deposit.get('status', 0)
        status_map = {
            0: 'pending',
            6: 'credited', 
            1: 'success'
        }
        status = status_map.get(status_code, str(status_code))
        
        data.append({
            'Deposit Type': 'Crypto',
            'Date (UTC)': utc_dt_str,
            'Date (Mexico City)': local_dt_str,
            'Currency': deposit.get('coin'),
            'Amount': deposit.get('amount'),
            'Status': status,
            'Payment Method': deposit.get('network', 'N/A'),
            'Transaction ID': deposit.get('txId'),
            'Order Number': 'N/A',
            'Account User': deposit.get('account_user', 'N/A'),
        })
    
    # Process fiat deposits
    for deposit in fiat_deposits:
        # Fiat uses createTime instead of insertTime
        create_time = deposit.get('createTime')
        
        # Convert timestamp to readable format
        try:
            utc_dt = datetime.fromtimestamp(create_time / 1000, tz=pytz.UTC)
            local_dt = utc_dt.astimezone(mexico_tz)
            utc_dt_str = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
            local_dt_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            utc_dt_str = ''
            local_dt_str = ''
        
        # Map fiat status
        status = deposit.get('status', 'Unknown')
        
        data.append({
            'Deposit Type': 'Fiat',
            'Date (UTC)': utc_dt_str,
            'Date (Mexico City)': local_dt_str,
            'Currency': deposit.get('fiatCurrency'),
            'Amount': deposit.get('amount'),
            'Status': status,
            'Payment Method': deposit.get('paymentMethod', 'N/A'),
            'Transaction ID': 'N/A',
            'Order Number': deposit.get('orderNo', 'N/A'),
            'Account User': deposit.get('account_user', 'N/A'),
        })
    
    df = pd.DataFrame(data)
    
    # Sort by date
    if not df.empty:
        df = df.sort_values('Date (UTC)', ascending=False)
    
    df.to_csv(filename, index=False)
    print(f"Combined deposit summary saved to {filename}")

