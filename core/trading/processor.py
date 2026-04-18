import time
import threading
import logging
from core.api.auth import fetch_token_with_retry
from core.api.trade_list import get_trade_list
from core.trading.trade import Trade
from core.utils.adaptive_polling import AdaptivePoller
from core.api.offers import send_scheduled_task_alert

logger = logging.getLogger(__name__)

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

            for trade_data in trades:
                try:
                    trade = Trade(trade_data, account, headers)
                    trade.process()
                except Exception as e:
                    logger.error(
                        f"An unexpected error occurred processing trade "
                        f"{trade_data.get('trade_hash')}: {e}", exc_info=True
                    )
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