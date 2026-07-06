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
            current_margin = float(offer.get("margin", 0.0))
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
                max_limit = float(o.get("fiat_amount_range_max", 0.0))
                if max_limit < min_competitor_max_limit:
                    continue
                    
                competitors.append(o)
                
            # 3. Find the lowest competitor margin
            if not competitors:
                logger.info(f"[DynamicPricing] No competitors found in our weight class (max_limit >= {min_competitor_max_limit}). Resetting to max margin.")
                target_margin = max_margin
                reason_msg = f"No competitors found in weight class \\(limit \\>\\= {escape_markdown(str(min_competitor_max_limit))} MXN\\)\\. Reset to Max Margin\\."
            else:
                # Find competitor with lowest margin
                lowest_comp = min(competitors, key=lambda x: float(x.get("margin", 999.0)))
                comp_username = lowest_comp.get("offer_owner_username")
                comp_margin = float(lowest_comp.get("margin"))
                comp_max_limit = float(lowest_comp.get("fiat_amount_range_max"))
                
                # Target is exactly undercut_percentage lower
                target_margin = comp_margin - undercut_percentage
                reason_msg = (
                    f"Set {escape_markdown(str(undercut_percentage))}% below lowest competitor "
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
        current_margin = float(offer.get("margin", 0.0))
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
        competitors = [o for o in public_offers if o.get("offer_owner_username") not in BOT_OWNER_USERNAMES and float(o.get("fiat_amount_range_max", 0.0)) >= min_competitor_max_limit]
        
        lowest_comp_margin_str = "None"
        if competitors:
            lowest_comp = min(competitors, key=lambda x: float(x.get("margin", 999.0)))
            lowest_comp_margin_str = f"`{lowest_comp.get('margin')}%` by `{escape_markdown(lowest_comp.get('offer_owner_username'))}`"
            
        rank_str = f"Rank \\#{owner_rank} Promoted" if owner_rank else "Not Promoted"
        report_lines.append(
            f"• *{crypto}/{fiat}/{payment_method}*:\n"
            f"  - Your Margin: `{current_margin}%` \\({rank_str}\\)\n"
            f"  - Lowest Competitor: {lowest_comp_margin_str}\n"
        )
        
    if not report_lines:
        return
        
    message = "📊 *Noones Market Status Report* 📊\n\n" + "\n".join(report_lines)
    topic_id = TELEGRAM_TOPICS.get("action_required")
    _send_text_alert(message, thread_id=topic_id)
