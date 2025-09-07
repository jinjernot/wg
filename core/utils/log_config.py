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
            # Default to True (verbose) if the key doesn't exist
            verbose_enabled = settings.get("verbose_logging_enabled", True)
        else:
            verbose_enabled = True
    except (json.JSONDecodeError, IOError):
        verbose_enabled = True # Default to verbose on error

    # Use INFO for verbose and WARNING for minimal
    log_level = logging.INFO if verbose_enabled else logging.WARNING
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Use force=True to allow re-configuration (requires Python 3.8+)
    logging.basicConfig(level=log_level, format=log_format, force=True)

    # --- Keep Email Logs Visible ---
    # This ensures logs from email_checker are always shown, even in minimal mode
    logging.getLogger('core.email_checker').setLevel(logging.INFO)
    
    # Quieten down noisy libraries
    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('oauth2client').setLevel(logging.WARNING)
    logging.getLogger('google.auth').setLevel(logging.WARNING)
    
    logging.info(f"Logger configured. Verbose logging: {'ON' if verbose_enabled else 'OFF'}.")