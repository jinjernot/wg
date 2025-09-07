import json
import os
from config import TRADE_STORAGE_DIR

def load_processed_trades(owner_username, platform):
    
    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}_{platform}.json")
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_processed_trade(trade_data, platform, processed_data):
    """
    Saves the complete trade data by merging the original API data
    with the bot's processed metadata.
    """
    owner_username = trade_data.get("owner_username", "unknown_user")
    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}_{platform}.json")
    
    # Load all trades from the persistent file
    all_trades = load_processed_trades(owner_username, platform)
    trade_hash = trade_data.get("trade_hash")

    combined_trade_data = {
        **trade_data, 
        **all_trades.get(trade_hash, {}), 
        **processed_data
    }
    
    # Update the master dictionary with the fully combined trade data
    all_trades[trade_hash] = combined_trade_data

    # Save the updated master dictionary back to the file
    with open(file_path, "w") as file:
        json.dump(all_trades, file, indent=4)