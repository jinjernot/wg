from flask import Blueprint, request, jsonify
from core.api.offers import set_offer_status, get_all_offers, toggle_single_offer, search_public_offers
import core.utils.web_utils as web_utils

offers_bp = Blueprint('offers', __name__)


@offers_bp.route("/offer/search", methods=["POST"])
def search_public_offers_route():
    data = request.json
    crypto_code = data.get("crypto_code")
    fiat_code = data.get("fiat_code")
    payment_method = data.get("payment_method")
    trade_direction = data.get("trade_direction", "buy")
    # --- Read the new filter key ---
    payment_method_country_iso = data.get("payment_method_country_iso") 
    # --- ADDED NEW KEY ---
    country_code = data.get("country_code")

    if not all([crypto_code, fiat_code, payment_method]):
        return jsonify({"success": False, "error": "Missing required parameters (crypto_code, fiat_code, payment_method)."}), 400

    # --- Pass the new filter ---
    response_data = search_public_offers(crypto_code, fiat_code, payment_method, trade_direction, payment_method_country_iso, country_code)
    
    # --- MODIFIED: Return the whole 'data' object ---
    if response_data is not None:
        return jsonify({"success": True, "data": response_data})
    else:
        return jsonify({"success": False, "error": "API search failed or returned no data.", "data": {}})


@offers_bp.route("/offer/toggle", methods=["POST"])
def toggle_offers():
    data = request.json
    is_enabled = data.get("enabled")
    if is_enabled is None:
        return jsonify({"success": False, "error": "Missing 'enabled' parameter."}), 400

    results = set_offer_status(turn_on=is_enabled)
    successful_accounts = [r["account"] for r in results if r["success"]]
    failed_accounts = [
        f"{r['account']} ({r['error']})" for r in results if not r["success"]]

    message = ""
    if successful_accounts:
        status_text = "on" if is_enabled else "off"
        message += f"Offers turned {status_text} for: {', '.join(successful_accounts)}. "
    if failed_accounts:
        message += f"Failed to toggle offers for: {', '.join(failed_accounts)}."

    success = len(successful_accounts) > 0
    if success:
        settings = web_utils.get_app_settings()
        settings["offers_enabled"] = is_enabled
        web_utils.update_app_settings(settings)

    return jsonify({"success": success, "message": message})


@offers_bp.route("/get_offers")
def get_offers_route():
    from core.api.offers import search_public_offers
    from core.trading.dynamic_pricing import load_settings
    from config import BOT_OWNER_USERNAMES
    import time
    
    offers = get_all_offers()
    if not offers:
        return jsonify([])
        
    try:
        settings = load_settings()
        min_competitor_max_limit = float(settings.get("min_competitor_max_limit", 5000.0))
        min_competitor_positive_feedback = int(settings.get("min_competitor_positive_feedback", 10))
        min_competitor_feedback_ratio = float(settings.get("min_competitor_feedback_ratio", 0.90))
        
        now_ts = time.time()
        
        for offer in offers:
            crypto = offer.get("crypto_currency_code")
            fiat = offer.get("currency_code")
            pm = offer.get("payment_method_slug")
            
            # Fetch public offers (using internal cache)
            public_offers = search_public_offers(
                crypto_code=crypto,
                fiat_code=fiat,
                payment_method_slug=pm,
                trade_direction="buy",
                payment_method_country_iso="MX" if fiat.upper() == "MXN" else None,
                country_code="MX" if fiat.upper() == "MXN" else None
            )
            
            closest_margin = None
            closest_user = None
            if public_offers:
                filtered = [o for o in public_offers if o.get("offer_owner_username") not in BOT_OWNER_USERNAMES]
                valid = []
                for o in filtered:
                    max_limit_val = o.get("fiat_amount_range_max")
                    max_limit = float(max_limit_val) if max_limit_val is not None else 0.0
                    if max_limit < min_competitor_max_limit:
                        continue
                        
                    # Activity check
                    last_seen_ts = o.get("last_seen_timestamp")
                    last_seen_status = o.get("last_seen")
                    if last_seen_ts:
                        try:
                            seconds_offline = now_ts - float(last_seen_ts)
                            if seconds_offline > 1800:
                                continue
                        except (ValueError, TypeError):
                            if last_seen_status and last_seen_status not in ["seen-very-recently", "seen-recently"]:
                                continue
                    elif last_seen_status and last_seen_status not in ["seen-very-recently", "seen-recently"]:
                        continue
                        
                    # Reputation check
                    try:
                        pos = int(o.get("offer_owner_feedback_positive") or 0)
                        neg = int(o.get("offer_owner_feedback_negative") or 0)
                    except (ValueError, TypeError):
                        pos = 0
                        neg = 0
                        
                    if pos < min_competitor_positive_feedback:
                        continue
                        
                    total = pos + neg
                    if total > 0 and (pos / total) < min_competitor_feedback_ratio:
                        continue
                        
                    valid.append(o)
                
                if valid:
                    def get_margin(x):
                        val = x.get("margin")
                        return float(val) if val is not None else 999.0
                    closest = min(valid, key=get_margin)
                    closest_margin = closest.get("margin")
                    closest_user = closest.get("offer_owner_username")
            
            offer["market_margin"] = closest_margin
            offer["market_competitor"] = closest_user
            
    except Exception as e:
        # Avoid breaking the offers list fetch if dynamic pricing details parsing fails
        pass
        
    return jsonify(offers)


@offers_bp.route("/offer/toggle_single", methods=["POST"])
def toggle_single_offer_route():
    data = request.json
    account_name = data.get("account_name")
    offer_hash = data.get("offer_hash")
    is_enabled = data.get("enabled")

    if not all([account_name, offer_hash, is_enabled is not None]):
        return jsonify({"success": False, "error": "Missing required parameters."}), 400

    result = toggle_single_offer(account_name, offer_hash, is_enabled)
    return jsonify(result)