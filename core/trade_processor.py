import time
import logging
from api.auth import fetch_token_with_retry
from .get_trade_list import get_trade_list
from .email_checker import get_gmail_service
from .trade import Trade # <-- Import the new Trade class

logger = logging.getLogger(__name__)

def process_trades(account):
    """
    Main loop to fetch and process trades for a given account.
    """
    gmail_service = get_gmail_service()
    if not gmail_service:
        logger.warning("Failed to initialize Gmail service. Email checking will be disabled.")

    while True:
        access_token = fetch_token_with_retry(account)
        if not access_token:
            logger.error(f"Failed to fetch access token for {account['name']}. Retrying in 60s.")
            time.sleep(60)
            continue

        headers = {"Authorization": f"Bearer {access_token}"}
        
        logger.debug(f"Checking for new trades for {account['name']}...")
        trades = get_trade_list(account, headers, limit=10, page=1)

        if trades:
            for trade_data in trades:
                try:
                    # Create a Trade object and process it
                    trade = Trade(trade_data, account, headers, gmail_service)
                    trade.process()
                except Exception as e:
                    logger.error(f"An unexpected error occurred processing trade {trade_data.get('trade_hash')}: {e}", exc_info=True)
        else:
            logger.debug(f"No active trades found for {account['name']}.")

        time.sleep(60)