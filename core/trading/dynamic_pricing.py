import os
import json
import logging
import time
from config import BASE_DIR, BOT_OWNER_USERNAMES, TELEGRAM_TOPICS
from core.api.offers import get_all_offers, search_public_offers, update_offer_margin
from core.messaging.alerts.telegram_alert import _send_text_alert, escape_markdown
from core.messaging.alerts.discord_alert import send_discord_text

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.join(BASE_DIR, "data", "config", "dynamic_pricing_settings.json")

def load_settings():
    """Loads dynamic pricing settings from JSON file."""
    default_settings = {
        "enabled": True,
        "min_competitor_max_limit": 5000.0,
        "undercut_percentage": 0.1,
        "min_competitor_positive_feedback": 10,
        "min_competitor_feedback_ratio": 0.90,
        "david_min_margin": 11.0,
        "joe_min_margin": 11.0,
        "rules": {
            "BTC": {
                "bank-transfer": {
                    "min_margin": 11.0,
                    "max_margin": 24.5
                },
                "spei-sistema-de-pagos-electronicos-interbancarios": {
                    "min_margin": 11.0,
                    "max_margin": 24.5
                }
            },
            "USDT": {
                "bank-transfer": {
                    "min_margin": 11.0,
                    "max_margin": 24.5
                },
                "spei-sistema-de-pagos-electronicos-interbancarios": {
                    "min_margin": 11.0,
                    "max_margin": 24.5
                }
            }
        }
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure defaults for top-level keys
                for k, v in default_settings.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            logger.error(f"Error loading dynamic pricing settings: {e}")
    return default_settings

def filter_competitors(public_offers, min_competitor_max_limit, min_competitor_positive_feedback, min_competitor_feedback_ratio):
    """
    Filter competitor offers out based on limit, status, seen timeframe, and feedback.
    """
    competitors = []
    now_ts = time.time()
    for o in public_offers:
        username = o.get("offer_owner_username")
        if username in BOT_OWNER_USERNAMES:
            continue
            
        # Exclude micro-offers that don't match our tier
        max_limit_val = o.get("fiat_amount_range_max")
        max_limit = float(max_limit_val) if max_limit_val is not None else 0.0
        if max_limit < min_competitor_max_limit:
            continue
            
        # 1. Ignore inactive/offline competitors (not active in last 30 minutes)
        last_seen_ts = o.get("last_seen_timestamp")
        last_seen_status = o.get("last_seen")
        if last_seen_ts:
            try:
                seconds_offline = now_ts - float(last_seen_ts)
                if seconds_offline > 1800:  # 30 minutes
                    continue
            except (ValueError, TypeError):
                if last_seen_status and last_seen_status not in ["seen-very-recently", "seen-recently"]:
                    continue
        elif last_seen_status and last_seen_status not in ["seen-very-recently", "seen-recently"]:
            continue
            
        # 3. Filter out low-reputation / price-baiting competitors
        try:
            pos_feedback = int(o.get("offer_owner_feedback_positive") or 0)
            neg_feedback = int(o.get("offer_owner_feedback_negative") or 0)
        except (ValueError, TypeError):
            pos_feedback = 0
            neg_feedback = 0
        
        # Check minimum positive feedback count
        if pos_feedback < min_competitor_positive_feedback:
            continue
            
        # Check feedback ratio (e.g. at least 90% positive)
        total_feedback = pos_feedback + neg_feedback
        if total_feedback > 0:
            ratio = pos_feedback / total_feedback
            if ratio < min_competitor_feedback_ratio:
                continue
            
        competitors.append(o)
    return competitors

def update_dynamic_pricing_job():
    """
    Background job that scans the competition for all active offers
    and adjusts margins dynamically.
    """
    settings = load_settings()
    if not settings.get("enabled", True):
        logger.info("[DynamicPricing] Dynamic pricing is currently disabled in settings.")
        return

    logger.info("[DynamicPricing] Running dynamic pricing update job...")
    
    # 1. Fetch own active offers
    own_offers = get_all_offers()
    if not own_offers:
        logger.info("[DynamicPricing] No active own offers found to adjust.")
        return

    min_competitor_max_limit = float(settings.get("min_competitor_max_limit", 5000.0))
    undercut_percentage = float(settings.get("undercut_percentage", 0.1))
    min_competitor_positive_feedback = int(settings.get("min_competitor_positive_feedback", 10))
    min_competitor_feedback_ratio = float(settings.get("min_competitor_feedback_ratio", 0.90))
    rules = settings.get("rules", {})

    for offer in own_offers:
        try:
            offer_hash = offer.get("offer_id")
            crypto = offer.get("crypto_currency_code")
            fiat = offer.get("currency_code")
            payment_method = offer.get("payment_method_slug")
            
            current_margin_val = offer.get("margin")
            current_margin = float(current_margin_val) if current_margin_val is not None else 0.0
            
            account_name = offer.get("account_name")
            
            # Skip if there is no rule configured for this crypto
            if crypto not in rules:
                logger.debug(f"[DynamicPricing] No rules configured for crypto {crypto}, skipping offer {offer_hash}.")
                continue
                
            crypto_rules = rules[crypto]
            
            # Safe check: only adjust if the specific payment method is configured
            if payment_method not in crypto_rules:
                logger.debug(f"[DynamicPricing] Payment method '{payment_method}' is not configured for {crypto}. Skipping offer {offer_hash} for safety.")
                continue
                
            rule = crypto_rules[payment_method]
            min_margin = float(rule.get("min_margin", 11.0))
            max_margin = float(rule.get("max_margin", 24.5))
            
            # Apply user-specific safety floor override for bank transfer / SPEI
            if payment_method in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios"]:
                if account_name and "david" in str(account_name).lower():
                    min_margin = float(settings.get("david_min_margin", 11.0))
                elif account_name and "joe" in str(account_name).lower():
                    min_margin = float(settings.get("joe_min_margin", 11.0))            
            logger.info(f"[DynamicPricing] Scanning competition for offer {offer_hash} ({crypto}/{fiat}/{payment_method}) on account {account_name}...")
            
            # Check country ISO parameters (specifically for MXN)
            payment_method_country_iso = "MX" if fiat.upper() == "MXN" else None
            country_code = "MX" if fiat.upper() == "MXN" else None
            
            # 2. Fetch public competitor offers (visitor buying -> traders selling)
            public_offers = search_public_offers(
                crypto_code=crypto,
                fiat_code=fiat,
                payment_method_slug=payment_method,
                trade_direction="buy",
                payment_method_country_iso=payment_method_country_iso,
                country_code=country_code
            )
            
            if public_offers is None:
                logger.warning(f"[DynamicPricing] Failed to fetch public offers for {crypto}/{fiat}/{payment_method}.")
                continue
                
            # Filter out own offers, low limits, inactive, and low-reputation competitors
            competitors = filter_competitors(
                public_offers,
                min_competitor_max_limit,
                min_competitor_positive_feedback,
                min_competitor_feedback_ratio
            )
                
            # 3. Find the closest competitor margin that we can outbid
            # Filter competitors to only those at or above our min safety margin
            def get_comp_margin(x):
                val = x.get("margin")
                return float(val) if val is not None else 999.0

            valid_competitors = [c for c in competitors if get_comp_margin(c) >= min_margin]

            if not competitors:
                logger.info(f"[DynamicPricing] No competitors found in our weight class (max_limit >= {min_competitor_max_limit}). Resetting to max margin.")
                target_margin = max_margin
                reason_msg = f"No competitors found in weight class \\(limit \\>\\= {escape_markdown(str(min_competitor_max_limit))} MXN\\)\\. Reset to Max Margin\\."
            elif not valid_competitors:
                logger.info(f"[DynamicPricing] All competitors are below our floor of {min_margin}%. Setting to min margin.")
                target_margin = min_margin
                reason_msg = f"All competitors are below Min Safety Margin \\({escape_markdown(str(min_margin))}%\\)\\. Capped at safety floor\\."
            else:
                # Find the closest competitor (the lowest among those above min_margin)
                lowest_comp = min(valid_competitors, key=get_comp_margin)
                comp_username = lowest_comp.get("offer_owner_username")
                
                comp_margin_val = lowest_comp.get("margin")
                comp_margin = float(comp_margin_val) if comp_margin_val is not None else 0.0
                
                comp_max_limit_val = lowest_comp.get("fiat_amount_range_max")
                comp_max_limit = float(comp_max_limit_val) if comp_max_limit_val is not None else 0.0
                
                # Get rule-specific undercut_percentage or default to the global settings one
                rule_undercut = rule.get("undercut_percentage")
                current_undercut = float(rule_undercut) if rule_undercut is not None else undercut_percentage

                # Target is exactly current_undercut lower
                target_margin = comp_margin - current_undercut
                reason_msg = (
                    f"Set {escape_markdown(str(current_undercut))}% below closest competitor "
                    f"`{escape_markdown(comp_username)}` at `{escape_markdown(str(comp_margin))}%` "
                    f"\\(max limit: {escape_markdown(f'{comp_max_limit:,.0f}')} MXN\\)\\."
                )
                
            # Enforce safety boundaries
            if target_margin < min_margin:
                target_margin = min_margin
                reason_msg += f" Capped at Min Safety Margin \\({escape_markdown(str(min_margin))}%\\)\\."
            elif target_margin > max_margin:
                target_margin = max_margin
                reason_msg += f" Capped at Max safety Margin \\({escape_markdown(str(max_margin))}%\\)\\."
                
            target_margin = float(round(target_margin, 2))
            
            # 4. Update offer if there is a meaningful change
            if abs(target_margin - current_margin) >= 0.05:
                logger.warning(f"[DynamicPricing] Updating offer {offer_hash} margin from {current_margin}% to {target_margin}% because: {reason_msg}")

                # Brief cooldown between offer updates to avoid hitting Noones rate limits.
                time.sleep(5)
                res = update_offer_margin(account_name, offer_hash, target_margin)
                if res.get("success"):
                    logger.info(f"[DynamicPricing] Successfully updated offer {offer_hash} to {target_margin}%.")
                    
                    user_clean = account_name.split("_")[0] if account_name else "Unknown"
                    
                    if target_margin > current_margin:
                        direction_icon = "📈"
                    elif target_margin < current_margin:
                        direction_icon = "📉"
                    else:
                        direction_icon = "🔄"
                    
                    # Send Telegram alert
                    alert_msg = (
                        f"{direction_icon} *\\[{crypto}\\] Dynamic Pricing Update\\!* {direction_icon}\n\n"
                        f"Your offer `\\[{offer_hash}\\]` margin has been updated\\:\n"
                        f"• *Old Margin*: `{escape_markdown(str(current_margin))}%`\n"
                        f"• *New Margin*: `{escape_markdown(str(target_margin))}%`\n"
                        f"• *Reason*: {reason_msg}\n\n"
                        f"*Details*:\n"
                        f"• *User*: `{escape_markdown(user_clean)}`\n"
                        f"• *Slug*: `{escape_markdown(payment_method)}`"
                    )
                    topic_id = TELEGRAM_TOPICS.get("pricing_updates") or TELEGRAM_TOPICS.get("action_required")
                    _send_text_alert(alert_msg, thread_id=topic_id)
                    send_discord_text(alert_msg, alert_type="pricing_updates")
                else:
                    logger.error(f"[DynamicPricing] Failed to update margin for {offer_hash}: {res.get('error')}")
            else:
                logger.info(f"[DynamicPricing] Offer {offer_hash} current margin {current_margin}% is already optimal (target: {target_margin}%). No change needed.")
                
        except Exception as e:
            logger.error(f"[DynamicPricing] Error processing pricing for offer: {e}", exc_info=True)

def send_market_status_report():
    """Generates and sends a consolidated market status report to Telegram."""
    logger.info("[DynamicPricing] Generating market status report...")
    settings = load_settings()
    own_offers = get_all_offers()
    if not own_offers:
        topic_id = TELEGRAM_TOPICS.get("market_reports") or TELEGRAM_TOPICS.get("action_required")
        msg = "📊 *Noones Market Status Report* 📊\n\nNo active offers found."
        _send_text_alert(msg, thread_id=topic_id)
        send_discord_text(msg, alert_type="market_reports")
        return

    min_competitor_max_limit = float(settings.get("min_competitor_max_limit", 5000.0))
    min_competitor_positive_feedback = int(settings.get("min_competitor_positive_feedback", 10))
    min_competitor_feedback_ratio = float(settings.get("min_competitor_feedback_ratio", 0.90))
    rules = settings.get("rules", {})
    
    report_lines = []
    
    for offer in own_offers:
        crypto = offer.get("crypto_currency_code")
        fiat = offer.get("currency_code")
        payment_method = offer.get("payment_method_slug")
        
        current_margin_val = offer.get("margin")
        current_margin = float(current_margin_val) if current_margin_val is not None else 0.0
        
        offer_hash = offer.get("offer_id")
        account_name = offer.get("account_name")
        user_clean = account_name.split("_")[0] if account_name else "Unknown"
        
        own_price_val = offer.get("fiat_price_per_crypto")
        own_price = float(own_price_val) if own_price_val is not None else 0.0
        
        # Only report on offers that have pricing rules configured
        if crypto not in rules or payment_method not in rules[crypto]:
            continue
            
        coin_icon = "🪙"
        if crypto and crypto.upper() == "BTC":
            coin_icon = "🔸"
        elif crypto and crypto.upper() == "USDT":
            coin_icon = "🟢"
            
        payment_method_country_iso = "MX" if fiat.upper() == "MXN" else None
        country_code = "MX" if fiat.upper() == "MXN" else None
        
        # Fetch public list to see rank and competitor margins
        public_offers = search_public_offers(
            crypto_code=crypto,
            fiat_code=fiat,
            payment_method_slug=payment_method,
            trade_direction="buy",
            payment_method_country_iso=payment_method_country_iso,
            country_code=country_code
        )
        
        if not public_offers:
            report_lines.append(
                f"• {coin_icon} *{crypto}/{fiat}/{payment_method}* \\({escape_markdown(user_clean)} \\| `{escape_markdown(offer_hash)}`\\):\n"
                f"  - 📊 *Your Margin*: `{current_margin}%` \\(`{own_price:,.2f} {fiat}`\\)\n"
                f"  - ⚠️ *Status*: `Offline / Error fetching market`\n"
            )
            continue
            
        # Find our rank in the promoted section
        promoted_offers = [o for o in public_offers if o.get("is_sticky") == True]
        owner_rank = None
        for idx, o in enumerate(promoted_offers):
            if o.get("offer_owner_username") in BOT_OWNER_USERNAMES:
                owner_rank = idx + 1
                break
                
        competitors = filter_competitors(
            public_offers,
            min_competitor_max_limit,
            min_competitor_positive_feedback,
            min_competitor_feedback_ratio
        )
        
        # Look up min_margin for this offer
        crypto_rules = rules.get(crypto, {})
        rule = crypto_rules.get(payment_method, {})
        min_margin = float(rule.get("min_margin", 11.0))
        
        def get_comp_margin_val(x):
            val = x.get("margin")
            return float(val) if val is not None else 999.0
            
        valid_competitors = [c for c in competitors if get_comp_margin_val(c) >= min_margin]

        closest_comp_margin_str = "None"
        if valid_competitors:
            closest_comp = min(valid_competitors, key=get_comp_margin_val)
            
            comp_price_val = closest_comp.get("fiat_price_per_crypto")
            comp_price = float(comp_price_val) if comp_price_val is not None else 0.0
            
            closest_comp_margin_str = (
                f"`{closest_comp.get('margin')}%` \\(`{comp_price:,.2f} {fiat}`\\) "
                f"by `{escape_markdown(closest_comp.get('offer_owner_username'))}`"
            )
            
        if owner_rank:
            if owner_rank == 1:
                rank_emoji = "🥇"
            elif owner_rank == 2:
                rank_emoji = "🥈"
            elif owner_rank == 3:
                rank_emoji = "🥉"
            else:
                rank_emoji = "🎖️"
            rank_str = f"{rank_emoji} Rank \\#{owner_rank} Promoted"
        else:
            rank_str = "❌ Not Promoted"

        report_lines.append(
            f"• {coin_icon} *{crypto}/{fiat}/{payment_method}* \\({escape_markdown(user_clean)} \\| `{escape_markdown(offer_hash)}`\\):\n"
            f"  - 📊 *Your Margin*: `{current_margin}%` \\(`{own_price:,.2f} {fiat}`\\) \\({rank_str}\\)\n"
            f"  - 👥 *Closest Competitor*: {closest_comp_margin_str}\n"
        )
        
    if not report_lines:
        return
        
    message = "📊 *Noones Market Status Report* 📊\n\n" + "\n".join(report_lines)
    topic_id = TELEGRAM_TOPICS.get("market_reports") or TELEGRAM_TOPICS.get("action_required")
    _send_text_alert(message, thread_id=topic_id)
    send_discord_text(message, alert_type="market_reports")

def send_hourly_market_report():
    """
    Sends a consolidated market overview of the Top 10 offers for BTC and USDT to Telegram.
    """
    logger.info("[DynamicPricing] Generating hourly market report...")
    
    cryptos = ["BTC", "USDT"]
    payment_method = "bank-transfer"
    fiat = "MXN"
    
    report_lines = []
    
    for crypto in cryptos:
        payment_method_country_iso = "MX"
        country_code = "MX"
        
        offers = search_public_offers(
            crypto_code=crypto,
            fiat_code=fiat,
            payment_method_slug=payment_method,
            trade_direction="buy",
            payment_method_country_iso=payment_method_country_iso,
            country_code=country_code
        )
        
        if not offers:
            report_lines.append(f"• *{crypto} / {fiat} / {payment_method}*:\n  `Error fetching market data`\n")
            continue
            
        report_lines.append(f"🟢 *{crypto} / {fiat} / {payment_method} (Top 10)*:")
        
        # Take the top 10 offers
        top_10 = offers[:10]
        for idx, offer in enumerate(top_10):
            username = offer.get("offer_owner_username")
            is_sticky = offer.get("is_sticky") == True
            
            margin_val = offer.get("margin")
            margin = float(margin_val) if margin_val is not None else 0.0
            
            price_val = offer.get("fiat_price_per_crypto")
            price = float(price_val) if price_val is not None else 0.0
            
            min_amount_val = offer.get("fiat_amount_range_min")
            min_amount = float(min_amount_val) if min_amount_val is not None else 0.0
            
            max_amount_val = offer.get("fiat_amount_range_max")
            max_amount = float(max_amount_val) if max_amount_val is not None else 0.0
            
            # Format username (bold if it's us, otherwise code format)
            if username in BOT_OWNER_USERNAMES:
                user_str = f"*{escape_markdown(username)}* \\(You\\)"
            else:
                user_str = f"`{escape_markdown(username)}`"
                
            sticky_tag = "⭐ " if is_sticky else ""
            
            report_lines.append(
                f"  {idx+1}\\. {sticky_tag}{user_str} \\| `{margin}%` \\| `{price:,.2f} {fiat}` \\| Limits: `{min_amount:,.0f}`\\-`{max_amount:,.0f}`"
            )
        report_lines.append("") # empty line separator
        
    message = "📊 *Hourly Market Report* 📊\n\n" + "\n".join(report_lines)
    topic_id = TELEGRAM_TOPICS.get("market_reports") or TELEGRAM_TOPICS.get("action_required")
    _send_text_alert(message, thread_id=topic_id)
    send_discord_text(message, alert_type="market_reports")
