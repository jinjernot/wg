import time
import logging
from core.api.auth import fetch_token_with_retry
from core.api.trade_list import get_trade_list
from core.trading.trade import Trade
from .trade import Trade

logger = logging.getLogger(__name__)

def process_trades(account):
    """
    Main loop to fetch and process trades for a given account.
    """
    while True:
        logger.info(f"--- Starting new trade processing cycle for {account['name']} ---")
        access_token = fetch_token_with_retry(account)
        if not access_token:
            logger.error(f"Failed to fetch access token for {account['name']}. Retrying in 60s.")
            time.sleep(60)
            continue

        headers = {"Authorization": f"Bearer {access_token}"}
        
        logger.debug(f"Checking for new trades for {account['name']}...")
        trades = get_trade_list(account, headers, limit=10, page=1, include_completed=True)

        if trades:
            logger.info(f"Found {len(trades)} trades to process for {account['name']}.")
            for trade_data in trades:
                try:
                    trade = Trade(trade_data, account, headers)
                    trade.process()
                except Exception as e:
                    logger.error(f"An unexpected error occurred processing trade {trade_data.get('trade_hash')}: {e}", exc_info=True)
        else:
            logger.debug(f"No active trades found for {account['name']}.")

        logger.info(f"--- Finished trade processing cycle for {account['name']}. Waiting... ---")
        time.sleep(60)