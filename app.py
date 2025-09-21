# app.py
import json
import os
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
from datetime import datetime

import bot_process_manager
import web_utils

from core.api.auth import fetch_token_with_retry
from core.messaging.message_sender import send_message_with_retry
from config import ACCOUNTS, CHAT_URL_PAXFUL, CHAT_URL_NOONES, JSON_PATH, TRADE_HISTORY
from core.api.offers import set_offer_status, get_all_offers, toggle_single_offer
from core.utils.log_config import setup_logging
from core.utils.profile import generate_user_profile
from core.bitso.fetch_funding import fetch_funding_transactions_for_user
from core.bitso.filter_data import filter_fundings_by_month
import bitso_config
from core.utils import trade_history


app = Flask(__name__)
setup_logging()
logger = logging.getLogger(__name__)

if not os.path.exists(JSON_PATH):
    os.makedirs(JSON_PATH)

# --- Web Page Route ---
@app.route("/")
def index():
    payment_data_from_files = web_utils.get_payment_data()
    app_settings = web_utils.get_app_settings()
    user_grouped_data = {}
    for filename, owners_data in payment_data_from_files.items():
        for owner_name, methods_data in owners_data.items():
            if owner_name not in user_grouped_data:
                user_grouped_data[owner_name] = {}
            for method_name, details_data in methods_data.items():
                user_grouped_data[owner_name][method_name] = { "filename": filename, "details": details_data }
    return render_template(
        "index.html",
        user_grouped_data=user_grouped_data,
        app_settings=app_settings
    )

# --- API Routes for Frontend ---
@app.route("/update_setting", methods=["POST"])
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

@app.route("/update_all_selections", methods=["POST"])
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
            errors.append(f"Incomplete data for one of the selections.")
            continue

        filepath = os.path.join(JSON_PATH, filename)
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
                    errors.append(f"Invalid structure in {filename} for {owner_username}.")
        except Exception as e:
            errors.append(f"An unexpected error occurred with {filename}: {str(e)}")

    if errors:
        return jsonify({"success": False, "error": " | ".join(errors)}), 500
    return jsonify({"success": True, "message": "All selections updated successfully."})

@app.route("/get_active_trades")
def get_active_trades():
    active_trades_data = []
    for filename in os.listdir("."):
        if filename.endswith("_trades.json"):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    trades_list = data.get("data", {}).get("trades", [])
                    if trades_list:
                        account_name_source = filename.replace("_trades.json", "").replace("_", " ").title()
                        for trade in trades_list:
                            trade['account_name_source'] = account_name_source
                        active_trades_data.extend(trades_list)
            except Exception as e:
                logger.error(f"Could not read or parse trades file {filename}: {e}")
    return jsonify(active_trades_data)

@app.route("/user_profile/<username>")
def get_user_profile(username):
    """New endpoint to get user profile data."""
    profile_data = generate_user_profile(username)
    if profile_data:
        return jsonify(profile_data)
    else:
        return jsonify({"error": "User not found"}), 404

# --- /get_summary route has been removed ---
@app.route("/offer/toggle", methods=["POST"])
def toggle_offers():
    data = request.json
    is_enabled = data.get("enabled")
    if is_enabled is None:
        return jsonify({"success": False, "error": "Missing 'enabled' parameter."}), 400

    results = set_offer_status(turn_on=is_enabled)
    successful_accounts = [r["account"] for r in results if r["success"]]
    failed_accounts = [f"{r['account']} ({r['error']})" for r in results if not r["success"]]

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

@app.route("/get_offers")
def get_offers_route():
    offers = get_all_offers()
    return jsonify(offers)

@app.route("/offer/toggle_single", methods=["POST"])
def toggle_single_offer_route():
    data = request.json
    account_name = data.get("account_name")
    offer_hash = data.get("offer_hash")
    is_enabled = data.get("enabled")

    if not all([account_name, offer_hash, is_enabled is not None]):
        return jsonify({"success": False, "error": "Missing required parameters."}), 400

    result = toggle_single_offer(account_name, offer_hash, is_enabled)
    return jsonify(result)

@app.route("/send_manual_message", methods=["POST"])
def send_manual_message():
    data = request.json
    trade_hash = data.get("trade_hash")
    account_name = data.get("account_name")
    message = data.get("message")

    if not all([trade_hash, account_name, message]):
        return jsonify({"success": False, "error": "Missing trade hash, account name, or message."}), 400

    formatted_account_name = account_name.replace(" ", "_")
    target_account = next((acc for acc in ACCOUNTS if acc["name"].lower() == formatted_account_name.lower()), None)

    if not target_account:
        return jsonify({"success": False, "error": f"Account '{account_name}' not found."}), 404

    token = fetch_token_with_retry(target_account)
    if not token:
        return jsonify({"success": False, "error": "Could not authenticate."}), 500

    headers = { "Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded" }
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in target_account["name"] else CHAT_URL_NOONES
    body = {"trade_hash": trade_hash, "message": message}

    if send_message_with_retry(chat_url, body, headers):
        return jsonify({"success": True, "message": "Message sent successfully!"})
    else:
        return jsonify({"success": False, "error": "Failed to send message via API."}), 500

@app.route("/bitso_summary")
def get_bitso_summary():
    """New endpoint to get the sum of all bitso deposits for the current month."""
    try:
        all_fundings = []
        for user, (api_key, api_secret) in bitso_config.API_KEYS.items():
            if not api_key or not api_secret:
                print(f"Missing credentials for {user}. Skipping...")
                continue
            fundings = fetch_funding_transactions_for_user(user, api_key, api_secret)
            all_fundings.extend(fundings)

        now = datetime.now()
        filtered_fundings = filter_fundings_by_month(all_fundings, now.year, now.month)

        deposits_by_sender = {}
        for funding in filtered_fundings:
            if funding.get('status') == 'complete':
                details = funding.get('details', {}) or {}
                clabe = details.get('sender_clabe')

                try:
                    amount = float(funding.get('amount', 0))
                except (ValueError, TypeError):
                    continue

                name = bitso_config.ACCOUNT.get(clabe, clabe)
                if name:
                    deposits_by_sender[name] = deposits_by_sender.get(name, 0) + amount

        sorted_deposits = sorted(deposits_by_sender.items())

        return jsonify({
            "success": True,
            "deposits_by_sender": sorted_deposits,
            "total_deposits": sum(deposits_by_sender.values())
        })

    except Exception as e:
        logger.error(f"Failed to get Bitso summary: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve Bitso summary."}), 500


@app.route("/generate_charts", methods=["POST"])
def generate_charts():
    """New endpoint to generate and retrieve trade charts."""
    try:
        plot_paths = trade_history.main()
        return jsonify({"success": True, "charts": plot_paths})
    except Exception as e:
        logger.error(f"Failed to generate charts: {e}")
        return jsonify({"success": False, "error": "Failed to generate charts."}), 500

@app.route('/charts/<filename>')
def get_chart(filename):
    """Serves the generated chart images."""
    return send_from_directory(TRADE_HISTORY, filename)


# --- Bot Process Routes ---
@app.route("/start_trading", methods=["POST"])
def start_trading_route():
    result = bot_process_manager.start_trading()
    return jsonify(result)

@app.route("/stop_trading", methods=["POST"])
def stop_trading_route():
    result = bot_process_manager.stop_trading()
    return jsonify(result)

@app.route("/trading_status")
def trading_status_route():
    result = bot_process_manager.get_trading_status()
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, port=5001)