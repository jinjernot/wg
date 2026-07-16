import logging
import json
import os
from core.messaging.message_sender import send_message_with_retry
from config_messages.welcome_david import *
from config_messages.welcome_joe import *
from config import APP_SETTINGS_FILE, CHAT_URL_NOONES

logger = logging.getLogger(__name__)

from core.utils.config_cache import get_cached_app_settings

OWNERS_CONFIG = {
    "davidvs": {
        "afk": WELCOME_AFK_MESSAGES_DAVID,
        "night": WELCOME_NIGHT_MESSAGES_DAVID,
        "default": WELCOME_MESSAGES_DAVID
    },
    "JoeWillgang": {
        "afk": WELCOME_AFK_MESSAGES_JOE,
        "night": WELCOME_NIGHT_MESSAGES_JOE,
        "default": WELCOME_MESSAGES_JOE
    }
}

def is_night_mode_enabled():
    """
    Checks the settings cache to see if nighttime messaging is enabled.
    Defaults to False if the file or key is missing.
    """
    settings = get_cached_app_settings()
    return settings.get("night_mode_enabled", False)

def is_afk_mode_enabled():
    """
    Checks the settings cache to see if AFK messaging is enabled.
    Defaults to False if the file or key is missing.
    """
    settings = get_cached_app_settings()
    return settings.get("afk_mode_enabled", False)


def send_welcome_message(trade, account, headers, max_retries=3):
    try:
        trade_hash = trade.get("trade_hash")
        payment_method_slug = trade.get("payment_method_slug", "").lower()
        owner_username = trade.get("owner_username", "unknown_user")

        # Determine if night mode or AFK mode is active
        night_mode_is_active = is_night_mode_enabled()
        afk_mode_is_active = is_afk_mode_enabled() # Check AFK mode
        logger.debug(f"Night mode active: {night_mode_is_active}, AFK mode active: {afk_mode_is_active}")

        # Map owner configuration — fail loudly if unknown rather than silently
        # sending the wrong payment details under davidvs's config.
        owner_config = OWNERS_CONFIG.get(owner_username)
        if owner_config is None:
            logger.warning(
                f"Unknown owner_username '{owner_username}' — no welcome config found. "
                f"Skipping welcome message for {trade_hash}."
            )
            return False

        # Select the appropriate message dictionary
        if afk_mode_is_active:
            message_dict = owner_config["afk"]
        elif night_mode_is_active:
            message_dict = owner_config["night"]
        else:
            message_dict = owner_config["default"]

        # Get the appropriate message from the selected dictionary
        message = message_dict.get(payment_method_slug, message_dict["default"])

        chat_url = CHAT_URL_NOONES

        # Build a local copy so we don't mutate the caller's shared dict.
        # self.headers is used concurrently by other operations on the same trade.
        local_headers = {**headers, "Content-Type": "application/x-www-form-urlencoded"}
        body = {"trade_hash": trade_hash, "message": message}

        # Send the message
        if send_message_with_retry(chat_url, body, local_headers, max_retries):
            logger.info(f"Welcome message sent for trade {trade_hash} ({account['name']})")
            return True
        else:
            logger.error(f"Failed to send welcome message for trade {trade_hash} ({account['name']})")
            return False
    except Exception as e:
        logger.error(f"Error sending welcome message: {e}")
        return False