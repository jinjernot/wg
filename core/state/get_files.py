import json
import os
from config import TRADE_STORAGE_DIR

def load_processed_trades(owner_username, platform):
    """Loads all processed trades for a specific user and platform."""
    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}_{platform}.json")
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_processed_trade(trade_data, platform):
    """
    Saves the complete and final state of a single trade to the JSON file.
    """
    owner_username = trade_data.get("owner_username", "unknown_user")
    trade_hash = trade_data.get("trade_hash")
    
    if not owner_username or not trade_hash:
        return # Cannot save without these essential keys

    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}_{platform}.json")
    
    # Load all trades to ensure we don't overwrite other trades in the file.
    all_trades = load_processed_trades(owner_username, platform)
    
    # Update the dictionary with the new, complete data for the specific trade.
    all_trades[trade_hash] = trade_data

    # Write the entire updated dictionary back to the file.
    # Write to a temporary file first to ensure atomicity
    temp_file_path = file_path + ".tmp"
    try:
        with open(temp_file_path, "w") as file:
            json.dump(all_trades, file, indent=4)
            file.flush()
            os.fsync(file.fileno())
        
        # Atomic replace
        os.replace(temp_file_path, file_path)
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise e