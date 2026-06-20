"""
Binance Fiat Orders Fetching
Fetches pure fiat deposit/withdrawal orders from Binance API (SPEI, bank transfers)
This is different from fiat/payments which is for fiat-to-crypto purchases
"""
import logging
from core.binance.auth import make_binance_request

logger = logging.getLogger(__name__)

def fetch_fiat_orders_for_user(user, api_key, api_secret, start_time=None, end_time=None, max_retries=5, backoff_factor=1.5):
    """
    Fetch pure fiat deposit/withdrawal orders for a Binance user account
    This endpoint captures SPEI bank transfers and other direct fiat deposits
    
    Args:
        user: Username identifier
        api_key: Binance API key
        api_secret: Binance API secret
        start_time: Optional - start timestamp in milliseconds
        end_time: Optional - end timestamp in milliseconds
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier
    
    Returns:
        List of fiat order records
    """
    endpoint = '/sapi/v1/fiat/orders'
    
    all_orders = []
    page = 1
    rows = 500  # Max allowed by Binance
    
    logger.info(f"Fetching fiat orders (SPEI/bank transfers) for {user}...")
    
    while True:
        # Build query parameters
        params = {
            'transactionType': 0,  # 0 = deposit, 1 = withdrawal
            'page': page,
            'rows': rows
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
        
        # Response structure: {"code": "000000", "message": "success", "data": [...], "total": N}
        if data.get('code') != '000000':
            logger.error(f"Binance API error for {user}: {data.get('message', 'Unknown error')}")
            break
        
        orders = data.get('data', [])
        total_records = data.get('total', 0)
        
        if not orders:
            logger.info(f"No more fiat orders found for {user}.")
            break
        
        all_orders.extend(orders)
        logger.info(f"Fetched {len(orders)} fiat orders (total: {len(all_orders)}/{total_records})")
        
        # Check if we've fetched all records
        if len(all_orders) >= total_records:
            logger.info(f"All fiat orders retrieved for {user}.")
            break
        
        page += 1
    
    logger.info(f"Total fiat orders fetched for {user}: {len(all_orders)}")
    return all_orders
