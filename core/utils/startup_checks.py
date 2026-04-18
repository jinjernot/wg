# core/utils/startup_checks.py

import os
import sys
import logging

logger = logging.getLogger(__name__)

# Hard required — app WILL crash immediately if these are missing.
_REQUIRED_VARS: list[tuple[str, str]] = [
    ("DISCORD_BOT_TOKEN",              "discord_bot.py"),
    ("DISCORD_GUILD_ID",               "discord_bot.py"),
    ("DISCORD_ACTIVE_TRADES_CHANNEL_ID", "trade_commands.py"),
    ("NOONES_API_KEY_JOE",             "main.py / trading"),
    ("NOONES_SECRET_KEY_JOE",          "main.py / trading"),
    ("NOONES_API_KEY_DAVID",           "main.py / trading"),
    ("NOONES_SECRET_KEY_DAVID",        "main.py / trading"),
]

# Soft required — app runs but with degraded functionality.
_OPTIONAL_VARS: list[tuple[str, str]] = [
    ("TELEGRAM_BOT_TOKEN",  "Telegram alerts disabled"),
    ("TELEGRAM_CHAT_ID",    "Telegram alerts disabled"),
    ("DISCORD_WEBHOOK_LOGS","Discord error logging disabled"),
]


def validate_config(exit_on_failure: bool = True) -> bool:
    """
    Validates that all required environment variables are set.
    Logs clear errors for missing hard-required vars and warnings for
    optional ones.

    Args:
        exit_on_failure: If True (default), calls sys.exit(1) when any
                         hard-required var is missing.

    Returns:
        True if all hard-required vars are present, False otherwise.
    """
    missing_required = [
        (var, usage)
        for var, usage in _REQUIRED_VARS
        if not os.getenv(var)
    ]
    missing_optional = [
        (var, note)
        for var, note in _OPTIONAL_VARS
        if not os.getenv(var)
    ]

    # Warn about optional missing vars (degraded but functional)
    for var, note in missing_optional:
        logger.warning(f"[Config] Optional env var '{var}' not set — {note}.")

    # Fail hard on missing required vars
    if missing_required:
        for var, usage in missing_required:
            logger.critical(
                f"[Config] MISSING REQUIRED ENV VAR: '{var}' "
                f"(needed by: {usage})"
            )
        logger.critical(
            f"[Config] {len(missing_required)} required variable(s) missing. "
            "Bot cannot start safely. Check your .env file."
        )
        if exit_on_failure:
            sys.exit(1)
        return False

    logger.info("[Config] All required environment variables are present. ✓")
    return True
