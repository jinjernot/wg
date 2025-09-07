import subprocess
import requests
import json
import sys
import os
import logging
from api.auth import fetch_token_with_retry
from core.messaging.message_sender import send_message_with_retry
from flask import Flask, render_template, request, jsonify
from config import ACCOUNTS, CHAT_URL_PAXFUL, CHAT_URL_NOONES, JSON_PATH, SETTINGS_FILE
from core.offer_manager import set_offer_status
from core.log_config import setup_logging
from core.reporting import generate_daily_summary

app = Flask(__name__)
setup_logging()
logger = logging.getLogger(__name__)

if not os.path.exists(JSON_PATH):
    os.makedirs(JSON_PATH)

trading_process = None

def get_app_settings():
    """Reads and ensures all keys are present in the settings file."""
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "night_mode_enabled": False,
            "afk_mode_enabled": False,
            "verbose_logging_enabled": True,
            "offers_enabled": False
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(default_settings, f)
        return default_settings
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            settings.setdefault("afk_mode_enabled", False)
            settings.setdefault("night_mode_enabled", False)
            settings.setdefault("verbose_logging_enabled", True)
            settings.setdefault("offers_enabled", False)
            return settings
    except (json.JSONDecodeError, FileNotFoundError):
        return { "night_mode_enabled": False, "afk_mode_enabled": False, "verbose_logging_enabled": True, "offers_enabled": False }

def update_app_settings(new_settings):
    """Writes the updated settings to the file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(new_settings, f, indent=4)

def get_payment_data():
    payment_data = {}
    if not os.path.exists(JSON_PATH):
        logger.warning(f"Warning: Directory {JSON_PATH} not found.")
        return payment_data
    for filename in os.listdir(JSON_PATH):
        if filename.endswith(".json"):
            filepath = os.path.join(JSON_PATH, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    payment_data[filename] = json.load(f)
                except json.JSONDecodeError:
                    logger.warning(f"Warning: Could not decode JSON from {filename}")
                    payment_data[filename] = {}
    return payment_data

@app.route("/")
def index():
    payment_data_from_files = get_payment_data()
    app_settings = get_app_settings()
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

@app.route("/accounts", methods=["GET", "POST"])
def manage_accounts():
    """Endpoint to list accounts or update the selected account."""
    if request.method == "GET":
        owner_username = request.args.get("owner_username")
        payment_method = request.args.get("payment_method")
        
        if not all([owner_username, payment_method]):
            return jsonify({"success": False, "error": "Missing owner_username or payment_method"}), 400

        # Normalize payment method to find the correct JSON file
        normalized_slug = "bank-transfer" if payment_method in ["spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"] else payment_method
        filename = f"{normalized_slug}.json"
        filepath = os.path.join(JSON_PATH, filename)

        if not os.path.exists(filepath):
            return jsonify({"success": False, "error": f"Payment file not found: {filename}"}), 404

        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            accounts = data.get(owner_username, {}).get(payment_method, {}).get("accounts", [])
            selected_id = data.get(owner_username, {}).get(payment_method, {}).get("selected_id")
            
            return jsonify({"success": True, "accounts": accounts, "selected_id": selected_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    if request.method == "POST":
        data = request.json
        owner_username = data.get("owner_username")
        payment_method = data.get("payment_method")
        selected_id = data.get("selected_id")

        if not all([owner_username, payment_method, selected_id]):
            return jsonify({"success": False, "error": "Incomplete data"}), 400
        
        normalized_slug = "bank-transfer" if payment_method in ["spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"] else payment_method
        filename = f"{normalized_slug}.json"
        filepath = os.path.join(JSON_PATH, filename)
        
        if not os.path.exists(filepath):
            return jsonify({"success": False, "error": f"Payment file not found: {filename}"}), 404

        try:
            with open(filepath, "r+") as f:
                file_data = json.load(f)
                if owner_username in file_data and payment_method in file_data[owner_username]:
                    file_data[owner_username][payment_method]["selected_id"] = selected_id
                    f.seek(0)
                    json.dump(file_data, f, indent=4)
                    f.truncate()
                    return jsonify({"success": True, "message": "Account selection updated."})
                else:
                    return jsonify({"success": False, "error": "Owner or payment method not found in file."}), 404
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500


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
        except (KeyError, json.JSONDecodeError) as e:
            errors.append(f"Error processing file {filename}: {str(e)}")
        except Exception as e:
            errors.append(f"An unexpected error occurred with {filename}: {str(e)}")

    if errors:
        return jsonify({"success": False, "error": " | ".join(errors)}), 500

    return jsonify({"success": True, "message": "All selections updated successfully."})

@app.route("/update_setting", methods=["POST"])
def update_setting():
    """Updates a specific setting in the settings file."""
    data = request.json
    key = data.get("key")
    is_enabled = data.get("enabled")

    if key is None or is_enabled is None:
        return jsonify({"success": False, "error": "Missing key or enabled parameter"}), 400

    settings = get_app_settings()

    if key not in settings:
        return jsonify({"success": False, "error": f"Invalid setting key: {key}"}), 400

    settings[key] = is_enabled
    update_app_settings(settings)

    # If the setting is for verbose logging, re-setup the logger
    if key == "verbose_logging_enabled":
        setup_logging()

    status_text = "enabled" if is_enabled else "disabled"
    return jsonify({"success": True, "message": f"Setting '{key}' has been {status_text}."})

@app.route("/offer/toggle", methods=["POST"])
def toggle_offers():
    """Toggles all offers on or off."""
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
        settings = get_app_settings()
        settings["offers_enabled"] = is_enabled
        update_app_settings(settings)

    return jsonify({"success": success, "message": message})


@app.route("/start_trading", methods=["POST"])
def start_trading():
    global trading_process
    if trading_process and trading_process.poll() is None:
        return jsonify({"success": False, "message": "Trading app is already running."})
    try:
        python_executable = sys.executable
        trading_process = subprocess.Popen([python_executable, "-u", "main.py"])
        return jsonify({"success": True, "message": "Trading app started."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/stop_trading", methods=["POST"])
def stop_trading():
    global trading_process
    if trading_process and trading_process.poll() is None:
        trading_process.terminate()
        trading_process.wait(timeout=5)
        if trading_process.poll() is None:
             trading_process.kill()
        trading_process = None
        return jsonify({"success": True, "message": "Trading app stopped."})
    else:
        return jsonify({"success": False, "message": "Trading app is not running."})

@app.route("/trading_status")
def trading_status():
    global trading_process
    if trading_process and trading_process.poll() is None:
        return jsonify({"status": "Running"})
    else:
        return jsonify({"status": "Stopped"})

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
        return jsonify({"success": False, "error": f"Account '{account_name}' not found in configuration."}), 404

    token = fetch_token_with_retry(target_account)
    if not token:
        return jsonify({"success": False, "error": "Could not authenticate with the platform."}), 500

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in target_account["name"] else CHAT_URL_NOONES
    body = {"trade_hash": trade_hash, "message": message}

    if send_message_with_retry(chat_url, body, headers):
        return jsonify({"success": True, "message": "Message sent successfully!"})
    else:
        return jsonify({"success": False, "error": "Failed to send message via the platform API."}), 500

@app.route("/get_summary")
def get_summary():
    """Endpoint to get the daily trading summary."""
    summary = generate_daily_summary()
    if summary:
        return jsonify(summary)
    else:
        return jsonify({"error": "Could not generate summary"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)