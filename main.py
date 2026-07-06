import threading
import logging
import os
import sys
import time
import shutil
import signal
from apscheduler.schedulers.background import BackgroundScheduler
from core.trading.processor import process_trades, get_thread_heartbeats
from config import PLATFORM_ACCOUNTS, TRADES_STORAGE_DIR
from core.api.offers import set_offer_status, send_scheduled_task_alert
from core.utils.log_config import setup_logging
from core.messaging.alerts.low_balance_alert import check_wallet_balances_and_alert
from core.messaging.alerts.telegram_alert import send_bot_online_alert, send_bot_offline_alert
from core.utils.connection_guard import wait_for_internet
from core.utils.startup_checks import validate_config
from core.binance.email_monitor import check_binance_emails

setup_logging()
logger = logging.getLogger(__name__)

# Restart backoff settings
_RESTART_BACKOFF_INITIAL = 30   # seconds before first restart attempt
_RESTART_BACKOFF_FACTOR  = 2
_RESTART_BACKOFF_MAX     = 300  # cap at 5 minutes

# How long a thread can be silent before we treat it as deadlocked
_DEADLOCK_TIMEOUT = 10 * 60    # 10 minutes

# Disk space alert threshold
_DISK_WARN_MB = 500            # warn when free space drops below 500 MB


# =============================================================================
# Safety hooks — installed once at module level
# =============================================================================

