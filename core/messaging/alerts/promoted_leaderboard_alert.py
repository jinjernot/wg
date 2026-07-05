import os
import json
import logging
from config import STATE_DIR, BOT_OWNER_USERNAMES, TELEGRAM_TOPICS
from core.api.offers import search_public_offers
from core.messaging.alerts.telegram_alert import _send_text_alert, escape_markdown

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(STATE_DIR, "promoted_state.json")

def load_previous_state():
    """Loads the previous leaderboard state from the JSON file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading promoted state file: {e}")
    return {}

def save_current_state(state):
    """Saves the current leaderboard state to the JSON file."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving promoted state file: {e}")

def check_promoted_leaderboard_and_alert():
    """
    Checks the promoted offers leaderboard for BTC and USDT.
    Triggers Telegram alerts if the bot owner is not in position #1.
    """
    logger.info("Running promoted offers leaderboard watchdog job...")
    
    prev_state = load_previous_state()
    current_state = {}
    
    cryptos = ["BTC", "USDT"]
    
    for crypto in cryptos:
        try:
            # Fetch public sell offers ( visitor buying BTC/USDT with MXN via bank-transfer )
            offers = search_public_offers(
                crypto_code=crypto,
                fiat_code="MXN",
                payment_method_slug="bank-transfer",
                trade_direction="buy", # visitor buys -> returns traders selling
                payment_method_country_iso="MX",
                country_code="MX"
            )
            
            if offers is None:
                logger.warning(f"[LeaderboardWatchdog] Failed to fetch offers for {crypto}.")
                continue
                
            # Filter for promoted/stickied offers
            promoted_offers = [o for o in offers if o.get("is_sticky") == True]
            
            # Find the bot owner's offer rank in the promoted list
            owner_rank = None
            owner_offer = None
            for idx, offer in enumerate(promoted_offers):
                username = offer.get("offer_owner_username")
                if username in BOT_OWNER_USERNAMES:
                    owner_rank = idx + 1
                    owner_offer = offer
                    break
            
            # Determine competitor information if we are not rank 1
            first_place = promoted_offers[0] if promoted_offers else None
            first_place_username = first_place.get("offer_owner_username") if first_place else None
            first_place_margin = first_place.get("margin") if first_place else None
            first_place_fee = first_place.get("seller_fee") if first_place else None
            
            # Formulate current status
            if owner_rank == 1:
                status = "first"
            elif owner_rank is not None:
                status = "not_first"
            else:
                status = "offline"
                
            current_state[crypto] = {
                "status": status,
                "rank": owner_rank,
                "first_place_username": first_place_username,
                "first_place_margin": first_place_margin,
                "first_place_fee": first_place_fee
            }
            
            # Get previous status for comparison
            prev_crypto_state = prev_state.get(crypto, {})
            prev_status = prev_crypto_state.get("status")
            
            # Prevent alerting on first-run if there is no previous status
            if not prev_status:
                logger.info(f"[LeaderboardWatchdog] Initial state recorded for {crypto}: {status}")
                continue
                
            # Check for changes in status
            if status != prev_status:
                alert_triggered = False
                alert_msg = ""
                
                # Case 1: Stolen from position #1
                if prev_status == "first" and status in ["not_first", "offline"]:
                    alert_triggered = True
                    alert_msg = f"🚨 *\\[{crypto}\\] Promoted Position STOLEN\\!* 🚨\n\n"
                    if status == "not_first":
                        alert_msg += (
                            f"You dropped to *Rank \\#{owner_rank}* in Promoted Spots\\.\n"
                            f"🥇 *Rank \\#1* is now: `{escape_markdown(first_place_username)}`\n"
                            f"  • Margin: `{escape_markdown(str(first_place_margin))}%`\n"
                            f"  • Fee: `{escape_markdown(str(first_place_fee))}%`"
                        )
                    else:
                        alert_msg += (
                            f"Your offer has dropped out of the Top 3 Promoted Spots entirely\\!\n"
                            f"🥇 *Rank \\#1* is now: `{escape_markdown(first_place_username)}`"
                        )
                
                # Case 2: Fell out of promoted list completely
                elif prev_status == "not_first" and status == "offline":
                    alert_triggered = True
                    alert_msg = (
                        f"⚠️ *\\[{crypto}\\] Promoted Spot Lost\\!* ⚠️\n\n"
                        f"Your offer fell out of the Top 3 Promoted Spots completely\\.\n"
                        f"Current Leaderboard is led by: `{escape_markdown(first_place_username)}`"
                    )
                
                # Case 3: Gained Position #1
                elif status == "first" and prev_status in ["not_first", "offline"]:
                    alert_triggered = True
                    alert_msg = (
                        f"🎉 *\\[{crypto}\\] Position \\#1 Reclaimed\\!* 🎉\n\n"
                        f"You are back at *Rank \\#1* on the Promoted Offers Leaderboard\\."
                    )
                    
                if alert_triggered and alert_msg:
                    logger.warning(f"[LeaderboardWatchdog] Alert: {alert_msg}")
                    # Send alert to Telegram 'action_required' topic
                    topic_id = TELEGRAM_TOPICS.get("action_required")
                    _send_text_alert(alert_msg, thread_id=topic_id)
                    
        except Exception as e:
            logger.error(f"Error checking promoted leaderboard for {crypto}: {e}", exc_info=True)
            
    # Save the updated state
    save_current_state(current_state)
