import threading
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from core.trade_processor import process_trades
from config import ACCOUNTS
from core.offer_manager import set_offer_status, send_scheduled_task_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def turn_on_offers_job():
    """Job to be run by the scheduler."""
    logging.info("SCHEDULER: Running scheduled job to turn on offers.")
    send_scheduled_task_alert("☀️ **Good Morning!**\nAutomatically turning on all offers.")
    
    results = set_offer_status(turn_on=True)
    
    successful_accounts = [r["account"] for r in results if r["success"]]
    if successful_accounts:
        success_message = f"✅ Offers turned on for: {', '.join(successful_accounts)}."
        logging.info(f"SCHEDULER: {success_message}")
        send_scheduled_task_alert(success_message)

    failed_accounts = [f"{r['account']} ({r['error']})" for r in results if not r["success"]]
    if failed_accounts:
        failure_message = f"❌ Failed to turn on offers for: {', '.join(failed_accounts)}."
        logging.error(f"SCHEDULER: {failure_message}")
        send_scheduled_task_alert(failure_message)

def main():
    # --- SCHEDULER SETUP ---
    scheduler = BackgroundScheduler(timezone='America/Mexico_City')
    # Schedule the job to run every day at 7:00 AM
    scheduler.add_job(turn_on_offers_job, 'cron', hour=7, minute=0)
    scheduler.start()
    logging.info("Scheduler started. Offers will be turned on daily at 7:00 AM Central Time.")
    
    # --- TRADE PROCESSOR THREADS ---
    threads = []
    for account in ACCOUNTS:
        thread = threading.Thread(target=process_trades, args=(account,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

if __name__ == "__main__":
    main()