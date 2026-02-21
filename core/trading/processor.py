import time
import logging
from core.api.auth import fetch_token_with_retry
from core.api.trade_list import get_trade_list
from core.trading.trade import Trade
from core.utils.adaptive_polling import AdaptivePoller

logger = logging.getLogger(__name__)

def process_trades(account):
    """
    Main loop to fetch and process trades for a given account.
    Uses adaptive polling to reduce API calls during quiet periods.
    """
    # Initialize adaptive poller for this account
    poller = AdaptivePoller(
        base_interval=60,      # Active period: 60s
        quiet_interval=120,    # Quiet period: 120s (50% reduction)
        off_hours_interval=300 # Off-hours: 300s (80% reduction)
    )
    
    failed_auth_attempts = 0
    max_failed_auth = 5  # Stop retrying auth after 5 failures
    
    while True:
        logger.debug(f"--- Starting new trade processing cycle for {account['name']} ---")
        access_token = fetch_token_with_retry(account)
        
        if not access_token:
            failed_auth_attempts += 1
            logger.error(f"Failed to fetch access token for {account['name']} "
                        f"(attempt {failed_auth_attempts}/{max_failed_auth}). Retrying in 60s.")
            
            if failed_auth_attempts >= max_failed_auth:
                logger.critical(f"Max authentication failures reached for {account['name']}. Stopping trade processing.")
                break
            
            time.sleep(60)
            continue
        
        # Reset failed auth counter on success
        failed_auth_attempts = 0

        headers = {"Authorization": f"Bearer {access_token}"}
        
        logger.debug(f"Checking for new trades for {account['name']}...")
        trades = get_trade_list(account, headers, limit=10, page=1, include_completed=True)

        if trades:
            logger.info(f"Found {len(trades)} trades to process for {account['name']}.")
            poller.record_activity(found_trades=True)
            
            for trade_data in trades:
                try:
                    trade = Trade(trade_data, account, headers)
                    trade.process()
                except Exception as e:
                    logger.error(f"An unexpected error occurred processing trade {trade_data.get('trade_hash')}: {e}", exc_info=True)
        else:
            logger.debug(f"No active trades found for {account['name']}.")
            poller.record_activity(found_trades=False)

        # Get adaptive interval based on activity and time of day
        wait_interval = poller.get_interval()
        logger.debug(f"--- Finished trade processing cycle for {account['name']}. Waiting {wait_interval}s... ---")
        time.sleep(wait_interval)