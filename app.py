import json
import os
import subprocess
import sys
from collections import deque # Used for efficiently reading last N lines of a file
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- Configuration ---
JSON_PATH = "data/json"  # Path to your payment method JSON files
TELEGRAM_LOG_FILE = "telegram_alerts.log" # Path to the log file for Telegram alerts
SETTINGS_FILE = "data/settings.json" # Path to the new settings file

# Create the JSON_PATH directory if it doesn't exist, to prevent errors on first run
if not os.path.exists(JSON_PATH):
    os.makedirs(JSON_PATH)

# Global variable to hold the trading bot process
trading_process = None

# --- Helper Functions ---
def get_app_settings():
    """Reads the application settings from the JSON file."""
    if not os.path.exists(SETTINGS_FILE):
        # If the file doesn't exist, create it with default values
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"night_mode_enabled": False, "afk_mode_enabled": False}, f) # Added afk_mode_enabled default
        return {"night_mode_enabled": False, "afk_mode_enabled": False} # Added afk_mode_enabled default
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            # Ensure new settings are always present, add with default if missing
            settings.setdefault("afk_mode_enabled", False) 
            settings.setdefault("night_mode_enabled", False)
            return settings
    except (json.JSONDecodeError, FileNotFoundError):
        return {"night_mode_enabled": False, "afk_mode_enabled": False} # Return default on error

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
                    payment_data[filename] = {} # Return empty dict for this file if error
    return payment_data

# --- Flask Routes ---
@app.route("/")
def index():
    """
    Renders the main dashboard page.
    It reads payment data and transforms it to be grouped by user
    before passing it to the HTML template.
    """
    payment_data_from_files = get_payment_data()
    app_settings = get_app_settings()

    user_grouped_data = {}
    for filename, owners_data in payment_data_from_files.items():
        for owner_name, methods_data in owners_data.items():
            if owner_name not in user_grouped_data:
                user_grouped_data[owner_name] = {}
            for method_name, details_data in methods_data.items():
                # Store the original filename and the details for each method
                user_grouped_data[owner_name][method_name] = {
                    "filename": filename, # Needed to know which file to update
                    "details": details_data
                }
    
    return render_template(
        "index.html",
        user_grouped_data=user_grouped_data,
        night_mode_enabled=app_settings.get("night_mode_enabled", False),
        afk_mode_enabled=app_settings.get("afk_mode_enabled", False) # Pass new AFK setting
    )

@app.route("/update_selection", methods=["POST"])
def update_selection():
    """
    Updates the 'selected_id' for a given payment method in the
    appropriate JSON file.
    """
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
        print(f"Error updating JSON file {filename}: {e}")
        return jsonify({"success": False, "error": f"Error processing file: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected error updating JSON file {filename}: {e}")
        return jsonify({"success": False, "error": f"Unexpected error: {str(e)}"}), 500

    return jsonify({"success": True})

@app.route("/get_telegram_messages")
def get_telegram_messages():
    """Reads the last 15 lines from the telegram log file."""
    if not os.path.exists(TELEGRAM_LOG_FILE):
        return jsonify([])
    
    try:
        with open(TELEGRAM_LOG_FILE, "r", encoding="utf-8") as f:
            last_15_lines = list(deque(f, 15))
            cleaned_lines = [line.strip() for line in last_15_lines]
            return jsonify(cleaned_lines)
    except Exception as e:
        print(f"Error reading telegram log file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/update_night_mode", methods=["POST"])
def update_night_mode():
    """Updates the nighttime trading mode status."""
    data = request.json
    is_enabled = data.get("night_mode_enabled")

    if is_enabled is None:
        return jsonify({"success": False, "error": "Missing parameter"}), 400

    settings = get_app_settings()
    settings["night_mode_enabled"] = is_enabled
    update_app_settings(settings)
    
    status_text = "enabled" if is_enabled else "disabled"
    return jsonify({"success": True, "message": f"Nighttime trading {status_text}."})

@app.route("/update_afk_mode", methods=["POST"]) # New route for AFK mode
def update_afk_mode():
    """Updates the AFK mode status."""
    data = request.json
    is_enabled = data.get("afk_mode_enabled")

    if is_enabled is None:
        return jsonify({"success": False, "error": "Missing parameter"}), 400

    settings = get_app_settings()
    settings["afk_mode_enabled"] = is_enabled
    update_app_settings(settings)
    
    status_text = "enabled" if is_enabled else "disabled"
    return jsonify({"success": True, "message": f"AFK mode {status_text}."})

# --- Routes for Trading App Control ---
@app.route("/start_trading", methods=["POST"])
def start_trading():
    """Starts the main.py script as a background process."""
    global trading_process
    if trading_process and trading_process.poll() is None:
        return jsonify({"success": False, "message": "Trading app is already running."})

    try:
        python_executable = sys.executable
        trading_process = subprocess.Popen([python_executable, "-u", "main.py"])
        return jsonify({"success": True, "message": "Trading app started."})
    except Exception as e:
        print(f"Error starting trading app: {e}")
        return jsonify({"success": False, "message": str(e)})

@app.route("/stop_trading", methods=["POST"])
def stop_trading():
    """Stops the trading app process if it's running."""
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
    """Checks if the trading app process is running."""
    global trading_process
    if trading_process and trading_process.poll() is None:
        return jsonify({"status": "Running"})
    else:
        return jsonify({"status": "Stopped"})

@app.route("/get_active_trades")
def get_active_trades():
    """
    Scans the root directory for *_trades.json files and returns their content.
    """
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