import logging
import requests
import os
import re

class TelegramHandler(logging.Handler):
    """
    A custom logging handler that sends logs to a Telegram topic.
    """
    # Class-level set to track credential errors already sent
    _sent_credential_errors = set()
    
    def __init__(self, bot_token, chat_id, thread_id=None):
        super().__init__()
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.thread_id = thread_id

    def emit(self, record):
        if not self.bot_token or not self.chat_id:
            return

        # Get the raw error message from the log record.
        log_message = record.getMessage()

        # Skip repeated "Credentials file not found" errors - only alert once per credential
        if "Credentials file not found for" in log_message:
            # Extract the credential identifier from the message
            if log_message not in self._sent_credential_errors:
                # First time seeing this error, add it to the set and allow it to be sent
                self._sent_credential_errors.add(log_message)
            else:
                # Already sent this error before, skip it
                return
        
        # Telegram message length limit is ~4096 characters. Look out for Markdown wrappers scaling out
        if len(log_message) > 4000:
            log_message = log_message[:4000] + "\n... [truncated]"

        # Escape characters for Telegram MarkdownV2 safely
        escape_chars = r'_*[]()~`>#+-=|{}.!'
        def escape_markdown(text):
            if not isinstance(text, str):
                text = str(text)
            return re.sub(f'(?<!\\\\)([{re.escape(escape_chars)}])', r'\\\1', text)

        safe_message = escape_markdown(log_message)
        level_name = escape_markdown(record.levelname)
        name = escape_markdown(record.name)
        location = escape_markdown(f"{os.path.basename(record.pathname)}:{record.lineno}")

        msg_body = (
            f"❌ *An Error Occurred*\n"
            f"*Level:* {level_name}\n"
            f"*Module:* `{name}`\n"
            f"*Location:* `{location}`\n"
            f"```\n{safe_message}\n```"
        )

        payload = {
            "chat_id": self.chat_id,
            "text": msg_body,
            "parse_mode": "MarkdownV2"
        }
        
        if self.thread_id:
            payload["message_thread_id"] = self.thread_id

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        try:
            requests.post(url, json=payload, timeout=5)
        except requests.exceptions.RequestException as e:
            # Avoids an infinite loop if the request fails
            print(f"Failed to send log to Telegram: {e}")
