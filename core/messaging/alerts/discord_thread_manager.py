import requests
import json
import os
import time
import threading
import tempfile
import logging
from config import DISCORD_BOT_TOKEN, DISCORD_CHAT_LOG_CHANNEL_ID, DISCORD_THREADS_FILE

logger = logging.getLogger(__name__)

STATE_FILE_PATH = str(DISCORD_THREADS_FILE)   # e.g. data/state/discord_threads.json
DISCORD_API_URL = "https://discord.com/api/v10"

# ---------------------------------------------------------------------------
# In-memory cache + synchronisation primitives
# ---------------------------------------------------------------------------
# Maps trade_hash -> thread_id.  Populated eagerly from disk on first use.
_cache: dict = {}
_cache_lock = threading.Lock()          # Guards _cache
_file_lock  = threading.Lock()          # Guards all disk reads/writes
_pending_events: dict = {}              # trade_hash -> threading.Event
_events_lock = threading.Lock()         # Guards _pending_events
_cache_initialized = False


def _ensure_cache_loaded():
    """Loads the JSON file into _cache exactly once, at first access."""
    global _cache_initialized
    with _cache_lock:
        if not _cache_initialized:
            data = _read_file()
            _cache.update(data)
            _cache_initialized = True


def _read_file() -> dict:
    """Reads discord_threads.json from disk (caller must hold _file_lock if needed)."""
    os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
    try:
        with open(STATE_FILE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# Keep the old name available so nothing external that might import it breaks.
def _load_thread_ids() -> dict:
    """Returns the full trade_hash -> thread_id mapping from disk (file-locked)."""
    with _file_lock:
        return _read_file()


def _save_thread_id(trade_hash, thread_id):
    """
    Persists a thread ID to disk (file-locked to prevent corruption) and
    updates the in-memory cache, then signals any threads waiting via
    get_thread_id(wait=True) so they wake up immediately instead of timing out.
    """
    if not trade_hash or not thread_id:
        return

    trade_hash = str(trade_hash)
    thread_id  = str(thread_id)

    # 1. Update in-memory cache first so waiters see it immediately.
    with _cache_lock:
        _cache[trade_hash] = thread_id

    # 2. Persist to disk atomically so readers never see a half-written file.
    #    Write to a temp file in the same directory, then os.replace() which is
    #    atomic on all platforms supported by this project.
    with _file_lock:
        dir_path = os.path.dirname(STATE_FILE_PATH)
        os.makedirs(dir_path, exist_ok=True)
        try:
            with open(STATE_FILE_PATH, "r") as f:
                current_state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            current_state = {}
        current_state[trade_hash] = thread_id
        # Write to a sibling temp file, then atomically swap it into place.
        fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(current_state, f, indent=4)
            os.replace(tmp_path, STATE_FILE_PATH)   # atomic on POSIX & Windows
        except Exception:
            # Clean up the temp file if anything goes wrong.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # 3. Wake up any thread blocked in get_thread_id(wait=True).
    with _events_lock:
        event = _pending_events.get(trade_hash)
        if event:
            event.set()


def get_thread_id(trade_hash, wait=False, timeout=20):
    """
    Returns the Discord thread ID for a given trade hash.

    If wait=True and the ID is not yet cached, blocks (efficiently, via a
    threading.Event) until the ID is saved or timeout is reached — no disk
    polling.
    """
    _ensure_cache_loaded()
    trade_hash = str(trade_hash)

    # Fast path: already in cache.
    with _cache_lock:
        thread_id = _cache.get(trade_hash)
    if thread_id or not wait:
        return thread_id

    # Slow path: register a waiter Event and block until _save_thread_id fires it.
    logger.info(f"Thread ID not found for {trade_hash}, waiting up to {timeout}s...")
    with _events_lock:
        if trade_hash not in _pending_events:
            _pending_events[trade_hash] = threading.Event()
        event = _pending_events[trade_hash]

    fired = event.wait(timeout=timeout)

    with _cache_lock:
        thread_id = _cache.get(trade_hash)

    if fired and thread_id:
        logger.info(f"Thread ID for {trade_hash} found after waiting.")
    else:
        logger.warning(f"Timeout waiting for thread ID for {trade_hash}.")

    return thread_id


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _make_request_with_retry(url, headers, payload, max_retries=3):
    """
    Make a Discord API request with automatic retry on rate limiting (429).
    Uses the retry_after value from the response body; falls back to
    exponential backoff if it cannot be parsed.

    Returns:
        Response object if successful, None otherwise.
    """
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)

            # Success
            if response.status_code in [200, 201]:
                return response

            # Rate limiting
            if response.status_code == 429:
                try:
                    error_data  = response.json()
                    retry_after = float(error_data.get("retry_after", 1.0))
                    code_msg    = f" (code {error_data['code']})" if "code" in error_data else ""
                except (json.JSONDecodeError, KeyError, ValueError):
                    retry_after = 2 ** attempt
                    code_msg    = ""
                logger.warning(
                    f"[RATE LIMIT] Discord API rate limited{code_msg} "
                    f"(attempt {attempt + 1}/{max_retries}). "
                    f"Retrying after {retry_after:.2f}s..."
                )
                time.sleep(retry_after)
                continue

            # Other errors — not retryable
            logger.error(
                f"Discord API request failed with status {response.status_code}: "
                f"{response.text}"
            )
            return None

        except requests.exceptions.Timeout:
            logger.error(
                f"Discord API request timed out (attempt {attempt + 1}/{max_retries})"
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None

        except Exception as e:
            logger.error(f"Error making Discord API request: {e}")
            return None

    logger.error(f"Failed to complete Discord API request after {max_retries} attempts")
    return None


# ---------------------------------------------------------------------------
# Thread creation
# ---------------------------------------------------------------------------

def create_trade_thread(trade_hash, embed_data, max_retries=3):
    """
    Creates a Discord message and a thread attached to it, then saves and
    returns the thread ID.

    Args:
        trade_hash: Unique trade identifier.
        embed_data: Discord embed data for the initial (pinned) message.
        max_retries: Maximum retry attempts for each HTTP call.

    Returns:
        Thread ID (str) if successful, None otherwise.
    """
    if not DISCORD_BOT_TOKEN or not DISCORD_CHAT_LOG_CHANNEL_ID:
        logger.error("Discord bot token or chat log channel ID is not configured.")
        return None

    # Avoid creating duplicate threads.
    existing_thread_id = get_thread_id(trade_hash)
    if existing_thread_id:
        logger.debug(f"Thread already exists for trade {trade_hash}: {existing_thread_id}")
        return existing_thread_id

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}

    # 1. Post the initial message (the new trade embed).
    post_message_url = f"{DISCORD_API_URL}/channels/{DISCORD_CHAT_LOG_CHANNEL_ID}/messages"
    payload = {"embeds": [embed_data]}

    try:
        response = _make_request_with_retry(post_message_url, headers, payload, max_retries)

        if not response or response.status_code != 200:
            logger.error(f"Failed to post initial message for trade {trade_hash}")
            return None

        message_id = response.json()["id"]
        logger.debug(f"Created initial message {message_id} for trade {trade_hash}")

        # 2. Create a thread from that message.
        create_thread_url = (
            f"{DISCORD_API_URL}/channels/{DISCORD_CHAT_LOG_CHANNEL_ID}"
            f"/messages/{message_id}/threads"
        )
        thread_payload = {
            "name": f"Trade Log: {trade_hash}",
            "auto_archive_duration": 1440,  # 24 hours
        }

        thread_response = _make_request_with_retry(
            create_thread_url, headers, thread_payload, max_retries
        )

        if thread_response and thread_response.status_code == 201:
            thread_id = thread_response.json()["id"]
            _save_thread_id(trade_hash, thread_id)  # updates cache + signals waiters
            logger.info(f"Successfully created Discord thread {thread_id} for trade {trade_hash}")
            return thread_id
        else:
            logger.error(f"Failed to create thread for trade {trade_hash}")
            return None

    except Exception as e:
        logger.error(f"Unexpected error creating Discord thread for trade {trade_hash}: {e}")
        return None