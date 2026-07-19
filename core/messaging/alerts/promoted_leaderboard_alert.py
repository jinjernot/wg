import os
import json
import logging
from config import STATE_DIR, BOT_OWNER_USERNAMES, TELEGRAM_TOPICS
from core.api.offers import search_public_offers
from core.messaging.alerts.telegram_alert import _send_text_alert, escape_markdown
from core.messaging.alerts.discord_alert import send_discord_text

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
    Triggers Telegram alerts if any bot owner username is not in position #1.
    """
    logger.info("Running promoted offers leaderboard watchdog job...")
    
    prev_state = load_previous_state()
    current_state = {}
    
    # Initialize dictionary for current_state to hold usernames
    for username in BOT_OWNER_USERNAMES:
        current_state[username] = {}
        
    from core.api.offers import get_all_offers
    own_offers = get_all_offers(active_only=False)
    combinations = set()
    if own_offers:
        for o in own_offers:
            c = o.get("crypto_currency_code")
            f = o.get("currency_code")
            p = o.get("payment_method_slug")
            if c and f and p:
                if c.upper() == "SOL":
                    continue
                if "cash-deposit" in p.lower() or "gift-card" in p.lower():
                    continue
                combinations.add((c, f, p))
    else:
        # Fallback if no offers found
        combinations = {("BTC", "MXN", "bank-transfer"), ("USDT", "MXN", "bank-transfer")}
    
    for crypto, fiat_code, payment_method_slug in combinations:
        try:
            # Fetch public sell offers ( visitor buying crypto with fiat via PM )
            offers = search_public_offers(
                crypto_code=crypto,
                fiat_code=fiat_code,
                payment_method_slug=payment_method_slug,
                trade_direction="buy",
                payment_method_country_iso="MX" if fiat_code.upper() == "MXN" else None,
                country_code="MX" if fiat_code.upper() == "MXN" else None
            )
            
            if offers is None:
                logger.warning(f"[LeaderboardWatchdog] Failed to fetch offers for {crypto}-{payment_method_slug}.")
                continue
                
            # Filter for promoted/stickied offers
            promoted_offers = [o for o in offers if o.get("is_sticky") == True]
            
            first_place = promoted_offers[0] if promoted_offers else None
            first_place_username = first_place.get("offer_owner_username") if first_place else None
            first_place_margin = first_place.get("margin") if first_place else None
            first_place_fee = first_place.get("seller_fee") if first_place else None
            
            # Check ranks and state for each bot owner username independently
            for username in BOT_OWNER_USERNAMES:
                owner_rank = None
                owner_offer = None
                for idx, offer in enumerate(promoted_offers):
                    offer_owner = offer.get("offer_owner_username")
                    if offer_owner == username:
                        owner_rank = idx + 1
                        owner_offer = offer
                        break
                
                # Find owner's offer in the full list to get its ID / details
                owner_offer_in_full = next((o for o in offers if o.get("offer_owner_username") == username), None)
                offer_id = None
                if owner_offer:
                    offer_id = owner_offer.get("offer_id")
                elif owner_offer_in_full:
                    offer_id = owner_offer_in_full.get("offer_id")
                
                # Formulate status
                if owner_rank == 1:
                    status = "first"
                elif owner_rank is not None:
                    status = "not_first"
                else:
                    status = "offline"
                    
                composite_key = f"{crypto}-{payment_method_slug}"
                
                current_state[username][composite_key] = {
                    "status": status,
                    "rank": owner_rank,
                    "first_place_username": first_place_username,
                    "first_place_margin": first_place_margin,
                    "first_place_fee": first_place_fee
                }
                
                # Check previous status for comparison
                prev_user_state = prev_state.get(username, {})
                # Migration for old implicit JoeWillgang tracking or old crypto-only keys
                if not prev_user_state and crypto in prev_state and username == "JoeWillgang":
                    prev_user_state = prev_state
                    
                # Try new composite key first, fallback to old crypto key for migration
                prev_crypto_state = prev_user_state.get(composite_key) or prev_user_state.get(crypto, {})
                prev_status = prev_crypto_state.get("status")
                
                if not prev_status:
                    logger.info(f"[LeaderboardWatchdog] Initial state recorded for {username} [{composite_key}]: {status}")
                    continue
                    
                # Check for changes in status
                if status != prev_status:
                    alert_triggered = False
                    alert_msg = ""
                    
                    # Case 1: Stolen from position #1
                    if prev_status == "first" and status in ["not_first", "offline"]:
                        alert_triggered = True
                        alert_msg = f"🚨 *{escape_markdown(username)} \\[{crypto}-{payment_method_slug}\\] Promoted Position STOLEN\\!* 🚨\n\n"
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
                            f"⚠️ *{escape_markdown(username)} \\[{crypto}-{payment_method_slug}\\] Promoted Spot Lost\\!* ⚠️\n\n"
                            f"Your offer fell out of the Top 3 Promoted Spots completely\\.\n"
                            f"Current Leaderboard is led by: `{escape_markdown(first_place_username)}`"
                        )
                    
                    # Case 3: Gained Position #1
                    elif status == "first" and prev_status in ["not_first", "offline"]:
                        alert_triggered = True
                        alert_msg = (
                            f"🎉 *{escape_markdown(username)} \\[{crypto}-{payment_method_slug}\\] Position \\#1 Reclaimed\\!* 🎉\n\n"
                            f"You are back at *Rank \\#1* on the Promoted Offers Leaderboard\\."
                        )
                        
                    if alert_triggered and alert_msg:
                        details_msg = (
                            f"\n\n*Details*:\n"
                            f"• *Coin*: `{escape_markdown(crypto)}`\n"
                            f"• *Payment Method*: `{escape_markdown(payment_method_slug)}`\n"
                            f"• *Offer ID*: `{escape_markdown(offer_id if offer_id else 'Not Found')}`"
                        )
                        alert_msg += details_msg

                        logger.warning(f"[LeaderboardWatchdog] Alert for {username}: {alert_msg}")
                        # Send alert to Telegram 'promoted_leaderboard' topic
                        topic_id = TELEGRAM_TOPICS.get("promoted_leaderboard") or TELEGRAM_TOPICS.get("action_required")
                        _send_text_alert(alert_msg, thread_id=topic_id)
                        # Send alert to Discord
                        send_discord_text(alert_msg, alert_type="promoted_leaderboard")
                        
        except Exception as e:
            logger.error(f"Error checking promoted leaderboard for {crypto}: {e}", exc_info=True)
            
    # Save the updated state
    save_current_state(current_state)
