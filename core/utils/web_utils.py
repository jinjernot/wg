import os
import json
import logging
from config import JSON_PATH, SETTINGS_FILE

logger = logging.getLogger(__name__)

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
        return {
            "night_mode_enabled": False,
            "afk_mode_enabled": False,
            "verbose_logging_enabled": True,
            "offers_enabled": False
        }

def update_app_settings(new_settings):
    """Writes the updated settings to the file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(new_settings, f, indent=4)

def get_payment_data():
    """Loads all payment method JSON files."""
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