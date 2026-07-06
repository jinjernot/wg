import os
import json
import logging
from config import BASE_DIR, BOT_OWNER_USERNAMES, TELEGRAM_TOPICS
from core.api.offers import get_all_offers, search_public_offers, update_offer_margin
from core.messaging.alerts.telegram_alert import _send_text_alert, escape_markdown

logger = logging.getLogger(__name__)

SETTINGS_FILE = os.path.join(BASE_DIR, "data", "config", "dynamic_pricing_settings.json")

def load_settings():
    """Loads dynamic pricing settings from JSON file."""
    default_settings = {
        "enabled": True,
        "min_competitor_max_limit": 5000.0,
        "undercut_percentage": 1.0,
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
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading dynamic pricing settings: {e}")
    return default_settings

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
    undercut_percentage = float(settings.get("undercut_percentage", 1.0))
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
                
            # Filter out own offers and offers with low limits
            competitors = []
            for o in public_offers:
                username = o.get("offer_owner_username")
                if username in BOT_OWNER_USERNAMES:
                    continue
                    
                # Exclude micro-offers that don't match our tier
                max_limit_val = o.get("fiat_amount_range_max")
                max_limit = float(max_limit_val) if max_limit_val is not None else 0.0
                if max_limit < min_competitor_max_limit:
                    continue
                    
                competitors.append(o)
                
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
                
                # Target is exactly undercut_percentage lower
                target_margin = comp_margin - undercut_percentage
                reason_msg = (
                    f"Set {escape_markdown(str(undercut_percentage))}% below closest competitor "
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
                
            target_margin = round(target_margin, 2)
            
            # 4. Update offer if there is a meaningful change
            if abs(target_margin - current_margin) >= 0.05:
                logger.warning(f"[DynamicPricing] Updating offer {offer_hash} margin from {current_margin}% to {target_margin}% because: {reason_msg}")
                
                res = update_offer_margin(account_name, offer_hash, target_margin)
                if res.get("success"):
                    logger.info(f"[DynamicPricing] Successfully updated offer {offer_hash} to {target_margin}%.")
                    
                    # Send Telegram alert
                    alert_msg = (
                        f"🔄 *\\[{crypto}\\] Dynamic Pricing Update\\!* 🔄\n\n"
                        f"Your offer `\\[{offer_hash}\\]` margin has been updated\\:\n"
                        f"• *Old Margin*: `{escape_markdown(str(current_margin))}%`\n"
                        f"• *New Margin*: `{escape_markdown(str(target_margin))}%`\n"
                        f"• *Reason*: {reason_msg}"
                    )
                    topic_id = TELEGRAM_TOPICS.get("action_required")
                    _send_text_alert(alert_msg, thread_id=topic_id)
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
        _send_text_alert("📊 *Noones Market Status Report* 📊\n\nNo active offers found.", thread_id=TELEGRAM_TOPICS.get("action_required"))
        return

    min_competitor_max_limit = float(settings.get("min_competitor_max_limit", 5000.0))
    rules = settings.get("rules", {})
    
    report_lines = []
    
    for offer in own_offers:
        crypto = offer.get("crypto_currency_code")
        fiat = offer.get("currency_code")
        payment_method = offer.get("payment_method_slug")
        
        current_margin_val = offer.get("margin")
        current_margin = float(current_margin_val) if current_margin_val is not None else 0.0
        
        offer_hash = offer.get("offer_id")
        
        # Only report on offers that have pricing rules configured
        if crypto not in rules or payment_method not in rules[crypto]:
            continue
            
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
            report_lines.append(f"• *{crypto}/{fiat}/{payment_method}*:\n  - Your Margin: `{current_margin}%` \\(`{offer_hash}`\\)\n  - Status: `Offline / Error fetching market`\n")
            continue
            
        # Find our rank in the promoted section
        promoted_offers = [o for o in public_offers if o.get("is_sticky") == True]
        owner_rank = None
        for idx, o in enumerate(promoted_offers):
            if o.get("offer_owner_username") in BOT_OWNER_USERNAMES:
                owner_rank = idx + 1
                break
                
        # Find competitor lowest margin
        def get_max_limit_val(o):
            val = o.get("fiat_amount_range_max")
            return float(val) if val is not None else 0.0
            
        competitors = [o for o in public_offers if o.get("offer_owner_username") not in BOT_OWNER_USERNAMES and get_max_limit_val(o) >= min_competitor_max_limit]
        
        own_price_val = offer.get("fiat_price_per_crypto")
        own_price = float(own_price_val) if own_price_val is not None else 0.0

        lowest_comp_margin_str = "None"
        if competitors:
            def get_comp_margin_val(x):
                val = x.get("margin")
                return float(val) if val is not None else 999.0
            lowest_comp = min(competitors, key=get_comp_margin_val)
            
            comp_price_val = lowest_comp.get("fiat_price_per_crypto")
            comp_price = float(comp_price_val) if comp_price_val is not None else 0.0
            
            lowest_comp_margin_str = (
                f"`{lowest_comp.get('margin')}%` \\(`{comp_price:,.2f} {fiat}`\\) "
                f"by `{escape_markdown(lowest_comp.get('offer_owner_username'))}`"
            )
            
        rank_str = f"Rank \\#{owner_rank} Promoted" if owner_rank else "Not Promoted"
        report_lines.append(
            f"• *{crypto}/{fiat}/{payment_method}*:\n"
            f"  - Your Margin: `{current_margin}%` \\(`{own_price:,.2f} {fiat}`\\) \\({rank_str}\\)\n"
            f"  - Lowest Competitor: {lowest_comp_margin_str}\n"
        )
        
    if not report_lines:
        return
        
    message = "📊 *Noones Market Status Report* 📊\n\n" + "\n".join(report_lines)
    topic_id = TELEGRAM_TOPICS.get("action_required")
    _send_text_alert(message, thread_id=topic_id)

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
    topic_id = TELEGRAM_TOPICS.get("action_required")
    _send_text_alert(message, thread_id=topic_id)
