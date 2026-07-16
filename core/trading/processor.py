import time
import threading
import logging
import atexit
from concurrent.futures import ThreadPoolExecutor
from core.api.auth import fetch_token_with_retry
from core.api.trade_list import get_trade_list
from core.trading.trade import Trade
from core.utils.adaptive_polling import AdaptivePoller
from core.messaging.alerts.telegram_alert import send_scheduled_task_alert
from core.state.trade_state_loader import load_processed_trades

logger = logging.getLogger(__name__)

# Concurrency controls to prevent parallel runs of the same trade
_active_processing_hashes = set()
_active_processing_lock = threading.Lock()

# Thread pool for existing trade processing.
# Kept intentionally small: fewer concurrent writers means less contention on
# the _lock in trade_state_loader, which was causing the main thread to block
# long enough to trip the watchdog's 10-minute deadlock timeout.
_existing_trade_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="existing-trader")
atexit.register(_existing_trade_executor.shutdown, wait=True, cancel_futures=False)

# How long to pause before retrying after a run of consecutive auth failures
AUTH_BACKOFF_SECONDS = 5 * 60  # 5 minutes
MAX_FAILED_AUTH = 5

# --- Thread heartbeat registry ---
# Keyed by thread name; updated at the start of every poll cycle.
# The watchdog in main.py reads this to detect deadlocked threads.
_heartbeats: dict[str, float] = {}
_heartbeat_lock = threading.Lock()


def get_thread_heartbeats() -> dict[str, float]:
    """Returns a snapshot of {thread_name: last_seen_timestamp} for all trading threads."""
    with _heartbeat_lock:
        return dict(_heartbeats)


def process_trades(account):
    """
    Main loop to fetch and process trades for a given account.
    Uses adaptive polling to reduce API calls during quiet periods.
    Never exits permanently — if authentication fails repeatedly it
    backs off for AUTH_BACKOFF_SECONDS and then retries indefinitely.
    """
    poller = AdaptivePoller(
        base_interval=15,      # Active period: 15s — fast new-trade detection
        quiet_interval=30,     # Quiet period: 30s (still very responsive)
        off_hours_interval=60  # Off-hours (2-7 AM): 60s max
    )

    failed_auth_attempts = 0

    thread_name = threading.current_thread().name

    while True:
        # Stamp heartbeat at the top of every cycle so the watchdog can
        # detect threads that are alive but frozen (deadlocked).
        with _heartbeat_lock:
            _heartbeats[thread_name] = time.time()

        logger.debug(f"--- Starting new trade processing cycle for {account['name']} ---")
        access_token = fetch_token_with_retry(account)

        if not access_token:
            failed_auth_attempts += 1
            logger.error(
                f"Failed to fetch access token for {account['name']} "
                f"(attempt {failed_auth_attempts}/{MAX_FAILED_AUTH})."
            )

            if failed_auth_attempts >= MAX_FAILED_AUTH:
                # Don't exit — alert and back off, then reset and keep trying
                alert_msg = (
                    f"⚠️ [{account['name']}] {MAX_FAILED_AUTH} consecutive auth failures. "
                    f"Pausing for {AUTH_BACKOFF_SECONDS // 60} minutes before retrying."
                )
                logger.critical(alert_msg)
                try:
                    send_scheduled_task_alert(alert_msg)
                except Exception as e:
                    logger.error(f"Failed to send auth-failure alert: {e}")

                time.sleep(AUTH_BACKOFF_SECONDS)
                failed_auth_attempts = 0  # Reset so recovery is clean
                logger.info(f"[{account['name']}] Resuming after auth backoff.")
                continue

            time.sleep(60)
            continue

        # Reset failed auth counter on success
        failed_auth_attempts = 0

        headers = {"Authorization": f"Bearer {access_token}"}

        logger.debug(f"Checking for new trades for {account['name']}...")
        trades = get_trade_list(account, headers, limit=100, page=1, include_completed=True)

        if trades:
            logger.info(f"Found {len(trades)} trades to process for {account['name']}.")
            poller.record_activity(found_trades=True)

            # Local cache for loaded trade states to avoid redundant disk reads
            loaded_trades_cache = {}

            trade_objects = []
            for trade_data in trades:
                try:
                    owner_username = trade_data.get("owner_username", "unknown_user")
                    if owner_username not in loaded_trades_cache:
                        loaded_trades_cache[owner_username] = load_processed_trades(owner_username, "Noones")
                    
                    trade = Trade(
                        trade_data, account, headers,
                        loaded_trades=loaded_trades_cache[owner_username]
                    )
                    trade_objects.append(trade)
                except Exception as e:
                    logger.error(f"Error instantiating Trade object: {e}")

            # Separate into new and existing trades
            new_trades = []
            existing_trades = []
            for trade in trade_objects:
                is_new = 'first_seen_utc' not in trade.trade_state
                if is_new:
                    new_trades.append(trade)
                else:
                    # Only process existing trade if it's not already running
                    with _active_processing_lock:
                        if trade.trade_hash not in _active_processing_hashes:
                            existing_trades.append(trade)

            # 1. Process new trades synchronously and sequentially in the main thread
            # This ensures welcome messages are sent immediately without latency.
            for trade in new_trades:
                with _active_processing_lock:
                    if trade.trade_hash in _active_processing_hashes:
                        logger.warning(f"New trade {trade.trade_hash} is already processing. Skipping.")
                        continue
                    _active_processing_hashes.add(trade.trade_hash)

                # Stamp heartbeat BEFORE processing each trade so the watchdog
                # never sees a 10-minute silence even when many new trades arrive
                # in one cycle (each one can take several seconds to process).
                with _heartbeat_lock:
                    _heartbeats[thread_name] = time.time()

                try:
                    logger.info(f"Processing new trade {trade.trade_hash} synchronously in main thread.")
                    trade.process()
                except Exception as e:
                    logger.error(f"Error processing new trade {trade.trade_hash}: {e}", exc_info=True)
                finally:
                    # Stamp heartbeat again after the trade is done so a slow
                    # trade.process() call doesn't eat into the watchdog budget.
                    with _heartbeat_lock:
                        _heartbeats[thread_name] = time.time()
                    with _active_processing_lock:
                        _active_processing_hashes.discard(trade.trade_hash)

            # 2. Process existing trades in background thread pool to avoid blocking the main thread.
            def _run_existing_trade(t):
                try:
                    logger.debug(f"Starting background processing for trade {t.trade_hash}.")
                    t.process()
                except Exception as ex:
                    logger.error(f"Error processing existing trade {t.trade_hash} in background: {ex}", exc_info=True)
                finally:
                    with _active_processing_lock:
                        _active_processing_hashes.discard(t.trade_hash)

            for trade in existing_trades:
                with _active_processing_lock:
                    _active_processing_hashes.add(trade.trade_hash)
                logger.info(f"Submitting existing trade {trade.trade_hash} to background pool.")
                _existing_trade_executor.submit(_run_existing_trade, trade)

        else:
            logger.debug(f"No active trades found for {account['name']}.")
            poller.record_activity(found_trades=False)

        # Get adaptive interval based on activity and time of day
        wait_interval = poller.get_interval()
        logger.debug(
            f"--- Finished trade processing cycle for {account['name']}. "
            f"Waiting {wait_interval}s... ---"
        )
        time.sleep(wait_interval)