import json
import os

from config import TRADE_STORAGE_DIR

def load_processed_trades(owner_username):
    """ Load previously processed trades. """
    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}.json")
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_processed_trade(trade):
    """ Save processed trades separately based on owner_username. """
    
    owner_username = trade.get("owner_username", "unknown_user")
    file_path = os.path.join(TRADE_STORAGE_DIR, f"{owner_username}.json")

    trades = load_processed_trades(owner_username)
    trade_hash = trade.get("trade_hash")
    
    trades[trade_hash] = trade

    with open(file_path, "w") as file:
        json.dump(trades, file, indent=4)
