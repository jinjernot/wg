"""
Binance Deposit Fetching
Fetches deposit history from Binance API with retry logic and pagination
"""
import logging
from core.binance.auth import make_binance_request

logger = logging.getLogger(__name__)

def fetch_deposit_history_for_user(user, api_key, api_secret, coin=None, start_time=None, end_time=None, max_retries=5, backoff_factor=1.5):
    """
    Fetch deposit history for a Binance user account
    
    Args:
        user: Username identifier
        api_key: Binance API key
        api_secret: Binance API secret
        coin: Optional - filter by specific cryptocurrency
        start_time: Optional - start timestamp in milliseconds
        end_time: Optional - end timestamp in milliseconds
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
    
    Returns:
        List of deposit records
    """
    endpoint = '/sapi/v1/capital/deposit/hisrec'
    
    all_deposits = []
    offset = 0
    limit = 1000  # Max allowed by Binance
    
    logger.info(f"Fetching deposit history for {user}...")
    
    while True:
        # Build query parameters
        params = {'limit': limit, 'offset': offset}
        
        if coin:
            params['coin'] = coin
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time
            
        deposits = make_binance_request(
            user, api_key, api_secret, endpoint, params, max_retries, backoff_factor
        )
        
        if deposits is None:
            # Error is already logged in make_binance_request
            return []
        
        if not deposits:
            logger.info(f"No more deposits found for {user}.")
            break
        
        all_deposits.extend(deposits)
        logger.info(f"Fetched {len(deposits)} deposits (total: {len(all_deposits)})")
        
        # Check if we got fewer results than the limit (last page)
        if len(deposits) < limit:
            logger.info(f"Final page reached for {user}.")
            break
        
        offset += limit
    
    logger.info(f"Total deposits fetched for {user}: {len(all_deposits)}")
    return all_deposits
