import json
from flask import Blueprint, request, jsonify
import core.utils.web_utils as web_utils
from core.utils.log_config import setup_logging
from config import PAYMENT_ACCOUNTS_PATH
import os

settings_bp = Blueprint('settings', __name__)


@settings_bp.route("/update_setting", methods=["POST"])
def update_setting():
    data = request.json
    key = data.get("key")
    is_enabled = data.get("enabled")

    if key is None or is_enabled is None:
        return jsonify({"success": False, "error": "Missing key or enabled parameter"}), 400

    settings = web_utils.get_app_settings()
    if key not in settings:
        return jsonify({"success": False, "error": f"Invalid setting key: {key}"}), 400

    settings[key] = is_enabled
    web_utils.update_app_settings(settings)

    if key == "verbose_logging_enabled":
        setup_logging()

    status_text = "enabled" if is_enabled else "disabled"
    return jsonify({"success": True, "message": f"Setting '{key}' has been {status_text}."})


@settings_bp.route("/update_all_selections", methods=["POST"])
def update_all_selections():
    selections = request.json
    if not isinstance(selections, list):
        return jsonify({"success": False, "error": "Invalid data format"}), 400

    errors = []
    for selection in selections:
        filename = selection.get("filename")
        owner_username = selection.get("owner_username")
        payment_method = selection.get("payment_method")
        selected_id = selection.get("selected_id")

        if not all([filename, owner_username, payment_method, selected_id]):
            errors.append("Incomplete data for one of the selections.")
            continue

        filepath = os.path.join(PAYMENT_ACCOUNTS_PATH, filename)
        if not os.path.exists(filepath):
            errors.append(f"File not found: {filename}")
            continue

        try:
            with open(filepath, "r+", encoding="utf-8") as f:
                file_data = json.load(f)
                if owner_username in file_data and payment_method in file_data.get(owner_username, {}):
                    file_data[owner_username][payment_method]["selected_id"] = selected_id
                    f.seek(0)
                    json.dump(file_data, f, indent=4)
                    f.truncate()
                else:
                    errors.append(
                        f"Invalid structure in {filename} for {owner_username}.")
        except Exception as e:
            errors.append(
                f"An unexpected error occurred with {filename}: {str(e)}")

    if errors:
        return jsonify({"success": False, "error": " | ".join(errors)}), 500
    return jsonify({"success": True, "message": "All selections updated successfully."})


@settings_bp.route("/get_pricing_settings", methods=["GET"])
def get_pricing_settings():
    from core.trading.dynamic_pricing import load_settings
    try:
        settings = load_settings()
        return jsonify({"success": True, "settings": settings})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/update_pricing_rules", methods=["POST"])
def update_pricing_rules():
    data = request.json
    crypto = data.get("crypto")
    pm = data.get("payment_method")
    min_m = data.get("min_margin")
    max_m = data.get("max_margin")

    if not all([crypto, pm, min_m is not None, max_m is not None]):
        return jsonify({"success": False, "error": "Missing parameters (crypto, payment_method, min_margin, max_margin)."}), 400

    from core.trading.dynamic_pricing import load_settings, SETTINGS_FILE
    
    try:
        settings = load_settings()
        if crypto in settings.get("rules", {}) and pm in settings["rules"][crypto]:
            settings["rules"][crypto][pm]["min_margin"] = float(min_m)
            settings["rules"][crypto][pm]["max_margin"] = float(max_m)
            
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
                
            return jsonify({"success": True, "message": f"Updated rules for {crypto}/{pm} successfully."})
        return jsonify({"success": False, "error": f"Rule not found for {crypto}/{pm}."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/get_market_prices", methods=["GET"])
def get_market_prices():
    from core.trading.dynamic_pricing import load_settings
    from core.api.offers import search_public_offers
    from config import BOT_OWNER_USERNAMES
    
    try:
        settings = load_settings()
        rules = settings.get("rules", {})
        
        market_data = []
        for crypto, crypto_rules in rules.items():
            for pm, rule_details in crypto_rules.items():
                # Fetch public offers (using internal cache)
                public_offers = search_public_offers(
                    crypto_code=crypto,
                    fiat_code="MXN",
                    payment_method_slug=pm,
                    trade_direction="buy",
                    payment_method_country_iso="MX",
                    country_code="MX"
                )
                
                closest_competitor = None
                if public_offers:
                    # Filter out own bot offers
                    filtered = [o for o in public_offers if o.get("offer_owner_username") not in BOT_OWNER_USERNAMES]
                    min_competitor_max_limit = float(settings.get("min_competitor_max_limit", 5000.0))
                    
                    # Apply active and reputation filters to match dynamic pricing calculations
                    valid = []
                    import time
                    now_ts = time.time()
                    
                    min_competitor_positive_feedback = int(settings.get("min_competitor_positive_feedback", 10))
                    min_competitor_feedback_ratio = float(settings.get("min_competitor_feedback_ratio", 0.90))
                    
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
                        # Find competitor with lowest margin
                        def get_margin(x):
                            val = x.get("margin")
                            return float(val) if val is not None else 999.0
                        closest = min(valid, key=get_margin)
                        
                        closest_competitor = {
                            "username": closest.get("offer_owner_username"),
                            "margin": closest.get("margin"),
                            "price": closest.get("fiat_price_per_crypto"),
                            "max_limit": closest.get("fiat_amount_range_max")
                        }
                
                market_data.append({
                    "crypto": crypto,
                    "payment_method": pm,
                    "min_margin": rule_details.get("min_margin"),
                    "max_margin": rule_details.get("max_margin"),
                    "closest_competitor": closest_competitor
                })
        
        return jsonify({"success": True, "market_data": market_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

