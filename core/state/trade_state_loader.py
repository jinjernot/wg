import json
import os
import time
import logging
from functools import wraps
from config import TRADES_STORAGE_DIR

logger = logging.getLogger(__name__)

def retry_on_permission_error(max_retries=5, base_delay=0.1):
    """Decorator to retry file operations on Windows PermissionError with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except PermissionError as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Failed after {max_retries} retries: {e}")
                        raise
                    delay = base_delay * (2 ** attempt)  # Exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                    logger.warning(f"PermissionError on attempt {attempt + 1}/{max_retries}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def load_processed_trades(owner_username, platform):
    """Loads all processed trades for a specific user and platform."""
    file_path = os.path.join(TRADES_STORAGE_DIR, f"{owner_username}_{platform}.json")
    try:
        # Check if file exists and is not empty
        if not os.path.exists(file_path):
            return {}
        
        if os.path.getsize(file_path) == 0:
            logger.warning(f"Trade file for {owner_username}_{platform} is empty. Returning empty dict.")
            return {}
            
        with open(file_path, "r") as file:
            return json.load(file)
    except json.JSONDecodeError as e:
        logger.error(f"Could not parse trades file for {owner_username}_{platform}: {e}")
        return {}
    except FileNotFoundError:
        return {}

@retry_on_permission_error(max_retries=5)
def save_processed_trade(trade_data, platform):
    """
    Saves the complete and final state of a single trade to the JSON file.
    Uses retry logic to handle Windows file locking issues.
    """
    owner_username = trade_data.get("owner_username", "unknown_user")
    trade_hash = trade_data.get("trade_hash")
    
    if not owner_username or not trade_hash:
        return # Cannot save without these essential keys

    file_path = os.path.join(TRADES_STORAGE_DIR, f"{owner_username}_{platform}.json")
    
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
        
        # Atomic replace - this is where PermissionError typically occurs
        os.replace(temp_file_path, file_path)
    except Exception as e:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass  # Ignore error if temp file can't be removed
        raise e