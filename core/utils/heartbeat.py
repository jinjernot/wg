import logging
import requests
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class HeartbeatMonitor:
    def __init__(self, webhook_url, interval_seconds=300):
        """
        Initialize heartbeat monitor.
        
        Args:
            webhook_url: Discord webhook URL for logs channel
            interval_seconds: How often to update (default: 300 = 5 minutes)
        """
        self.webhook_url = webhook_url
        self.interval = interval_seconds
        self.message_id = None
        self.start_time = time.time()
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the heartbeat monitor in background thread"""
        if self.running:
            logger.warning("Heartbeat monitor already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("Heartbeat monitor started")
    
    def stop(self):
        """Stop the heartbeat monitor"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Heartbeat monitor stopped")
    
    def _run(self):
        """Main heartbeat loop"""
        # Send initial message
        self._send_initial_message()
        
        # Update periodically
        while self.running:
            time.sleep(self.interval)
            if self.running:
                self._update_message()
    
    def _send_initial_message(self):
        """Send the initial heartbeat message"""
        try:
            payload = {
                "embeds": [{
                    "title": "🟢 Bot Online",
                    "description": self._get_status_text(),
                    "color": 0x00ff00,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "footer": {"text": "Heartbeat updates every 5 minutes"}
                }]
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                params={"wait": "true"}  # Get message ID back
            )
            
            if response.status_code == 200:
                data = response.json()
                self.message_id = data.get("id")
                logger.info(f"Heartbeat message created: {self.message_id}")
            else:
                logger.error(f"Failed to create heartbeat message: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error sending initial heartbeat: {e}")
    
    def _update_message(self):
        """Update the existing heartbeat message"""
        if not self.message_id:
            logger.warning("No message ID, sending new message")
            self._send_initial_message()
            return
        
        try:
            # Extract webhook ID and token from URL
            # Format: https://discord.com/api/webhooks/{id}/{token}
            parts = self.webhook_url.rstrip('/').split('/')
            webhook_id = parts[-2]
            webhook_token = parts[-1]
            
            edit_url = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}/messages/{self.message_id}"
            
            payload = {
                "embeds": [{
                    "title": "🟢 Bot Online",
                    "description": self._get_status_text(),
                    "color": 0x00ff00,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "footer": {"text": "Heartbeat updates every 5 minutes"}
                }]
            }
            
            response = requests.patch(edit_url, json=payload)
            
            if response.status_code == 200:
                logger.debug("Heartbeat message updated")
            else:
                logger.error(f"Failed to update heartbeat: {response.status_code}")
                # Try sending new message
                self.message_id = None
                self._send_initial_message()
        
        except Exception as e:
            logger.error(f"Error updating heartbeat: {e}")
    
    def _get_status_text(self):
        """Generate status text with uptime"""
        uptime_seconds = int(time.time() - self.start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        
        uptime_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        
        return (
            f"**Status:** Running\n"
            f"**Uptime:** {uptime_str}\n"
            f"**Last Update:** <t:{int(time.time())}:R>"
        )
