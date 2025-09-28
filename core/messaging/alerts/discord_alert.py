import requests
import logging
import json
import os
from config import DISCORD_WEBHOOKS
from config_messages.discord_messages import (
    AMOUNT_VALIDATION_EMBEDS,
    EMAIL_VALIDATION_EMBEDS,
    NAME_VALIDATION_EMBEDS,
    COLORS
)
from .discord_thread_manager import get_thread_id

logger = logging.getLogger(__name__)

def _send_discord_request(webhook_url, payload=None, files=None):
    """Helper function to send HTTP requests to Discord."""
    if not webhook_url or "YOUR_WEBHOOK_URL_HERE" in webhook_url:
        return False, "Webhook URL is not configured.", None

    try:
        if files:
            response = requests.post(webhook_url, data={"payload_json": json.dumps(payload)}, files=files)
        else:
            response = requests.post(webhook_url, json=payload)

        if response.status_code in [200, 204]:
            return True, "Success", None
        else:
            error_code = None
            try:
                error_code = response.json().get("code")
            except json.JSONDecodeError:
                pass # No JSON body
            return False, f"{response.status_code} - {response.text}", error_code
    except Exception as e:
        return False, str(e), None

def send_discord_embed(embed_data, alert_type="default", trade_hash=None):
    """
    Sends a formatted embed message to the appropriate Discord webhook.
    Routes to the chat_log webhook if a trade_hash is provided.
    Retries in the main channel if the thread is archived.
    """
    if trade_hash:
        webhook_url_base = DISCORD_WEBHOOKS.get("chat_log", DISCORD_WEBHOOKS.get("default"))
    else:
        webhook_url_base = DISCORD_WEBHOOKS.get(alert_type, DISCORD_WEBHOOKS.get("default"))

    webhook_url = webhook_url_base
    thread_id = None

    if trade_hash:
        thread_id = get_thread_id(trade_hash)
        if thread_id:
            webhook_url += f"?thread_id={thread_id}"

    payload = {"embeds": [embed_data]}

    success, message, error_code = _send_discord_request(webhook_url, payload)

    if not success and error_code == 10003 and thread_id:
        logger.warning(f"Failed to send to thread {thread_id} (likely archived). Retrying in main channel.")
        success, message, _ = _send_discord_request(webhook_url_base, payload)

    if success:
        logger.info(f"Discord alert ('{alert_type}') sent successfully to {'thread '+thread_id if thread_id else 'main channel'}.")
    else:
        logger.error(f"Failed to send Discord alert ('{alert_type}'): {message}")


def send_discord_embed_with_image(embed_data, image_path, alert_type="default", trade_hash=None):
    """
    Sends an embed message along with an image file.
    Routes to the chat_log webhook if a trade_hash is provided.
    Retries in the main channel if the thread is archived.
    """
    if trade_hash:
        webhook_url_base = DISCORD_WEBHOOKS.get("chat_log", DISCORD_WEBHOOKS.get("default"))
    else:
        webhook_url_base = DISCORD_WEBHOOKS.get(alert_type, DISCORD_WEBHOOKS.get("default"))

    webhook_url = webhook_url_base
    thread_id = None

    if trade_hash:
        thread_id = get_thread_id(trade_hash)
        if thread_id:
            webhook_url += f"?thread_id={thread_id}"

    payload = {"embeds": [embed_data]}

    try:
        with open(image_path, 'rb') as f:
            files = {'file1': (os.path.basename(image_path), f, 'image/png')}
            success, message, error_code = _send_discord_request(webhook_url, payload, files=files)

        if not success and error_code == 10003 and thread_id:
            logger.warning(f"Failed to send image to thread {thread_id} (likely archived). Retrying in main channel.")
            with open(image_path, 'rb') as f:
                files = {'file1': (os.path.basename(image_path), f, 'image/png')}
                success, message, _ = _send_discord_request(webhook_url_base, payload, files=files)

        if success:
            logger.info(f"Discord attachment alert ('{alert_type}') sent successfully.")
        else:
            logger.error(f"Failed to send Discord attachment alert ('{alert_type}'): {message}")
    except IOError as e:
        logger.error(f"Could not open image file for Discord alert: {e}")

def create_new_trade_embed(trade_data, platform, send=True):
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
    if send:
        send_discord_embed(embed, alert_type="trades")
    else:
        return embed

def create_trade_status_update_embed(trade_hash, owner_username, new_status, platform):
    """Creates and sends a Discord embed for a trade status change."""
    
    # Determine the title and color based on the new status
    if new_status == 'Paid':
        title = "💰 Trade Paid"
        color = COLORS.get("warning", 0xFFA500)
    elif new_status == 'Successful':
        title = "✅ Trade Completed"
        color = COLORS.get("success", 0x00FF00)
    elif 'Dispute' in new_status:
        title = "⚠️ Trade Disputed"
        color = COLORS.get("error", 0xFF0000)
    else:
        title = "🔄 Trade Status Updated"
        color = COLORS.get("info", 0x5865F2)

    embed = {
        "title": title,
        "color": color,
        "description": f"The status for trade `{trade_hash}` has been updated.",
        "fields": [
            {"name": "Account", "value": str(owner_username), "inline": True},
            {"name": "New Status", "value": f"**{new_status}**", "inline": True}
        ],
        "footer": {"text": "WillGang Bot"}
    }
    send_discord_embed(embed, alert_type="trades", trade_hash=trade_hash)


def create_attachment_embed(trade_hash, owner_username, author, image_path, platform, bank_name=None):
    """Creates and sends a Discord embed for a new attachment with the image."""
    if platform == "Paxful":
        embed_color = COLORS["PAXFUL_GREEN"]
    elif platform == "Noones":
        embed_color = COLORS["NOONES_GREEN"]
    else:
        embed_color = COLORS["info"]

    fields = [
        {"name": "Account", "value": str(owner_username), "inline": True},
        {"name": "Uploaded By", "value": str(author), "inline": True}
    ]

    if bank_name:
        fields.append({"name": "Identified Bank", "value": str(bank_name), "inline": False})

    embed = {
        "title": "📄 New Attachment Uploaded",
        "color": embed_color,
        "description": f"Review attachment for trade `{trade_hash}`.",
        "fields": fields,
        "footer": {"text": "WillGang Bot"}
    }
    send_discord_embed_with_image(embed, image_path, alert_type="attachments", trade_hash=trade_hash)

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
    send_discord_embed(embed, alert_type="attachments", trade_hash=trade_hash)

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
    send_discord_embed(embed, alert_type="attachments", trade_hash=trade_hash)

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
    send_discord_embed(embed, alert_type="chat_log", trade_hash=trade_hash)

def create_name_validation_embed(trade_hash, success, account_name):
    """Builds and sends a name validation embed using templates."""
    template = NAME_VALIDATION_EMBEDS["success"] if success else NAME_VALIDATION_EMBEDS["failure"]

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
    send_discord_embed(embed, alert_type="attachments", trade_hash=trade_hash)