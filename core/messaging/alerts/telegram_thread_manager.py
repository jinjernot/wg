import json
import os
import logging

logger = logging.getLogger(__name__)

STATE_FILE_PATH = os.path.join("data", "telegram_threads.json")

def _load_message_ids():
    """Loads the trade_hash to initial message_id mapping from a JSON file."""
    os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
    try:
        with open(STATE_FILE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_message_id(trade_hash, message_id):
    """Saves a single trade_hash and message_id to the JSON file."""
    if not trade_hash or not message_id:
        return
    current_state = _load_message_ids()
    current_state[str(trade_hash)] = str(message_id)
    with open(STATE_FILE_PATH, "w") as f:
        json.dump(current_state, f, indent=4)

def get_message_id(trade_hash):
    """Gets the initial message ID for a given trade hash."""
    threads = _load_message_ids()
    return threads.get(trade_hash)

CHAT_STATE_FILE_PATH = os.path.join("data", "telegram_chat_threads.json")

def _load_chat_message_ids():
    """Loads the trade_hash to first chat message_id mapping."""
    os.makedirs(os.path.dirname(CHAT_STATE_FILE_PATH), exist_ok=True)
    try:
        with open(CHAT_STATE_FILE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_chat_message_id(trade_hash, message_id):
    """Saves the first chat message ID for a given trade hash."""
    if not trade_hash or not message_id:
        return
    current_state = _load_chat_message_ids()
    current_state[str(trade_hash)] = str(message_id)
    with open(CHAT_STATE_FILE_PATH, "w") as f:
        json.dump(current_state, f, indent=4)

def get_chat_message_id(trade_hash):
    """Gets the first chat message ID to reply to."""
    threads = _load_chat_message_ids()
    return threads.get(trade_hash)
