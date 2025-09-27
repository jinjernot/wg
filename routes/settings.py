import json
from flask import Blueprint, request, jsonify
import core.utils.web_utils as web_utils
from core.utils.log_config import setup_logging
from config import JSON_PATH
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