def _handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Catch any exception that escapes all try/except blocks."""
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical(
        "Uncaught exception — process will exit.",
        exc_info=(exc_type, exc_value, exc_traceback)
    )
    try:
        send_bot_offline_alert(reason=f"Fatal uncaught exception: {exc_value}")
    except Exception:
        pass

sys.excepthook = _handle_uncaught_exception


def _handle_sigterm(signum, frame):
    """Graceful shutdown when OS/NSSM sends SIGTERM."""
    logger.info("Received SIGTERM — initiating graceful shutdown.")
    try:
        send_bot_offline_alert(reason="Graceful shutdown (SIGTERM received)")
    except Exception:
        pass
    raise SystemExit(0)

signal.signal(signal.SIGTERM, _handle_sigterm)


def _toggle_offers_job(turn_on: bool):
    """Shared implementation for turning offers on or off."""
    verb = "on" if turn_on else "off"
    logger.info(f"SCHEDULER: Running scheduled job to turn {verb} offers.")
    send_scheduled_task_alert(f"Automatically turning {verb} all offers.")

    results = set_offer_status(turn_on=turn_on)

    successful_accounts = [r["account"] for r in results if r["success"]]
    if successful_accounts:
        success_message = f"Offers turned {verb} for: {', '.join(successful_accounts)}."
        logger.info(f"SCHEDULER: {success_message}")
        send_scheduled_task_alert(success_message)

    failed_accounts = [
        f"{r['account']} ({r['error']})" for r in results if not r["success"]]
    if failed_accounts:
        failure_message = f"Failed to turn {verb} offers for: {', '.join(failed_accounts)}."
        logger.error(f"SCHEDULER: {failure_message}")
        send_scheduled_task_alert(failure_message)


def turn_on_offers_job():
    """Scheduler entry-point: turn all offers on."""
    _toggle_offers_job(turn_on=True)


def turn_off_offers_job():
    """Scheduler entry-point: turn all offers off."""
    _toggle_offers_job(turn_on=False)


def check_disk_space_job():
    """Alerts via Telegram if free disk space drops below _DISK_WARN_MB."""
    try:
        usage = shutil.disk_usage("/")
        free_mb = usage.free / (1024 * 1024)
        if free_mb < _DISK_WARN_MB:
            msg = (
                f"💾 Low disk space on trading server: "
                f"{free_mb:.0f} MB free (threshold: {_DISK_WARN_MB} MB). "
                "Consider cleaning logs or attachments."
            )
            logger.error(msg)
            send_scheduled_task_alert(msg)
        else:
            logger.debug(f"[DiskCheck] Free space OK: {free_mb:.0f} MB")
    except Exception as e:
        logger.warning(f"[DiskCheck] Could not check disk space: {e}")



def main():

    if not os.path.exists(TRADES_STORAGE_DIR):
        logger.info(
            f"Creating trade storage directory at: {TRADES_STORAGE_DIR}")
        os.makedirs(TRADES_STORAGE_DIR)

    try:
        send_bot_online_alert()
    except Exception as e:
        logger.error(f"Failed to send bot online alert: {e}")

    try:
        logger.info("Performing initial wallet balance check on startup...")
        check_wallet_balances_and_alert()

        logger.info("Performing initial Binance email check on startup...")
        try:
            check_binance_emails()
        except Exception as e:
            logger.error(f"Failed to perform initial Binance email check: {e}")

        from core.messaging.alerts.promoted_leaderboard_alert import check_promoted_leaderboard_and_alert
        from core.trading.dynamic_pricing import update_dynamic_pricing_job, send_market_status_report, send_hourly_market_report

        logger.info("Running initial dynamic pricing update and market status report on startup...")
        try:
            update_dynamic_pricing_job()
            send_market_status_report()
        except Exception as e:
            logger.error(f"Failed to perform initial startup pricing/report check: {e}")

        scheduler = BackgroundScheduler(timezone='America/Mexico_City')
        scheduler.add_job(turn_on_offers_job, 'cron', hour=8, minute=30)
        scheduler.add_job(turn_off_offers_job, 'cron', hour=2, minute=0)
        scheduler.add_job(check_wallet_balances_and_alert, 'interval', minutes=30)
        scheduler.add_job(check_disk_space_job, 'interval', hours=1)
        scheduler.add_job(check_binance_emails, 'interval', seconds=30)
        scheduler.add_job(check_promoted_leaderboard_and_alert, 'interval', minutes=3)
        scheduler.add_job(update_dynamic_pricing_job, 'interval', minutes=5)
        scheduler.add_job(send_market_status_report, 'interval', hours=4)
        scheduler.add_job(send_hourly_market_report, 'interval', hours=1)
        scheduler.start()
        logger.info(
            "Scheduler started. Offers will be turned on daily at 8:30 AM and off at 2:00 AM Central Time.")

        # --- Trading thread registry --- 
        # Keyed by account name so the watchdog can respawn individual threads.
        trading_threads: dict[str, tuple[threading.Thread, dict]] = {}
        for account in PLATFORM_ACCOUNTS:
            t = threading.Thread(
                target=process_trades,
                args=(account,),
                daemon=True,
                name=f"trader-{account['name']}"
            )
            t.start()
            trading_threads[account["name"]] = (t, account)
            logger.info(f"[Watchdog] Started trading thread for {account['name']}.")

        # --- Watchdog loop (replaces thread.join()) ---
        # Checks every 60 s, respawns dead threads, and detects deadlocked ones.
        logger.info("[Watchdog] Thread watchdog is active.")
        while True:
            time.sleep(60)
            heartbeats = get_thread_heartbeats()

            for account_name, (thread, account) in list(trading_threads.items()):
                if not thread.is_alive():
                    logger.error(
                        f"[Watchdog] Trading thread for '{account_name}' has died — restarting."
                    )
                    try:
                        send_scheduled_task_alert(
                            f"⚠️ [{account_name}] trading thread died unexpectedly. Auto-restarting."
                        )
                    except Exception:
                        pass
                    new_thread = threading.Thread(
                        target=process_trades,
                        args=(account,),
                        daemon=True,
                        name=f"trader-{account_name}"
                    )
                    new_thread.start()
                    trading_threads[account_name] = (new_thread, account)
                    logger.info(f"[Watchdog] Restarted trading thread for '{account_name}'.")

                else:
                    # Deadlock check — thread alive but not making progress
                    last_seen = heartbeats.get(thread.name, 0)
                    if last_seen > 0:  # 0 means thread hasn't stamped yet (just started)
                        silent_for = time.time() - last_seen
                        if silent_for > _DEADLOCK_TIMEOUT:
                            logger.critical(
                                f"[Watchdog] Thread '{account_name}' appears DEADLOCKED "
                                f"(no heartbeat for {silent_for / 60:.1f}m). "
                                "Triggering full process restart."
                            )
                            try:
                                send_scheduled_task_alert(
                                    f"🔴 [{account_name}] trading thread is deadlocked "
                                    f"({silent_for / 60:.0f}m silent). Restarting process."
                                )
                            except Exception:
                                pass
                            # Can't kill individual Python threads cleanly;
                            # raise to trigger the outer restart loop.
                            raise RuntimeError(
                                f"Deadlock detected in thread '{account_name}' — "
                                "forcing process restart."
                            )

    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt).")
        try:
            send_bot_offline_alert(reason="Manual shutdown")
        except Exception as e:
            logger.error(f"Failed to send bot offline alert: {e}")
        raise  # Re-raise so the outer loop knows it was intentional
    except Exception as e:
        logger.critical(f"Bot crashed: {e}", exc_info=True)
        try:
            send_bot_offline_alert(reason=f"Crash: {e}")
        except Exception as alert_err:
            logger.error(f"Failed to send bot offline alert: {alert_err}")
        raise


if __name__ == "__main__":
    validate_config()  # Fail fast if env vars are missing

    restart_count = 0
    backoff = _RESTART_BACKOFF_INITIAL

    while True:
        try:
            main()
            # main() returned cleanly (only happens on clean KeyboardInterrupt re-raise)
            logger.info("Trading bot exited cleanly.")
            break

        except KeyboardInterrupt:
            logger.info("Trading bot stopped by user. Exiting.")
            break

        except Exception as e:
            restart_count += 1
            logger.critical(
                f"Trading bot crashed (restart #{restart_count}): {e}. "
                f"Will restart in {backoff}s.",
                exc_info=True
            )

            # Wait for internet before restarting (outage scenario)
            logger.info("Checking internet connectivity before restarting...")
            wait_for_internet(retry_interval=30, label="TradingBot")

            logger.info(f"Restarting trading bot in {backoff}s (restart #{restart_count + 1})...")
            time.sleep(backoff)
            backoff = min(backoff * _RESTART_BACKOFF_FACTOR, _RESTART_BACKOFF_MAX)