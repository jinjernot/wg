import json
import os
import shutil
import time
import threading
import logging
import copy
from config import TRADES_STORAGE_DIR

logger = logging.getLogger(__name__)

# In-memory authoritative cache: { "owner_username_platform": { "trade_hash": { ... } } }
_mem_cache = {}
# Lock to protect _mem_cache
_cache_lock = threading.Lock()
# Set of dirtied cache keys that need flushing to disk
_dirty_keys = set()
# Event to wake up the background flusher thread
_flush_event = threading.Event()

def load_processed_trades(owner_username, platform):
    """Loads all processed trades for a specific user and platform, using in-memory cache."""
    cache_key = f"{owner_username}_{platform}"
    
    with _cache_lock:
        if cache_key in _mem_cache:
            return copy.deepcopy(_mem_cache[cache_key])
            
    # Not in cache, load from disk
    file_path = os.path.join(TRADES_STORAGE_DIR, f"{cache_key}.json")
    data = {}
    try:
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, "r") as file:
                data = json.load(file)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        
    with _cache_lock:
        if cache_key not in _mem_cache:
            _mem_cache[cache_key] = data
        return copy.deepcopy(_mem_cache[cache_key])

def save_processed_trade(trade_data, platform):
    """Saves the complete state of a trade by updating the memory cache and triggering an async flush."""
    owner_username = trade_data.get("owner_username")
    trade_hash = trade_data.get("trade_hash")
    if not owner_username or not trade_hash:
        return

    cache_key = f"{owner_username}_{platform}"
    
    with _cache_lock:
        if cache_key not in _mem_cache:
            _mem_cache[cache_key] = {}
        
        # Check if data actually changed to prevent useless disk writes
        if _mem_cache[cache_key].get(trade_hash) == trade_data:
            return
            
        _mem_cache[cache_key][trade_hash] = copy.deepcopy(trade_data)
        _dirty_keys.add(cache_key)
        
    # Wake up the flusher thread
    _flush_event.set()

def _flusher_loop():
    """Background thread that periodically writes dirtied state to disk safely."""
    while True:
        # Wait until awakened by a save, or fallback flush every 5 seconds
        _flush_event.wait(timeout=5.0)
        _flush_event.clear()
        
        # Gather dirtied data quickly under the lock
        to_flush = {}
        with _cache_lock:
            for key in _dirty_keys:
                to_flush[key] = copy.deepcopy(_mem_cache[key])
            _dirty_keys.clear()
            
        if not to_flush:
            continue
            
        # Write to disk completely outside of the lock
        for key, data in to_flush.items():
            file_path = os.path.join(TRADES_STORAGE_DIR, f"{key}.json")
            temp_file_path = file_path + ".tmp"
            try:
                with open(temp_file_path, "w") as file:
                    json.dump(data, file, indent=4)
                    file.flush()
                    os.fsync(file.fileno())
                
                # Retry replace for Windows antivirus locks
                for attempt in range(5):
                    try:
                        os.replace(temp_file_path, file_path)
                        break
                    except PermissionError:
                        if attempt == 4:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            shutil.move(temp_file_path, file_path)
                        time.sleep(0.1 * (2**attempt))
            except Exception as e:
                logger.error(f"Error asynchronously flushing state for {key}: {e}")

# Start the background flusher thread once on module import
_flusher_thread = threading.Thread(target=_flusher_loop, daemon=True, name="StateFlusher")
_flusher_thread.start()