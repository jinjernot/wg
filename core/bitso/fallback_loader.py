"""
Fallback data loader for blocked Bitso accounts.
This module is separate from bitso_reports to avoid heavy dependencies like matplotlib.
"""
import pandas as pd
import os


def load_eduardo_fallback_data(year: int, month: int):
    """
    Temporary workaround for blocked eduardo_ramirez account (December 2025).
    Loads data from static CSV file in root directory.
    """
    # Only use this workaround for December 2025
    if year != 2025 or month != 12:
        return []
    
    # Get the project root directory (parent of the data directory)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(project_root)  # Go up one more level to reach will_gang root
    fallback_csv = os.path.join(project_root, 'bitso_deposits_eduardo_ramirez.csv')
    
    if not os.path.exists(fallback_csv):
        print(f"⚠️ Fallback CSV not found at: {fallback_csv}")
        return []
    
    print(f"📁 Loading fallback data for eduardo_ramirez from: {fallback_csv}")
    
    try:
        df = pd.read_csv(fallback_csv)
        
        # Convert DataFrame back to list of dicts (simulating API response format)
        fundings = []
        for _, row in df.iterrows():
            # Safely convert amount to string, handling NaN and other types
            try:
                amount_value = float(row['Amount'])
                amount_str = str(amount_value)
            except (ValueError, TypeError):
                print(f"⚠️ Skipping row with invalid amount: {row.get('Funding ID', 'unknown')}")
                continue
            
            # Safely get string fields, replacing NaN with empty string
            def safe_str(val):
                if pd.isna(val):
                    return ''
                return str(val)
            
            funding = {
                'fid': safe_str(row['Funding ID']),
                'status': safe_str(row['Status']),
                'created_at': safe_str(row['Date (UTC)']),
                'amount': amount_str,
                'currency': safe_str(row['Currency']),
                'asset': safe_str(row['Asset']),
                'method': safe_str(row['Method']),
                'method_name': safe_str(row['Method Name']),
                'details': {
                    'sender_name': safe_str(row['Sender Name']),
                    'sender_clabe': safe_str(row['Sender CLABE']),
                    'receiver_clabe': safe_str(row['Receive CLABE'])
                },
                'account_user': 'eduardo_ramirez'
            }
            fundings.append(funding)
        
        print(f"✅ Loaded {len(fundings)} transactions from fallback CSV")
        return fundings
        
    except Exception as e:
        print(f"❌ Error loading fallback CSV: {e}")
        return []
