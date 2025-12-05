import requests
import logging
import json
import os
import time
from datetime import datetime, timezone
from dateutil.parser import isoparse
from config import DISCORD_WEBHOOKS, DISCORD_BOT_TOKEN, DISCORD_CHAT_LOG_CHANNEL_ID
from config_messages.discord_messages import (
    AMOUNT_VALIDATION_EMBEDS,
    EMAIL_VALIDATION_EMBEDS,
    NAME_VALIDATION_EMBEDS,
    DUPLICATE_RECEIPT_EMBEDS,
    COLORS,
    format_currency,
    NEW_TRADE_EMBED,
    CHAT_MESSAGE_EMBEDS,
    ATTACHMENT_EMBED,
    STATUS_UPDATE_EMBEDS
)
from .discord_thread_manager import get_thread_id
from config_messages.chat_messages import (
    TRADE_COMPLETION_MESSAGE,
    PAYMENT_RECEIVED_MESSAGE,
    PAYMENT_REMINDER_MESSAGE,
    AFK_MESSAGE,
    EXTENDED_AFK_MESSAGE,
    NO_ATTACHMENT_MESSAGE,
    ATTACHMENT_MESSAGE,
    ONLINE_REPLY_MESSAGE,
    OXXO_IN_BANK_TRANSFER_MESSAGE,
    THIRD_PARTY_ALLOWED_MESSAGE
)
from core.utils.profile import generate_user_profile

logger = logging.getLogger(__name__)

