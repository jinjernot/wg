# main.py
import threading
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from core.trading.processor import process_trades
from config import ACCOUNTS, TRADE_STORAGE_DIR
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

    failed_accounts = [f"{r['account']} ({r['error']})" for r in results if not r["success"]]
    if failed_accounts:
        failure_message = f"Failed to turn on offers for: {', '.join(failed_accounts)}."
        logger.error(f"SCHEDULER: {failure_message}")
        send_scheduled_task_alert(failure_message)

def main():
    # --- ENSURE DIRECTORY EXISTS ---
    if not os.path.exists(TRADE_STORAGE_DIR):
        logger.info(f"Creating trade storage directory at: {TRADE_STORAGE_DIR}")
        os.makedirs(TRADE_STORAGE_DIR)
    # -----------------------------

    scheduler = BackgroundScheduler(timezone='America/Mexico_City')
    # Schedule the job to run every day at 7:00 AM
    scheduler.add_job(turn_on_offers_job, 'cron', hour=7, minute=0)
    scheduler.add_job(check_wallet_balances_and_alert, 'interval', minutes=30)
    scheduler.start()
    logger.info("Scheduler started. Offers will be turned on daily at 7:00 AM Central Time.")

    threads = []
    for account in ACCOUNTS:
        thread = threading.Thread(target=process_trades, args=(account,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()