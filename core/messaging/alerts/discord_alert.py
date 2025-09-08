# core/messaging/alerts/discord_alert.py
import requests
import logging
import json
import os
from config import DISCORD_WEBHOOKS
from config_messages.discord_messages import AMOUNT_VALIDATION_EMBEDS, EMAIL_VALIDATION_EMBEDS, COLORS

logger = logging.getLogger(__name__)

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
    """Creates and sends a Discord embed for a new trade notification, color-coded by platform."""
    platform_name = "Paxful" if platform == "Paxful" else "Noones"
    
    if platform == "Paxful":
        embed_color = COLORS["PAXFUL_GREEN"]
    elif platform == "Noones":
        embed_color = COLORS["NOONES_GREEN"]
    else:
        embed_color = COLORS["info"]

    embed = {
        "title": f"🚀 New {platform_name} Trade",
        "color": embed_color,
        "fields": [
            {"name": "Trade Hash", "value": f"`{trade_data.get('trade_hash')}`", "inline": True},
            {"name": "Account", "value": str(trade_data.get('owner_username')), "inline": True},
            {"name": "Amount", "value": f"{trade_data.get('fiat_amount_requested')} {trade_data.get('fiat_currency_code')}", "inline": False},
            {"name": "Buyer", "value": str(trade_data.get('responder_username')), "inline": False},
            {"name": "Payment Method", "value": str(trade_data.get('payment_method_name')), "inline": False},
        ], "footer": {"text": "WillGang Bot"}
    }
    send_discord_embed(embed, alert_type="trades")

def create_attachment_embed(trade_hash, owner_username, author, image_path, platform):
    """Creates and sends a Discord embed for a new attachment with the image."""
    if platform == "Paxful":
        embed_color = COLORS["PAXFUL_GREEN"]
    elif platform == "Noones":
        embed_color = COLORS["NOONES_GREEN"]
    else:
        embed_color = COLORS["info"]

    embed = {
        "title": "📄 New Attachment Uploaded",
        "color": embed_color,
        "description": f"Review attachment for trade `{trade_hash}`.",
        "fields": [ 
            {"name": "Account", "value": str(owner_username), "inline": True},
            {"name": "Uploaded By", "value": str(author), "inline": True} 
        ],
        "footer": {"text": "WillGang Bot"}
    }
    send_discord_embed_with_image(embed, image_path, alert_type="attachments")

def create_amount_validation_embed(trade_hash, owner_username, expected, found, currency):
    """Builds and sends an amount validation embed using templates."""
    if found is None:
        template = AMOUNT_VALIDATION_EMBEDS["not_found"]
        fields = [{"name": f["name"], "value": f["value"].format(owner_username=owner_username)} for f in template["fields"]]
    elif float(expected) == float(found):
        template = AMOUNT_VALIDATION_EMBEDS["matched"]
        fields = [{"name": f["name"], "value": f["value"].format(owner_username=owner_username, found=found, currency=currency)} for f in template["fields"]]
    else:
        template = AMOUNT_VALIDATION_EMBEDS["mismatch"]
        fields = [{"name": f["name"], "value": f["value"].format(owner_username=owner_username, expected=float(expected), found=found, currency=currency)} for f in template["fields"]]
    
    embed = {
        "title": template["title"],
        "color": COLORS["success"] if "✅" in template["title"] else (COLORS["warning"] if "⚠️" in template["title"] else COLORS["error"]),
        "fields": fields, "footer": {"text": f"Trade: {trade_hash}"}
    }
    send_discord_embed(embed, alert_type="attachments")

def create_email_validation_embed(trade_hash, success, account_name):
    """Builds and sends an email validation embed using templates."""
    template = EMAIL_VALIDATION_EMBEDS["success"] if success else EMAIL_VALIDATION_EMBEDS["failure"]
    
    formatted_fields = [
        {"name": field["name"], "value": field["value"].format(account_name=account_name)}
        for field in template["fields"]
    ]

    embed = {
        "title": template["title"],
        "color": COLORS["success"] if success else COLORS["error"],
        "fields": formatted_fields,
        "footer": {"text": f"Trade: {trade_hash}"}
    }
    send_discord_embed(embed, alert_type="attachments")

def create_chat_message_embed(trade_hash, owner_username, author, message, platform):
    """Creates and sends a Discord embed for a new chat message."""
    if platform == "Paxful":
        embed_color = COLORS["PAXFUL_GREEN"]
    elif platform == "Noones":
        embed_color = COLORS["NOONES_GREEN"]
    else:
        embed_color = COLORS["chat"]

    embed = {
        "title": "💬 New Chat Message",
        "color": embed_color,
        "description": message,
        "fields": [
            {"name": "Trade Hash", "value": f"`{trade_hash}`", "inline": True},
            {"name": "Account", "value": str(owner_username), "inline": True},
            {"name": "Author", "value": str(author), "inline": False},
        ],
        "footer": {"text": "WillGang Bot"}
    }
    send_discord_embed(embed, alert_type="chat_log")