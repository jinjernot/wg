import logging
import json
import os
from logging.handlers import RotatingFileHandler
from config import SETTINGS_FILE, DISCORD_WEBHOOKS
from core.messaging.alerts.discord_logging_handler import DiscordHandler

def setup_logging():
    """Reads settings and configures the root logger."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
            verbose_enabled = settings.get("verbose_logging_enabled", True)
        else:
            verbose_enabled = True
    except (json.JSONDecodeError, IOError):
        verbose_enabled = True

    log_level = logging.INFO if verbose_enabled else logging.WARNING
    log_format = '%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s'
    
    logging.basicConfig(level=log_level, format=log_format, force=True)

    log_dir = os.path.join("data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    error_log_path = os.path.join(log_dir, "error.log")

    file_handler = RotatingFileHandler(
        error_log_path, maxBytes=5*1024*1024, backupCount=5
    )
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    logging.getLogger().addHandler(file_handler)

    # --- Discord Handler for Errors ---
    discord_webhook_url = DISCORD_WEBHOOKS.get("logs")
    if discord_webhook_url:
        discord_handler = DiscordHandler(discord_webhook_url)
        discord_handler.setLevel(logging.ERROR)
        # Use a more concise format for Discord
        discord_formatter = logging.Formatter(
            '%(name)s:%(lineno)d\n%(message)s'
        )
        discord_handler.setFormatter(discord_formatter)
        logging.getLogger().addHandler(discord_handler)
        logging.info("Discord error logging is enabled.")
    else:
        logging.warning("Webhook URL for 'logs' not found in DISCORD_WEBHOOKS. Discord error logging is disabled.")


    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('oauth2client').setLevel(logging.WARNING)
    logging.getLogger('google.auth').setLevel(logging.WARNING)
    logging.info(f"Logger configured. Verbose logging: {'ON' if verbose_enabled else 'OFF'}. Errors will be logged to {error_log_path}")