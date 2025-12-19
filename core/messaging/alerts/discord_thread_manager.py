import requests
import json
import os
import time
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

def _make_request_with_retry(url, headers, payload, max_retries=3):
    """
    Make a Discord API request with exponential backoff for rate limiting.
    
    Args:
        url: The API endpoint URL
        headers: Request headers
        payload: Request payload (JSON)
        max_retries: Maximum number of retry attempts
    
    Returns:
        Response object if successful, None otherwise
    """
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            
            # Success
            if response.status_code in [200, 201]:
                return response
            
            # Rate limiting (429 or error code 40062)
            if response.status_code == 429:
                try:
                    error_data = response.json()
                    retry_after = error_data.get("retry_after", 1)
                    
                    # Check for specific error code 40062 (thread creation rate limit)
                    if error_data.get("code") == 40062:
                        logger.warning(
                            f"Discord thread creation rate limit hit (40062). "
                            f"Waiting {retry_after} seconds before retry (attempt {attempt + 1}/{max_retries})"
                        )
                    else:
                        logger.warning(
                            f"Discord API rate limit (429). "
                            f"Waiting {retry_after} seconds before retry (attempt {attempt + 1}/{max_retries})"
                        )
                    
                    # Wait for the specified retry_after duration
                    time.sleep(retry_after)
                    continue
                    
                except (json.JSONDecodeError, KeyError):
                    # If we can't parse the retry_after, use exponential backoff
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited but couldn't parse retry_after. Waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
            
            # Other errors
            logger.error(f"Discord API request failed with status {response.status_code}: {response.text}")
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"Discord API request timed out (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
            
        except Exception as e:
            logger.error(f"Error making Discord API request: {e}")
            return None
    
    logger.error(f"Failed to complete Discord API request after {max_retries} attempts")
    return None

def create_trade_thread(trade_hash, embed_data, max_retries=3):
    """
    Creates a new message and a thread for it, then returns the thread ID.
    Includes rate limiting protection and retry logic.
    
    Args:
        trade_hash: Unique trade identifier
        embed_data: Discord embed data for the initial message
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        Thread ID if successful, None otherwise
    """
    if not DISCORD_BOT_TOKEN or not DISCORD_CHAT_LOG_CHANNEL_ID:
        logger.error("Discord bot token or chat log channel ID is not configured.")
        return None

    # Check if a thread already exists to avoid duplicates
    existing_thread_id = get_thread_id(trade_hash)
    if existing_thread_id:
        logger.debug(f"Thread already exists for trade {trade_hash}: {existing_thread_id}")
        return existing_thread_id

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    
    # 1. Post the initial message (the new trade embed)
    post_message_url = f"{DISCORD_API_URL}/channels/{DISCORD_CHAT_LOG_CHANNEL_ID}/messages"
    payload = {"embeds": [embed_data]}
    
    try:
        response = _make_request_with_retry(post_message_url, headers, payload, max_retries)
        
        if not response or response.status_code != 200:
            logger.error(f"Failed to post initial message for trade {trade_hash}")
            return None
        
        message_id = response.json()["id"]
        logger.debug(f"Created initial message {message_id} for trade {trade_hash}")

        # 2. Create a thread from that message with rate limit protection
        create_thread_url = f"{DISCORD_API_URL}/channels/{DISCORD_CHAT_LOG_CHANNEL_ID}/messages/{message_id}/threads"
        thread_payload = {
            "name": f"Trade Log: {trade_hash}",
            "auto_archive_duration": 1440  # 24 hours
        }
        
        thread_response = _make_request_with_retry(create_thread_url, headers, thread_payload, max_retries)
        
        if thread_response and thread_response.status_code == 201:
            thread_id = thread_response.json()["id"]
            _save_thread_id(trade_hash, thread_id)
            logger.info(f"Successfully created Discord thread {thread_id} for trade {trade_hash}")
            return thread_id
        else:
            logger.error(f"Failed to create thread for trade {trade_hash}")
            return None

    except Exception as e:
        logger.error(f"Unexpected error creating Discord thread for trade {trade_hash}: {e}")
        return None