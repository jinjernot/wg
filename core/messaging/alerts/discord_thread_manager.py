# core/messaging/alerts/discord_thread_manager.py
import requests
import json
import os
import logging
from config import DISCORD_BOT_TOKEN, DISCORD_CHAT_LOG_CHANNEL_ID 

logger = logging.getLogger(__name__)

STATE_FILE_PATH = os.path.join("data", "discord_threads.json")
DISCORD_API_URL = "https://discord.com/api/v10"

def _load_thread_ids():
    """Loads the trade_hash to thread_id mapping from a JSON file."""
    os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
    try:
        with open(STATE_FILE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _save_thread_id(trade_hash, thread_id):
    """Saves a single trade_hash and thread_id to the JSON file."""
    if not trade_hash or not thread_id:
        return
    current_state = _load_thread_ids()
    current_state[str(trade_hash)] = str(thread_id)
    with open(STATE_FILE_PATH, "w") as f:
        json.dump(current_state, f, indent=4)

def get_thread_id(trade_hash):
    """Gets a thread ID for a given trade hash."""
    threads = _load_thread_ids()
    return threads.get(trade_hash)

def create_trade_thread(trade_hash, embed_data):
    """Creates a new message and a thread for it, then returns the thread ID."""
    if not DISCORD_BOT_TOKEN or not DISCORD_CHAT_LOG_CHANNEL_ID:
        logger.error("Discord bot token or chat log channel ID is not configured.")
        return None

    # Check if a thread already exists to avoid duplicates
    existing_thread_id = get_thread_id(trade_hash)
    if existing_thread_id:
        return existing_thread_id

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    
    # 1. Post the initial message (the new trade embed)
    post_message_url = f"{DISCORD_API_URL}/channels/{DISCORD_CHAT_LOG_CHANNEL_ID}/messages"
    payload = {"embeds": [embed_data]}
    
    try:
        response = requests.post(post_message_url, headers=headers, json=payload)
        if response.status_code != 200:
            logger.error(f"Failed to post initial message to create thread: {response.text}")
            return None
        
        message_id = response.json()["id"]

        # 2. Create a thread from that message
        create_thread_url = f"{DISCORD_API_URL}/channels/{DISCORD_CHAT_LOG_CHANNEL_ID}/messages/{message_id}/threads"
        thread_payload = {
            "name": f"Trade Log: {trade_hash}",
            "auto_archive_duration": 1440  # 24 hours
        }
        thread_response = requests.post(create_thread_url, headers=headers, json=thread_payload)
        
        if thread_response.status_code == 201: # 201 Created
            thread_id = thread_response.json()["id"]
            _save_thread_id(trade_hash, thread_id)
            logger.info(f"Successfully created Discord thread {thread_id} for trade {trade_hash}")
            return thread_id
        else:
            logger.error(f"Failed to create thread: {thread_response.text}")
            return None

    except Exception as e:
        logger.error(f"An error occurred while creating Discord thread: {e}")
        return None