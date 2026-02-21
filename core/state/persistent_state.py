import json
import os
import threading
import logging

logger = logging.getLogger(__name__)

STATE_FILE_PATH = os.path.join("data", "chat_state.json")
_state_lock = threading.Lock()


def load_last_message_ids():
    """Loads the last processed message IDs from a JSON file."""
    # Ensure the directory exists
    os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)

    try:
        with open(STATE_FILE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("Chat state file not found or is invalid. Starting with a fresh state.")
        return {}


def save_last_message_id(trade_hash, message_id):
    """Saves a single last processed message ID to the JSON file."""
    if not trade_hash or not message_id:
        return

    with _state_lock:
        current_state = load_last_message_ids()
        current_state[str(trade_hash)] = str(message_id)

        try:
            with open(STATE_FILE_PATH, "w") as f:
                json.dump(current_state, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save chat state to {STATE_FILE_PATH}: {e}")