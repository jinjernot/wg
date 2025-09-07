# core/messaging/discord_alert.py
import requests
import logging
import json
import os
from config import DISCORD_WEBHOOKS
from config_messages.discord_messages import AMOUNT_VALIDATION_EMBEDS, EMAIL_VALIDATION_EMBEDS

logger = logging.getLogger(__name__)

# --- Color Codes for Different Alert Types ---
COLORS = {
    "info": 3447003,    # Blue
    "success": 3066993,  # Green
    "warning": 15105570, # Orange
    "error": 15158332,   # Red
    "chat": 8359053,     # Greyple
}

def _send_discord_request(webhook_url, payload=None, files=None):
    """Helper function to send HTTP requests to Discord."""
    if not webhook_url or "YOUR_WEBHOOK_URL_HERE" in webhook_url:
        return False, "Webhook URL is not configured."

    try:
        if files:
            response = requests.post(webhook_url, data={"payload_json": json.dumps(payload)}, files=files)
        else:
            response = requests.post(webhook_url, json=payload)
        
        if response.status_code in [200, 204]:
            return True, "Success"
        else:
            return False, f"{response.status_code} - {response.text}"
    except Exception as e:
        return False, str(e)

def send_discord_embed(embed_data, alert_type="default"):
    """Sends a formatted embed message to the appropriate Discord webhook."""
    webhook_url = DISCORD_WEBHOOKS.get(alert_type, DISCORD_WEBHOOKS.get("default"))
    payload = {"embeds": [embed_data]}
    
    success, message = _send_discord_request(webhook_url, payload)
    if success:
        logger.info(f"Discord alert ('{alert_type}') sent successfully.")
    else:
        logger.error(f"Failed to send Discord alert ('{alert_type}'): {message}")

def send_discord_embed_with_image(embed_data, image_path, alert_type="default"):
    """Sends an embed message along with an image file."""
    webhook_url = DISCORD_WEBHOOKS.get(alert_type, DISCORD_WEBHOOKS.get("default"))
    payload = {"embeds": [embed_data]}

    try:
        with open(image_path, 'rb') as f:
            files = {'file1': (os.path.basename(image_path), f, 'image/png')}
            success, message = _send_discord_request(webhook_url, payload, files)
        
        if success:
            logger.info(f"Discord attachment alert ('{alert_type}') sent successfully.")
        else:
            logger.error(f"Failed to send Discord attachment alert ('{alert_type}'): {message}")
    except IOError as e:
        logger.error(f"Could not open image file for Discord alert: {e}")

def create_new_trade_embed(trade_data, platform):
    """Creates and sends a Discord embed for a new trade notification."""
    platform_name = "Paxful" if platform == "Paxful" else "Noones"
    embed = {
        "title": f"🚀 New {platform_name} Trade",
        "color": COLORS["info"],
        "fields": [
            {"name": "Trade Hash", "value": f"`{trade_data.get('trade_hash')}`", "inline": True},
            {"name": "Amount", "value": f"{trade_data.get('fiat_amount_requested')} {trade_data.get('fiat_currency_code')}", "inline": True},
            {"name": "Buyer", "value": str(trade_data.get('responder_username')), "inline": False},
            {"name": "Payment Method", "value": str(trade_data.get('payment_method_name')), "inline": False},
        ], "footer": {"text": "WillGang Bot"}
    }
    send_discord_embed(embed, alert_type="trades")

def create_attachment_embed(trade_hash, author, image_path):
    """Creates and sends a Discord embed for a new attachment with the image."""
    embed = {
        "title": "📄 New Attachment Uploaded",
        "color": COLORS["info"],
        "description": f"Review attachment for trade `{trade_hash}`.",
        "fields": [ {"name": "Uploaded By", "value": str(author), "inline": True} ],
        "footer": {"text": "WillGang Bot"}
    }
    send_discord_embed_with_image(embed, image_path, alert_type="attachments")

def create_amount_validation_embed(trade_hash, expected, found, currency):
    """Builds and sends an amount validation embed using templates."""
    if found is None:
        template = AMOUNT_VALIDATION_EMBEDS["not_found"]
        fields = template["fields"]
    elif float(expected) == float(found):
        template = AMOUNT_VALIDATION_EMBEDS["matched"]
        fields = [{"name": f["name"], "value": f["value"].format(found=found, currency=currency)} for f in template["fields"]]
    else:
        template = AMOUNT_VALIDATION_EMBEDS["mismatch"]
        fields = [{"name": f["name"], "value": f["value"].format(expected=float(expected), found=found, currency=currency)} for f in template["fields"]]
    
    embed = {
        "title": template["title"],
        "color": COLORS["success"] if "✅" in template["title"] else (COLORS["warning"] if "⚠️" in template["title"] else COLORS["error"]),
        "fields": fields, "footer": {"text": f"Trade: {trade_hash}"}
    }
    send_discord_embed(embed, alert_type="attachments")

def create_email_validation_embed(trade_hash, success):
    """Builds and sends an email validation embed using templates."""
    template = EMAIL_VALIDATION_EMBEDS["success"] if success else EMAIL_VALIDATION_EMBEDS["failure"]
    embed = {
        "title": template["title"], "color": COLORS["success"] if success else COLORS["error"],
        "fields": template["fields"], "footer": {"text": f"Trade: {trade_hash}"}
    }
    send_discord_embed(embed, alert_type="validations")

def create_chat_message_embed(trade_hash, author, message):
    """Creates and sends a Discord embed for a new chat message."""
    embed = {
        "title": "💬 New Chat Message",
        "color": COLORS["chat"],
        "description": message,
        "fields": [
            {"name": "Author", "value": str(author), "inline": True},
            {"name": "Trade Hash", "value": f"`{trade_hash}`", "inline": True},
        ],
        "footer": {"text": "WillGang Bot"}
    }
    send_discord_embed(embed, alert_type="chat_log")