import os
import json
import time
import logging
from config import PAYMENT_ACCOUNTS_PATH
from core.utils.web_utils import get_app_settings

logger = logging.getLogger(__name__)

CACHE_TTL = 10  # seconds

_app_settings_cache = {
    "data": None,
    "timestamp": 0
}

_payment_data_cache = {}

def get_cached_app_settings():
    """
    Returns app settings from cache. Reloads from disk if older than CACHE_TTL.
    """
    now = time.time()
    if _app_settings_cache["data"] is None or (now - _app_settings_cache["timestamp"]) > CACHE_TTL:
        _app_settings_cache["data"] = get_app_settings()
        _app_settings_cache["timestamp"] = now
    return _app_settings_cache["data"]

def get_cached_payment_account(json_filename):
    """
    Returns payment account data from cache. Reloads from disk if older than CACHE_TTL.
    """
    now = time.time()
    
    # Check if cached and fresh
    if json_filename in _payment_data_cache:
        cache_entry = _payment_data_cache[json_filename]
        if (now - cache_entry["timestamp"]) <= CACHE_TTL:
            return cache_entry["data"]

    # Load from disk
    json_path = os.path.join(PAYMENT_ACCOUNTS_PATH, json_filename)
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Could not read or parse {json_filename}: {e}")
        data = None
        
    _payment_data_cache[json_filename] = {
        "data": data,
        "timestamp": now
    }
    return data
