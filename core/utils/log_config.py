import logging
import json
import os
from logging.handlers import RotatingFileHandler
from config import APP_SETTINGS_FILE, DISCORD_WEBHOOKS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOPICS
from core.messaging.alerts.discord_logging_handler import DiscordHandler
from core.messaging.alerts.telegram_logging_handler import TelegramHandler

def setup_logging():
    """Reads settings and configures the root logger."""
    try:
        if os.path.exists(APP_SETTINGS_FILE):
            with open(APP_SETTINGS_FILE, "r") as f:
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

    # Rotate at 50 MB, keep 3 backups — prevents disk-full crashes.
    # 50 MB cap makes rotation rare for an error-only log, minimising
    # the risk of Windows multi-process file-rename contention.
    file_handler = RotatingFileHandler(
        error_log_path, maxBytes=50 * 1024 * 1024, backupCount=3
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

    # --- Telegram Handler for Errors ---
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        telegram_handler = TelegramHandler(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOPICS.get("logs"))
        telegram_handler.setLevel(logging.ERROR)
        # Use a more concise format for Telegram (custom format already escapes markdown)
        telegram_formatter = logging.Formatter('%(message)s')
        telegram_handler.setFormatter(telegram_formatter)
        logging.getLogger().addHandler(telegram_handler)
        logging.info("Telegram error logging is enabled.")
    else:
        logging.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not provided. Telegram error logging disabled.")


    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('oauth2client').setLevel(logging.WARNING)
    logging.getLogger('google.auth').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.info(f"Logger configured. Verbose logging: {'ON' if verbose_enabled else 'OFF'}. Errors will be logged to {error_log_path}")