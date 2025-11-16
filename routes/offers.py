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
    country_code = data.get("country_code") # <-- Read the new code

    if not all([crypto_code, fiat_code, payment_method]):
        return jsonify({"success": False, "error": "Missing required parameters (crypto_code, fiat_code, payment_method)."}), 400

    # --- Pass the new code to the function ---
    offers = search_public_offers(crypto_code, fiat_code, payment_method, trade_direction, country_code)
    
    return jsonify({"success": True, "offers": offers})


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
    offers = get_all_offers()
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