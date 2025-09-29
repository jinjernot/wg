import logging
import json
import os
from config import SETTINGS_FILE

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
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=log_level, format=log_format, force=True)
    logging.getLogger('core.email_checker').setLevel(logging.INFO)
    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('oauth2client').setLevel(logging.WARNING)
    logging.getLogger('google.auth').setLevel(logging.WARNING)
    
    logging.info(f"Logger configured. Verbose logging: {'ON' if verbose_enabled else 'OFF'}.")