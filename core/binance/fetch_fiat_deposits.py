"""
Binance Fiat Deposit Fetching
Fetches fiat deposit/payment history from Binance API (SPEI, bank transfers, etc.)
"""
import logging
from core.binance.auth import make_binance_request

logger = logging.getLogger(__name__)

def fetch_fiat_deposit_history_for_user(user, api_key, api_secret, start_time=None, end_time=None, max_retries=5, backoff_factor=1.5):
    """
    Fetch fiat deposit/payment history for a Binance user account
    
    Args:
        user: Username identifier
        api_key: Binance API key
        api_secret: Binance API secret
        start_time: Optional - start timestamp in milliseconds
        end_time: Optional - end timestamp in milliseconds
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
    
    Returns:
        List of fiat deposit records
    """
    # NOTE: Binance has two fiat endpoints:
    # - /sapi/v1/fiat/orders: Pure fiat deposits/withdrawals (bank transfers, SPEI)
    # - /sapi/v1/fiat/payments: Fiat-to-crypto purchases (buying crypto with fiat)
    # This function uses 'payments' to track crypto purchases made with fiat currency
    endpoint = '/sapi/v1/fiat/payments'
    
    all_deposits = []
    page = 1  # Binance fiat API uses 1-based pagination
    rows = 500  # Max allowed by Binance for fiat payments
    
    logger.info(f"Fetching fiat deposit history for {user}...")
    
    while True:
        # Build query parameters
        params = {
            'transactionType': 0,  # 0 = deposit, 1 = withdrawal (integer, not string)
            'page': page,  # Integer page number
            'rows': rows   # Integer rows per page
        }
        
        if start_time:
            params['beginTime'] = int(start_time)
        if end_time:
            params['endTime'] = int(end_time)
            
        data = make_binance_request(
            user, api_key, api_secret, endpoint, params, max_retries, backoff_factor
        )
        
        if data is None:
            # Error is already logged in make_binance_request
            return []
        
        # The response structure is: {"code": "000000", "message": "success", "data": [...], "total": N}
        if data.get('code') != '000000':
            logger.error(f"Binance API error for {user}: {data.get('message', 'Unknown error')}")
            break
        
        deposits = data.get('data', [])
        total_records = data.get('total', 0)
        
        if not deposits:
            logger.info(f"No more fiat deposits found for {user}.")
            break
        
        all_deposits.extend(deposits)
        logger.info(f"Fetched {len(deposits)} fiat deposits (total: {len(all_deposits)}/{total_records})")
        
        # Check if we've fetched all records
        if len(all_deposits) >= total_records:
            logger.info(f"All fiat deposits retrieved for {user}.")
            break
        
        page += 1
    
    logger.info(f"Total fiat deposits fetched for {user}: {len(all_deposits)}")
    return all_deposits
