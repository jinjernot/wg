import logging
import requests
import os
from datetime import datetime

class DiscordHandler(logging.Handler):
    """
    A custom logging handler that sends logs to a Discord channel via a webhook.
    """
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url

    def emit(self, record):
        if not self.webhook_url:
            return

        # Get the raw error message from the log record.
        log_message = record.getMessage()
        
        # Discord embed field value limit is 1024 characters.
        if len(log_message) > 1000:
            log_message = log_message[:1000] + "\n... [truncated]"

        # Create a more structured and readable embed using fields.
        embed = {
            "title": f"❌ An Error Occurred",
            "color": 15158332,  # Red color
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Level",
                    "value": record.levelname,
                    "inline": True
                },
                {
                    "name": "Module",
                    "value": f"`{record.name}`",
                    "inline": True
                },
                {
                    "name": "Location",
                    "value": f"`{os.path.basename(record.pathname)}:{record.lineno}`",
                    "inline": False
                },
                {
                    "name": "Message",
                    "value": f"```\n{log_message}\n```",
                    "inline": False
                }
            ]
        }

        payload = {"embeds": [embed]}

        try:
            requests.post(self.webhook_url, json=payload, timeout=5)
        except requests.exceptions.RequestException as e:
            # Avoids an infinite loop if the request fails,
            # by not using the logger to report the failure.
            print(f"Failed to send log to Discord: {e}")