import logging
import requests

class DiscordHandler(logging.Handler):
    """
    A custom logging handler that sends logs to a Discord channel via a webhook.
    """
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url

    def emit(self, record):
        if not self.webhook_url or "YOUR_WEBHOOK_URL_HERE" in self.webhook_url:
            return

        log_entry = self.format(record)
        
        # Discord embed description limit is 4096
        if len(log_entry) > 4000:
            log_entry = log_entry[:4000] + "\n... [truncated]"

        embed = {
            "title": f"❌ {record.levelname}: An Error Occurred",
            "description": f"```python\n{log_entry}\n```",
            "color": 15158332  # Red color
        }

        payload = {"embeds": [embed]}

        try:
            requests.post(self.webhook_url, json=payload, timeout=5)
        except requests.exceptions.RequestException as e:
            # Avoids an infinite loop if the request fails,
            # by not using the logger to report the failure.
            print(f"Failed to send log to Discord: {e}")