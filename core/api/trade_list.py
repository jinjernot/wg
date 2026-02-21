import certifi
import logging
import json
import time
import os 
from datetime import datetime, timedelta, timezone
from config import (
    TRADE_LIST_URL_NOONES,
    TRADE_COMPLETED_URL_NOONES,
    TRADES_ACTIVE_DIR
)
from core.utils.http_client import get_http_client

logger = logging.getLogger(__name__)


def get_trade_list(account, headers, limit=10, page=1, max_retries=3, include_completed=False):

    data = {
        "page": page,
        "count": 1,
        "limit": limit
    }

    http_client = get_http_client()
    
    for attempt in range(max_retries):
        try:
            response = http_client.post(
                TRADE_LIST_URL_NOONES,
                headers=headers,
                json=data,
                verify=certifi.where(),
                timeout=10
            )
            
            if response.status_code == 200:
                trades_data = response.json()
                filename = f"{account['name'].replace(' ', '_')}_trades.json"
                filepath = os.path.join(TRADES_ACTIVE_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as json_file:
                    json.dump(trades_data, json_file, indent=4)
                logger.debug(f"Saved raw trade data to {filepath}")

                if trades_data.get("status") == "success" and trades_data["data"].get("trades"):
                    trades = trades_data["data"]["trades"]
                    
                    # Fetch recently completed trades if requested
                    # Completed trades immediately drop off the /trade/list endpoint
                    if include_completed:
                        try:
                            completed_url = TRADE_COMPLETED_URL_NOONES
                            
                            # Fetch recent completed trades (last 5 minutes)
                            completed_data = {
                                "page": 1,
                                "limit": 20  # Get recent completed trades
                            }
                            
                            completed_response = http_client.post(
                                completed_url,
                                headers=headers,
                                data=completed_data,  # Use data= not json=
                                verify=certifi.where(),
                                timeout=10
                            )
                            
                            if completed_response.status_code == 200:
                                completed_trades_data = completed_response.json()
                                if completed_trades_data.get("status") == "success" and completed_trades_data["data"].get("trades"):
                                    completed_trades = completed_trades_data["data"]["trades"]
                                    
                                    # Filter to only very recently completed (within 5 minutes)
                                    five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
                                    recently_completed = []
                                    for trade in completed_trades:
                                        # API uses 'Released' status for completed trades
                                        if trade.get("trade_status") in ["Released", "Successful"]:
                                            completed_at_str = trade.get("completed_at")
                                            if completed_at_str:
                                                try:
                                                    completed_at = datetime.fromisoformat(completed_at_str.replace("Z", "+00:00"))
                                                    if completed_at > five_minutes_ago:
                                                        recently_completed.append(trade)
                                                        logger.info(f"Found recently completed trade: {trade.get('trade_hash')} at {completed_at_str}")
                                                except (ValueError, TypeError) as e:
                                                    logger.debug(f"Error parsing completion time: {e}")
                                    
                                    # Add recently completed trades to processing queue
                                    trades.extend(recently_completed)
                                    logger.debug(f"Added {len(recently_completed)} recently completed trades from last 5 minutes")
                            else:
                                logger.warning(f"Failed to fetch completed trades from {completed_url}: {completed_response.status_code}")
                                logger.debug(f"Response text: {completed_response.text}")
                        except Exception as e:
                            logger.error(f"Error fetching completed trades: {e}")
                    
                    return trades
                else:
                    logger.warning(f"No trades found for {account['name']}.")
                    return []
            else:
                logger.error(f"Error fetching trade list for {account['name']}: {response.status_code} - {response.text}")
                return []
        
        except Exception as e:
            logger.error(f"SSL/Request Error on attempt {attempt + 1} for {account['name']}: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.debug(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                logger.error("Max retries reached. Giving up.")
                return []
    
    return []