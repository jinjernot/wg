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

def save_processed_trade(trade_data, platform):
    """
    Saves the complete and final trade data to the JSON file.
    """
    owner_username = trade_data.get("owner_username", "unknown_user")
    trade_hash = trade_data.get("trade_hash")
    
    if not owner_username or not trade_hash:
        return # Cannot save without these keys

    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}_{platform}.json")
    
    all_trades = load_processed_trades(owner_username, platform)
    all_trades[trade_hash] = trade_data

    with open(file_path, "w") as file:
        json.dump(all_trades, file, indent=4)