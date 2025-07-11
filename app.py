import json
import os
import subprocess
import sys
import csv
from datetime import datetime, timedelta, timezone
from collections import deque, Counter
from flask import Flask, render_template, request, jsonify

# --- Import the TRADE_HISTORY variable from config ---
from config import TRADE_HISTORY

app = Flask(__name__)

# --- Configuration ---
JSON_PATH = "data/json"
SETTINGS_FILE = "data/settings.json"

# Create the JSON_PATH directory if it doesn't exist, to prevent errors on first run
if not os.path.exists(JSON_PATH):
    os.makedirs(JSON_PATH)

# Global variable to hold the trading bot process
trading_process = None

# --- Helper Functions ---
def get_app_settings():
    """Reads the application settings from the JSON file."""
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"night_mode_enabled": False, "afk_mode_enabled": False}, f)
        return {"night_mode_enabled": False, "afk_mode_enabled": False}
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            settings.setdefault("afk_mode_enabled", False)
            settings.setdefault("night_mode_enabled", False)
            return settings
    except (json.JSONDecodeError, FileNotFoundError):
        return {"night_mode_enabled": False, "afk_mode_enabled": False}

def update_app_settings(new_settings):
    """Writes the updated settings to the JSON file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(new_settings, f, indent=4)

def get_payment_data():
    """Reads all payment JSON files from JSON_PATH and returns their content."""
    payment_data = {}
    if not os.path.exists(JSON_PATH):
        print(f"Warning: Directory {JSON_PATH} not found.")
        return payment_data
    for filename in os.listdir(JSON_PATH):
        if filename.endswith(".json"):
            filepath = os.path.join(JSON_PATH, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    payment_data[filename] = json.load(f)
                except json.JSONDecodeError:
                    print(f"Warning: Could not decode JSON from {filename}")
                    payment_data[filename] = {}
    return payment_data

# --- Flask Routes ---
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
                user_grouped_data[owner_name][method_name] = {
                    "filename": filename,
                    "details": details_data
                }
    return render_template(
        "index.html",
        user_grouped_data=user_grouped_data,
        night_mode_enabled=app_settings.get("night_mode_enabled", False),
        afk_mode_enabled=app_settings.get("afk_mode_enabled", False)
    )

@app.route("/update_selection", methods=["POST"])
def update_selection():
    data = request.json
    filename = data.get("filename")
    owner_username = data.get("owner_username")
    payment_method = data.get("payment_method")
    selected_id = data.get("selected_id")
    if not all([filename, owner_username, payment_method, selected_id]):
        return jsonify({"success": False, "error": "Missing data"}), 400
    filepath = os.path.join(JSON_PATH, filename)
    if not os.path.exists(filepath):
        return jsonify({"success": False, "error": f"File not found: {filename}"}), 404
    try:
        with open(filepath, "r+", encoding="utf-8") as f:
            file_data = json.load(f)
            file_data[owner_username][payment_method]["selected_id"] = selected_id
            f.seek(0)
            json.dump(file_data, f, indent=4)
            f.truncate()
    except (KeyError, json.JSONDecodeError) as e:
        return jsonify({"success": False, "error": f"Error processing file: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"Unexpected error: {str(e)}"}), 500
    return jsonify({"success": True})

@app.route("/get_trade_stats")
def get_trade_stats():
    stats = {
        "trades_today": 0,
        "volume_today": 0,
        "success_rate": 100,
        "top_payment_method": "N/A",
    }
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"all_accounts_trades_{today_str}.csv"
    
    # --- This now uses the correct, imported path from your config ---
    filepath = os.path.join(TRADE_HISTORY, filename)

    if not os.path.exists(filepath):
        return jsonify(stats)

    all_trades = []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_trades = list(reader)

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=1)
    recent_trades = []
    for trade in all_trades:
        completed_at_str = trade.get("completed_at")
        if completed_at_str:
            try:
                # Handle potential timezone differences in isoformat strings
                if completed_at_str.endswith('Z'):
                    completed_at = datetime.fromisoformat(completed_at_str[:-1] + '+00:00')
                else:
                    completed_at = datetime.fromisoformat(completed_at_str)
                
                if completed_at.tzinfo is None:
                    completed_at = completed_at.replace(tzinfo=timezone.utc)

                if completed_at > cutoff_date:
                    recent_trades.append(trade)
            except ValueError:
                continue # Skip trades with malformed dates

    if not recent_trades:
        return jsonify(stats)

    successful_trades = [t for t in recent_trades if t.get('status') == 'successful']
    stats["trades_today"] = len(successful_trades)
    
    total_volume = sum(float(t.get("fiat_amount_requested", 0)) for t in successful_trades if t.get("fiat_amount_requested"))
    stats["volume_today"] = round(total_volume, 2)
    
    if len(recent_trades) > 0:
        stats["success_rate"] = round((len(successful_trades) / len(recent_trades)) * 100, 2)

    if successful_trades:
        payment_methods = [t.get("payment_method_name") for t in successful_trades if t.get("payment_method_name")]
        if payment_methods:
            stats["top_payment_method"] = Counter(payment_methods).most_common(1)[0][0]

    return jsonify(stats)

@app.route("/update_night_mode", methods=["POST"])
def update_night_mode():
    data = request.json
    is_enabled = data.get("night_mode_enabled")
    if is_enabled is None:
        return jsonify({"success": False, "error": "Missing parameter"}), 400
    settings = get_app_settings()
    settings["night_mode_enabled"] = is_enabled
    update_app_settings(settings)
    status_text = "enabled" if is_enabled else "disabled"
    return jsonify({"success": True, "message": f"Nighttime trading {status_text}."})

@app.route("/update_afk_mode", methods=["POST"])
def update_afk_mode():
    data = request.json
    is_enabled = data.get("afk_mode_enabled")
    if is_enabled is None:
        return jsonify({"success": False, "error": "Missing parameter"}), 400
    settings = get_app_settings()
    settings["afk_mode_enabled"] = is_enabled
    update_app_settings(settings)
    status_text = "enabled" if is_enabled else "disabled"
    return jsonify({"success": True, "message": f"AFK mode {status_text}."})

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
                print(f"Could not read or parse trades file {filename}: {e}")
    return jsonify(active_trades_data)

if __name__ == "__main__":
    app.run(debug=True, port=5001)