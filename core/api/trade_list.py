import certifi
import logging
import json
import time
import os 
from datetime import datetime, timedelta, timezone
from config import (
    TRADE_LIST_URL_NOONES, 
    TRADE_LIST_URL_PAXFUL, 
    TRADE_COMPLETED_URL_NOONES,
    TRADE_COMPLETED_URL_PAXFUL,
    TRADES_ACTIVE_DIR
)
from core.utils.http_client import get_http_client

logger = logging.getLogger(__name__)


def get_trade_list(account, headers, limit=10, page=1, max_retries=3, include_completed=False):
    # --- ADDED TEMPORARY CHECK ---
    if "_Paxful" in account.get("name", ""):
        logger.warning(f"Temporarily skipping trade list fetching for Paxful account: {account['name']}")
        return []
    # --- END OF CHECK ---

    if "_Paxful" in account["name"]:
        trade_list_url = TRADE_LIST_URL_PAXFUL
    else:
        trade_list_url = TRADE_LIST_URL_NOONES

    data = {
        "page": page,
        "count": 1,
        "limit": limit
    }
    
    headers_paxful = headers.copy()
    if "_Paxful"in account["name"]:
        headers_paxful["Content-Type"] = "application/x-www-form-urlencoded"
    
    http_client = get_http_client()
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1} of {max_retries} for {account['name']}")
            response = http_client.post(
                trade_list_url,
                headers=headers_paxful,
                json=data if "_Paxful" not in account["name"] else data,  
                verify=certifi.where(),
                timeout=10
            )
            
            if response.status_code == 200:
                trades_data = response.json()
                filename = f"{account['name'].replace(' ', '_')}_trades.json"
                filepath = os.path.join(TRADES_ACTIVE_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as json_file:
                    json.dump(trades_data, json_file, indent=4)
                logger.info(f"Saved raw trade data to {filepath}")

                if trades_data.get("status") == "success" and trades_data["data"].get("trades"):
                    trades = trades_data["data"]["trades"]
                    
                    if include_completed:
                        # Fetch recently completed trades from the completed endpoint
                        try:
                            # Use the proper completed URL based on the account type
                            if "_Paxful" in account["name"]:
                                completed_url = TRADE_COMPLETED_URL_PAXFUL
                            else:
                                completed_url = TRADE_COMPLETED_URL_NOONES
                            # Fetch completed trades from last 15 minutes
                            completed_data = {
                                "page": 1,
                                "count": 1,
                                "limit": 20  # Get recent completed trades
                            }
                            
                            logger.debug(f"Fetching completed trades from {completed_url}")
                            completed_response = http_client.post(
                                completed_url,
                                headers=headers_paxful,
                                json=completed_data,
                                verify=certifi.where(),
                                timeout=10
                            )
                            
                            if completed_response.status_code == 200:
                                completed_trades_data = completed_response.json()
                                if completed_trades_data.get("status") == "success" and completed_trades_data["data"].get("trades"):
                                    completed_trades = completed_trades_data["data"]["trades"]
                                    
                                    # Filter to only recently completed (within 15 minutes)
                                    fifteen_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=15)
                                    recently_completed = []
                                    for trade in completed_trades:
                                        if trade.get("trade_status") == "Successful":
                                            completed_at_str = trade.get("completed_at")
                                            if completed_at_str:
                                                try:
                                                    completed_at = datetime.fromisoformat(completed_at_str.replace("Z", "+00:00"))
                                                    if completed_at > fifteen_minutes_ago:
                                                        recently_completed.append(trade)
                                                        logger.info(f"Found recently completed trade: {trade.get('trade_hash')}")
                                                except (ValueError, TypeError) as e:
                                                    logger.debug(f"Error parsing completion time: {e}")
                                    
                                    # Add recently completed trades to the active trades list
                                    trades.extend(recently_completed)
                                    logger.info(f"Added {len(recently_completed)} recently completed trades to processing queue")
                            else:
                                logger.warning(f"Failed to fetch completed trades: {completed_response.status_code}")
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