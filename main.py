import threading
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from core.trading.processor import process_trades
from config import PLATFORM_ACCOUNTS, TRADES_STORAGE_DIR
from core.api.offers import set_offer_status, send_scheduled_task_alert
from core.utils.log_config import setup_logging
from core.messaging.alerts.low_balance_alert import check_wallet_balances_and_alert

setup_logging()
logger = logging.getLogger(__name__)


def turn_on_offers_job():
    """Job to be run by the scheduler."""
    logger.info("SCHEDULER: Running scheduled job to turn on offers.")
    send_scheduled_task_alert("Automatically turning on all offers.")

    results = set_offer_status(turn_on=True)

    successful_accounts = [r["account"] for r in results if r["success"]]
    if successful_accounts:
        success_message = f"Offers turned on for: {', '.join(successful_accounts)}."
        logger.info(f"SCHEDULER: {success_message}")
        send_scheduled_task_alert(success_message)

    failed_accounts = [
        f"{r['account']} ({r['error']})" for r in results if not r["success"]]
    if failed_accounts:
        failure_message = f"Failed to turn on offers for: {', '.join(failed_accounts)}."
        logger.error(f"SCHEDULER: {failure_message}")
        send_scheduled_task_alert(failure_message)


def turn_off_offers_job():
    """Job to be run by the scheduler to turn off offers."""
    logger.info("SCHEDULLER: Running scheduled job to turn off offers.")
    send_scheduled_task_alert("Automatically turning off all offers.")

    results = set_offer_status(turn_on=False)

    successful_accounts = [r["account"] for r in results if r["success"]]
    if successful_accounts:
        success_message = f"Offers turned off for: {', '.join(successful_accounts)}."
        logger.info(f"SCHEDULER: {success_message}")
        send_scheduled_task_alert(success_message)

    failed_accounts = [
        f"{r['account']} ({r['error']})" for r in results if not r["success"]]
    if failed_accounts:
        failure_message = f"Failed to turn off offers for: {', '.join(failed_accounts)}."
        logger.error(f"SCHEDULER: {failure_message}")
        send_scheduled_task_alert(failure_message)


def main():

    if not os.path.exists(TRADES_STORAGE_DIR):
        logger.info(
            f"Creating trade storage directory at: {TRADES_STORAGE_DIR}")
        os.makedirs(TRADES_STORAGE_DIR)

    logger.info("Performing initial wallet balance check on startup...")
    check_wallet_balances_and_alert()

    scheduler = BackgroundScheduler(timezone='America/Mexico_City')
    scheduler.add_job(turn_on_offers_job, 'cron', hour=8, minute=0)
    scheduler.add_job(turn_off_offers_job, 'cron', hour=2, minute=0)
    scheduler.add_job(check_wallet_balances_and_alert, 'interval', minutes=30)
    scheduler.start()
    logger.info(
        "Scheduler started. Offers will be turned on daily at 8:00 AM and off at 2:00 AM Central Time.")

    threads = []
    for account in ACCOUNTS:
        # --- ADDED TEMPORARY CHECK ---
        if "_Paxful" in account.get("name", ""):
            logger.warning(f"Temporarily skipping all processing for Paxful account: {account.get('name')}")
            continue
        # --- END OF CHECK ---
            
        thread = threading.Thread(target=process_trades, args=(account,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()