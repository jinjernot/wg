import logging
import json
import os

from core.messaging.message_sender import send_message_with_retry

from config_messages.welcome_david import *
from config_messages.welcome_joe import *
from config import *

def is_night_mode_enabled():
    """
    Checks the settings file to see if nighttime messaging is enabled.
    Defaults to False if the file or key is missing.
    """
    settings_file = os.path.join("data", "settings.json")
    if not os.path.exists(settings_file):
        return False
    try:
        with open(settings_file, "r") as f:
            settings = json.load(f)
        return settings.get("night_mode_enabled", False)
    except (json.JSONDecodeError, Exception) as e:
        logging.error(f"Could not read settings file: {e}")
        return False

def is_afk_mode_enabled():
    """
    Checks the settings file to see if AFK messaging is enabled.
    Defaults to False if the file or key is missing.
    """
    settings_file = os.path.join("data", "settings.json")
    if not os.path.exists(settings_file):
        return False
    try:
        with open(settings_file, "r") as f:
            settings = json.load(f)
        return settings.get("afk_mode_enabled", False)
    except (json.JSONDecodeError, Exception) as e:
        logging.error(f"Could not read settings file: {e}")
        return False


def send_welcome_message(trade, account, headers, max_retries=3):
    trade_hash = trade.get("trade_hash")
    payment_method_slug = trade.get("payment_method_slug", "").lower()
    owner_username = trade.get("owner_username", "unknown_user")

    # Determine if night mode or AFK mode is active
    night_mode_is_active = is_night_mode_enabled()
    afk_mode_is_active = is_afk_mode_enabled() # Check AFK mode
    logging.debug(f"Night mode active: {night_mode_is_active}, AFK mode active: {afk_mode_is_active}")

    # Select the appropriate message dictionary based on owner and mode status
    if owner_username == "davidvs":
        if afk_mode_is_active:
            message_dict = WELCOME_AFK_MESSAGES_DAVID
        elif night_mode_is_active:
            message_dict = WELCOME_NIGHT_MESSAGES_DAVID
        else:
            message_dict = WELCOME_MESSAGES_DAVID
    elif owner_username == "JoeWillgang":
        if afk_mode_is_active:
            message_dict = WELCOME_AFK_MESSAGES_JOE
        elif night_mode_is_active:
            message_dict = WELCOME_NIGHT_MESSAGES_JOE
        else:
            message_dict = WELCOME_MESSAGES_JOE
    else:
        # Default to David's messages if owner is unknown
        if afk_mode_is_active:
            message_dict = WELCOME_AFK_MESSAGES_DAVID
        elif night_mode_is_active:
            message_dict = WELCOME_NIGHT_MESSAGES_DAVID
        else:
            message_dict = WELCOME_MESSAGES_DAVID

    # Get the appropriate message from the selected dictionary
    message = message_dict.get(payment_method_slug, message_dict["default"])

    # Determine which chat URL to use
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in account["name"] else CHAT_URL_NOONES

    # Prepare the message body
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    body = {"trade_hash": trade_hash, "message": message}

    # Send the message
    if send_message_with_retry(chat_url, body, headers, max_retries):
        print(f"Welcome message sent for trade {trade_hash} ({account['name']})")
    else:
        print(f"Failed to send welcome message for trade {trade_hash} ({account['name']})")