AUTOMATED_MESSAGES = set(
    TRADE_COMPLETION_MESSAGE +
    PAYMENT_RECEIVED_MESSAGE +
    PAYMENT_REMINDER_MESSAGE +
    AFK_MESSAGE +
    EXTENDED_AFK_MESSAGE +
    NO_ATTACHMENT_MESSAGE +
    ATTACHMENT_MESSAGE +
    ONLINE_REPLY_MESSAGE +
    OXXO_IN_BANK_TRANSFER_MESSAGE +
    THIRD_PARTY_ALLOWED_MESSAGE
)

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
    Sends a formatted embed message.
    For chat_log, it sends as the bot and adds a reaction.
    For others, it uses the webhook.
    """
    if alert_type == "chat_log" and trade_hash:
        thread_id = get_thread_id(trade_hash)
        channel_id = thread_id if thread_id else DISCORD_CHAT_LOG_CHANNEL_ID
        if not channel_id:
            logger.error("No channel ID found for chat log alert.")
            return

        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        payload = {"embeds": [embed_data]}
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                message_id = response.json()["id"]
                logger.info(f"Successfully sent chat message {message_id} as bot.")
                
                # Add reactions based on the message type
                title = embed_data.get("title", "")
                if "AUTOMATED MESSAGE" in title:
                    emoji = "🤖"
                elif "MESSAGE SENT" in title:
                    emoji = "📤"
                else: # Default reaction for buyer messages
                    emoji = "💬"
                
                if emoji:
                    time.sleep(0.5)
                    reaction_url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"
                    with requests.Session() as session:
                        session.headers.update(headers)
                        reaction_response = session.put(reaction_url, timeout=10)
                        if reaction_response.status_code == 204:
                            logger.info(f"Successfully added reaction to message {message_id}.")
                        else:
                            logger.error(f"Failed to add reaction to message {message_id}: {reaction_response.status_code} - {reaction_response.text}")
            else:
                logger.error(f"Failed to send chat message as bot: {response.status_code} - {response.text}")

        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while sending message as bot: {e}")

    else:
        # Original webhook logic for other alert types
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
    """Creates and sends a visually improved Discord embed for a new trade notification."""
    trade_hash = trade_data.get('trade_hash')
    
    # Platform-specific details
    if platform == "Paxful":
        embed_color = COLORS["PAXFUL_GREEN"]
        platform_emoji = "🅿️"
        trade_url = f"https://paxful.com/trade/{trade_hash}"
    else:  # Noones
        embed_color = COLORS["NOONES_GREEN"]
        platform_emoji = "💠"
        trade_url = f"https://noones.com/trade/{trade_hash}"

    # Get buyer info with stats
    buyer_username = trade_data.get('responder_username', 'N/A')
    buyer_line = f"**{buyer_username}**"
    
    if buyer_username != 'N/A':
        profile_data = generate_user_profile(buyer_username)
        if profile_data:
            trades_count = profile_data.get('successful_trades', 0)
            volume = profile_data.get('total_volume', 0.0)
            currency = trade_data.get('fiat_currency_code', '')
            volume_formatted = format_currency(volume, currency)
            buyer_line = f"**{buyer_username}** • {trades_count} trades • ${volume_formatted} volume"

    # Format amount using helper
    amount = trade_data.get('fiat_amount_requested', '0')
    currency = trade_data.get('fiat_currency_code', '')
    amount_formatted = format_currency(amount, currency)

    # Get timestamp
    try:
        start_time_str = trade_data.get('started_at')
        timestamp = isoparse(start_time_str) if start_time_str else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        timestamp = datetime.now(timezone.utc)

    # Build embed from template
    template = NEW_TRADE_EMBED
    embed = {
        "title": template["title_format"].format(platform_emoji=platform_emoji),
        "url": trade_url,
        "color": embed_color,
        "description": template["description_format"].format(buyer_line=buyer_line),
        "fields": [
            {"name": field["name"], "value": field.get("value") or field.get("value_format", "").format(
                amount_formatted=amount_formatted,
                payment_method=trade_data.get('payment_method_name', 'N/A'),
                owner_username=trade_data.get('owner_username', 'N/A'),
                trade_hash=trade_hash,
                trade_url=trade_url
            ), "inline": field["inline"]}
            for field in template["fields"]
        ],
        "timestamp": timestamp.isoformat(),
        "footer": {"text": template["footer"]}
    }

    if send:
        send_discord_embed(embed, alert_type="trades")
    else:
        return embed


def create_trade_status_update_embed(trade_hash, owner_username, new_status, platform):
    """Creates and sends a Discord embed for a trade status change with improved formatting."""
    
    trade_url = f"https://paxful.com/trade/{trade_hash}" if platform == "Paxful" else f"https://noones.com/trade/{trade_hash}"

    # Determine template based on status
    if new_status == 'Paid':
        template = STATUS_UPDATE_EMBEDS["paid"]
    elif new_status == 'Successful':
        template = STATUS_UPDATE_EMBEDS["successful"]
    elif 'Dispute' in new_status:
        template = STATUS_UPDATE_EMBEDS["disputed"]
    else:
        template = STATUS_UPDATE_EMBEDS["other"]

    # Build embed
    if "title_format" in template:
        title = template["title_format"].format(status=new_status)
    else:
        title = template["title"]

    embed = {
        "title": title,
        "color": COLORS[template["color"]],
        "description": template["description_format"].format(
            trade_hash=trade_hash,
            owner_username=owner_username,
            status=new_status
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "🤖 WillGang Bot"}
    }
    send_discord_embed(embed, alert_type="trades", trade_hash=trade_hash)


def create_attachment_embed(trade_hash, owner_username, author, image_path, platform, bank_name=None):
    """Creates and sends a Discord embed for a new attachment with improved formatting."""
    
    if platform == "Paxful":
        embed_color = COLORS["PAXFUL_GREEN"]
    else:  # Noones
        embed_color = COLORS["NOONES_GREEN"]

    template = ATTACHMENT_EMBED
    
    # Build fields
    fields = []
    if bank_name:
        fields.append({
            "name": template["bank_field"]["name"],
            "value": template["bank_field"]["value"].format(bank_name=bank_name),
            "inline": template["bank_field"]["inline"]
        })
    
    fields.append(template["image_field"])

    embed = {
        "title": template["title"],
        "color": embed_color,
        "description": template["description_format"].format(
            trade_hash=trade_hash,
            author=author,
            owner_username=owner_username
        ),
        "fields": fields,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "🤖 WillGang Bot"}
    }
    send_discord_embed_with_image(embed, image_path, alert_type="attachments", trade_hash=trade_hash)


def create_amount_validation_embed(trade_hash, owner_username, expected, found, currency):
    """Builds and sends an amount validation embed using templates."""
    if found is None:
        template = AMOUNT_VALIDATION_EMBEDS["not_found"]
        fields = [{"name": f["name"], "value": f["value"].format(owner_username=owner_username)} for f in template["fields"]]
    elif float(expected) == float(found):
        template = AMOUNT_VALIDATION_EMBEDS["matched"]
        fields = [{"name": f["name"], "value": f["value"].format(owner_username=owner_username, expected=float(expected), found=found, currency=currency)} for f in template["fields"]]
    else:
        template = AMOUNT_VALIDATION_EMBEDS["mismatch"]
        fields = [{"name": f["name"], "value": f["value"].format(owner_username=owner_username, expected=float(expected), found=found, currency=currency)} for f in template["fields"]]

    embed = {
        "title": template["title"],
        "color": COLORS["success"] if "✅" in template["title"] else (COLORS["warning"] if "⚠️" in template["title"] else COLORS["error"]),
        "description": template.get("description", ""),
        "fields": fields,
        "footer": {"text": f"Trade: {trade_hash}"}
    }
    send_discord_embed(embed, alert_type="attachments", trade_hash=trade_hash)

def create_email_validation_embed(trade_hash, success, account_name, details=None):
    """Builds and sends an email validation embed using templates."""
    template = EMAIL_VALIDATION_EMBEDS["success"] if success else EMAIL_VALIDATION_EMBEDS["failure"]

    formatted_fields = [
        {"name": field["name"], "value": field["value"].format(account_name=account_name)}
        for field in template["fields"]
    ]

    if success and details:
        formatted_fields.append({"name": "🏦 Bank Found", "value": f"**{details.get('validator', 'Unknown').replace('_', ' ').title()}**", "inline": True})
        formatted_fields.append({"name": "💰 Amount Found", "value": f"${details.get('found_amount', 0):,.2f}", "inline": True})
        formatted_fields.append({"name": "👤 Name Found", "value": f"{details.get('found_name', 'Unknown')}", "inline": True})

    embed = {
        "title": template["title"],
        "color": COLORS["success"] if success else COLORS["error"],
        "description": template.get("description", ""),
        "fields": formatted_fields,
        "footer": {"text": f"Trade: {trade_hash}"}
    }
    send_discord_embed(embed, alert_type="attachments", trade_hash=trade_hash)


def create_chat_message_embed(trade_hash, owner_username, author, message, platform):
    """Creates and sends a visually improved Discord embed for a new chat message."""
    
    trade_url = f"https://paxful.com/trade/{trade_hash}" if platform == "Paxful" else f"https://noones.com/trade/{trade_hash}"
    is_bot_owner = author in ["davidvs", "JoeWillgang"]
    is_automated = message in AUTOMATED_MESSAGES

    # Determine message type and get template
    if is_bot_owner and is_automated:
        template = CHAT_MESSAGE_EMBEDS["automated"]
    elif is_bot_owner and not is_automated:
        template = CHAT_MESSAGE_EMBEDS["manual"]
    else:
        template = CHAT_MESSAGE_EMBEDS["buyer"]

    # Get color
    if template["color_type"] == "info":
        embed_color = COLORS["info"]
    elif template["color_type"] == "platform":
        embed_color = COLORS["PAXFUL_GREEN"] if platform == "Paxful" else COLORS["NOONES_GREEN"]
    else:
        embed_color = COLORS["info"]

    # Truncate long messages
    message_preview = message if len(message) <= 900 else message[:900] + "..."

    embed = {
        "author": {"name": template["author_format"].format(author=author)},
        "color": embed_color,
        "description": template["description_format"].format(
            trade_hash=trade_hash,
            owner_username=owner_username,
            message=message_preview
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "🤖 WillGang Bot • View Trade"}
    }
    
    # Add title and URL for bot owner messages
    if is_bot_owner:
        embed['title'] = template["title"]
        embed['url'] = trade_url
         
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
        "description": template.get("description", ""),
        "fields": formatted_fields,
        "footer": {"text": f"Trade: {trade_hash}"}
    }
    send_discord_embed(embed, alert_type="attachments", trade_hash=trade_hash)

def create_duplicate_receipt_embed(trade_hash, owner_username, image_path, platform, previous_trade_info):
    """Builds and sends a duplicate receipt embed."""
    template = DUPLICATE_RECEIPT_EMBEDS["warning"]
    
    previous_trade_hash = previous_trade_info.get("trade_hash", "N/A")
    previous_owner = previous_trade_info.get("owner_username", "N/A")

    embed_data = {
        "title": template["title"],
        "color": COLORS.get("error", 0xFF0000),
        "description": template["description"].format(
            trade_hash=trade_hash,
            owner_username=owner_username,
            previous_trade_hash=previous_trade_hash,
            previous_owner=previous_owner
        ),
        "fields": [
            {"name": field["name"], "value": field["value"].format(
                trade_hash=trade_hash,
                owner_username=owner_username,
                previous_trade_hash=previous_trade_hash,
                previous_owner=previous_owner
            ), "inline": field.get("inline", False)}
            for field in template.get("fields", [])
        ],
        "footer": {"text": "🤖 WillGang Bot"}
    }
    send_discord_embed_with_image(embed_data, image_path, alert_type="attachments", trade_hash=trade_hash)
