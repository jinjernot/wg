
import requests
import logging
import json
import os
import time
import random
import threading
from datetime import datetime, timezone
from dateutil.parser import isoparse
from config import DISCORD_WEBHOOKS, DISCORD_BOT_TOKEN, DISCORD_CHAT_LOG_CHANNEL_ID, BOT_OWNER_USERNAMES
from config_messages.discord_messages import (
    AMOUNT_VALIDATION_EMBEDS,
    EMAIL_VALIDATION_EMBEDS,
    NAME_VALIDATION_EMBEDS,
    DUPLICATE_RECEIPT_EMBEDS,
    COLORS,
    format_currency,
    NEW_TRADE_EMBED,
    HIGH_VALUE_TRADE_EMBED,
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
    THIRD_PARTY_ALLOWED_MESSAGE,
    RELEASE_MESSAGE,
    DELAY_MESSAGE,
    SPAM_WARNING_MESSAGE,
)
from core.utils.profile import generate_user_profile

logger = logging.getLogger(__name__)

_discord_api_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Discord flood filter — mirrors the one in telegram_alert.py.
# Prevents the same embed/message from being sent more than once within
# _DISCORD_FLOOD_WINDOW seconds, even across concurrent background threads.
# Keyed on the first _DISCORD_SIG_LEN chars of the serialised payload.
# ---------------------------------------------------------------------------
_DISCORD_FLOOD_WINDOW = 5 * 60   # 5 minutes
_DISCORD_SIG_LEN      = 200      # chars used as the payload "signature"
_discord_flood_cache: dict[str, float] = {}
_discord_flood_lock  = threading.Lock()

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
    THIRD_PARTY_ALLOWED_MESSAGE +
    RELEASE_MESSAGE +
    DELAY_MESSAGE +
    SPAM_WARNING_MESSAGE
)

def _send_discord_request(webhook_url, payload=None, files=None, max_retries=5):
    """Helper function to send HTTP requests to Discord with automatic rate-limit retry."""
    if not webhook_url or "YOUR_WEBHOOK_URL_HERE" in webhook_url:
        return False, "Webhook URL is not configured.", None

    logger.debug(f"[WEBHOOK] Sending request to: {webhook_url!r}")

    # --- Flood filter ---
    sig = json.dumps(payload, sort_keys=True)[:_DISCORD_SIG_LEN] if payload else webhook_url[:_DISCORD_SIG_LEN]
    with _discord_flood_lock:
        last_sent = _discord_flood_cache.get(sig, 0)
        if time.time() - last_sent < _DISCORD_FLOOD_WINDOW:
            logger.debug(
                f"[FloodFilter] Suppressed duplicate Discord webhook alert "
                f"(cooldown: {_DISCORD_FLOOD_WINDOW // 60}m): {sig[:80]}..."
            )
            return True, "Suppressed (flood filter)", None
        _discord_flood_cache[sig] = time.time()
        # Evict stale entries
        stale_cutoff = time.time() - _DISCORD_FLOOD_WINDOW * 2
        for k in [k for k, v in _discord_flood_cache.items() if v < stale_cutoff]:
            del _discord_flood_cache[k]

    for attempt in range(max_retries):
        try:
            with _discord_api_lock:
                if files:
                    response = requests.post(webhook_url, data={"payload_json": json.dumps(payload)}, files=files, timeout=15)
                else:
                    response = requests.post(webhook_url, json=payload, timeout=15)

            if response.status_code in [200, 204]:
                return True, "Success", None

            if response.status_code == 429:
                try:
                    retry_after = float(response.json().get("retry_after", 1.0))
                except (json.JSONDecodeError, AttributeError, ValueError):
                    retry_after = 1.0
                
                # Add exponential jitter to avoid thundering herds
                jitter = random.uniform(0.1, 0.5) * (attempt + 1)
                total_sleep = retry_after + jitter
                
                logger.warning(
                    f"[RATE LIMIT] Discord rate limited (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying after {total_sleep:.2f}s (base {retry_after:.2f}s + jitter)."
                )
                time.sleep(total_sleep)
                continue  # retry

            # Non-retryable error
            error_code = None
            try:
                error_code = response.json().get("code")
            except json.JSONDecodeError:
                pass
            return False, f"{response.status_code} - {response.text}", error_code

        except Exception as e:
            return False, str(e), None

    # All retries exhausted on rate limit
    return False, f"Rate limited after {max_retries} retries.", None


def _send_discord_bot_request(url, headers, payload, max_retries=5):
    """Send a request as the Discord bot (not webhook) with rate-limit retry."""
    # --- Flood filter ---
    sig = json.dumps(payload, sort_keys=True)[:_DISCORD_SIG_LEN] if payload else url[:_DISCORD_SIG_LEN]
    with _discord_flood_lock:
        last_sent = _discord_flood_cache.get(sig, 0)
        if time.time() - last_sent < _DISCORD_FLOOD_WINDOW:
            logger.debug(
                f"[FloodFilter] Suppressed duplicate Discord bot message "
                f"(cooldown: {_DISCORD_FLOOD_WINDOW // 60}m): {sig[:80]}..."
            )
            return True, None
        _discord_flood_cache[sig] = time.time()
        stale_cutoff = time.time() - _DISCORD_FLOOD_WINDOW * 2
        for k in [k for k, v in _discord_flood_cache.items() if v < stale_cutoff]:
            del _discord_flood_cache[k]

    for attempt in range(max_retries):
        try:
            with _discord_api_lock:
                response = requests.post(url, headers=headers, json=payload, timeout=15)

            if response.status_code == 200:
                return True, response

            if response.status_code == 429:
                try:
                    retry_after = float(response.json().get("retry_after", 1.0))
                except (json.JSONDecodeError, AttributeError, ValueError):
                    retry_after = 1.0
                jitter = random.uniform(0.1, 0.5) * (attempt + 1)
                total_sleep = retry_after + jitter
                logger.warning(
                    f"[RATE LIMIT] Discord bot rate limited (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying after {total_sleep:.2f}s."
                )
                time.sleep(total_sleep)
                continue

            return False, response

        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while sending message as bot: {e}")
            return False, None

    return False, response if 'response' in dir() else None

def send_discord_embed(embed_data, alert_type="default", trade_hash=None):
    """
    Sends a formatted embed message.
    For chat_log, it sends as the bot and adds a reaction.
    For others, it uses the webhook.
    """
    if alert_type == "chat_log" and trade_hash:
        thread_id = get_thread_id(trade_hash, wait=True)
        if thread_id:
            channel_id = thread_id
        else:
            logger.warning(
                f"[chat_log] No thread ID found for trade {trade_hash}. "
                f"Falling back to main channel {DISCORD_CHAT_LOG_CHANNEL_ID}. "
                f"Check that discord_threads.json on the prod machine has this trade hash."
            )
            channel_id = DISCORD_CHAT_LOG_CHANNEL_ID
        if not channel_id:
            logger.error("No channel ID found for chat log alert.")
            return

        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        payload = {"embeds": [embed_data]}

        success, response = _send_discord_bot_request(url, headers, payload)

        if success and response is not None:
            message_id = response.json()["id"]
            logger.info(f"Successfully sent chat message {message_id} as bot.")

            # Add reactions based on the message type
            title = embed_data.get("title", "")
            if "AUTOMATED MESSAGE" in title:
                emoji = "🤖"
            elif "MESSAGE SENT" in title:
                emoji = "📤"
            else:  # Default reaction for buyer messages
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
                        # Reactions are cosmetic — don't spam ERROR logs for rate limits
                        logger.debug(f"Could not add reaction to message {message_id}: {reaction_response.status_code}")
        elif not success:
            # Only log an error for genuine failures, not flood-filter suppressions
            # (which return success=True, response=None).
            status = response.status_code if response is not None else "N/A"
            text   = response.text       if response is not None else "No response"
            logger.error(f"Failed to send chat message as bot: {status} - {text}")

    else:
        webhook_url_base, thread_id, webhook_url = _resolve_webhook(alert_type, trade_hash)
        if not webhook_url_base:
            return

        payload = {"embeds": [embed_data]}
        success, message, error_code = _send_discord_request(webhook_url, payload)

        if not success and error_code == 10003 and thread_id:
            logger.warning(f"Failed to send to thread {thread_id} (likely archived). Retrying in main channel.")
            success, message, _ = _send_discord_request(webhook_url_base, payload)

        if success:
            logger.info(f"Discord alert ('{alert_type}') sent successfully to {'thread ' + thread_id if thread_id else 'main channel'}.")
        else:
            logger.error(f"Failed to send Discord alert ('{alert_type}'): {message}")


def _resolve_webhook(alert_type, trade_hash):
    """
    Resolves the base webhook URL, thread ID, and final URL for a given alert.

    Returns:
        (webhook_url_base, thread_id, webhook_url) — webhook_url_base is None
        if no valid webhook is configured.
    """
    if trade_hash:
        webhook_url_base = DISCORD_WEBHOOKS.get("chat_log", DISCORD_WEBHOOKS.get("default"))
    else:
        webhook_url_base = DISCORD_WEBHOOKS.get(alert_type, DISCORD_WEBHOOKS.get("default"))

    if not webhook_url_base:
        logger.error(
            f"No webhook configured for alert_type '{alert_type}'. "
            f"Available keys: {list(DISCORD_WEBHOOKS.keys())}"
        )
        return None, None, None

    logger.debug(f"[WEBHOOK] alert_type={alert_type!r}, base URL resolved.")

    thread_id   = None
    webhook_url = webhook_url_base

    if trade_hash:
        thread_id = get_thread_id(trade_hash, wait=True)
        if thread_id:
            webhook_url += f"?thread_id={thread_id}"

    return webhook_url_base, thread_id, webhook_url


def send_discord_embed_with_image(embed_data, image_path, alert_type="default", trade_hash=None):
    """
    Sends an embed message along with an image file.
    Routes to the chat_log webhook if a trade_hash is provided.
    Retries in the main channel if the thread is archived.
    """
    webhook_url_base, thread_id, webhook_url = _resolve_webhook(alert_type, trade_hash)
    if not webhook_url_base:
        return

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
    embed_color = COLORS["NOONES_GREEN"]
    platform_emoji = "🔔"
    trade_url = f"https://noones.com/trade/{trade_hash}"

    # Get buyer info with stats
    buyer_username = trade_data.get('responder_username', 'N/A')
    buyer_line = f"**{buyer_username}**"
    
    if buyer_username != 'N/A':
        profile_data = generate_user_profile(buyer_username)
        if profile_data:
            trades_count = profile_data.get('total_trades', 0)
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
    owner_username = trade_data.get('owner_username', 'N/A')
    template = NEW_TRADE_EMBED
    embed = {
        "title": template["title_format"].format(platform_emoji=platform_emoji, owner_username=owner_username),
        "color": COLORS[template["color"]],
        "description": template["description_format"].format(
            buyer_line=buyer_line,
            amount_formatted=amount_formatted,
            payment_method=trade_data.get('payment_method_name', 'N/A'),
            trade_hash=trade_hash
        ),
        "fields": [],
        "timestamp": timestamp.isoformat(),
        "footer": {"text": template["footer"]}
    }

    if send:
        send_discord_embed(embed, alert_type="trades")
    else:
        return embed


def create_high_value_trade_embed(trade_data, platform):
    """Creates and sends a high-priority Discord embed for trades over 5000 MXN."""
    trade_hash = trade_data.get('trade_hash')

    buyer_username = trade_data.get('responder_username', 'N/A')
    buyer_line = f"**{buyer_username}**"

    if buyer_username != 'N/A':
        profile_data = generate_user_profile(buyer_username)
        if profile_data:
            trades_count = profile_data.get('total_trades', 0)
            volume = profile_data.get('total_volume', 0.0)
            currency = trade_data.get('fiat_currency_code', '')
            volume_formatted = format_currency(volume, currency)
            buyer_line = f"**{buyer_username}** • {trades_count} trades • ${volume_formatted} volume"

    amount = trade_data.get('fiat_amount_requested', '0')
    currency = trade_data.get('fiat_currency_code', '')
    amount_formatted = format_currency(amount, currency)

    owner_username = trade_data.get('owner_username', 'N/A')
    template = HIGH_VALUE_TRADE_EMBED

    embed = {
        "title": template["title_format"].format(owner_username=owner_username),
        "color": COLORS[template["color"]],
        "description": template["description_format"].format(
            buyer_line=buyer_line,
            amount_formatted=amount_formatted,
            payment_method=trade_data.get('payment_method_name', 'N/A'),
            trade_hash=trade_hash
        ),
        "fields": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": template["footer"]}
    }

    send_discord_embed(embed, alert_type="trades")


def create_trade_status_update_embed(trade_hash, owner_username, new_status, platform):
    """Creates and sends a Discord embed for a trade status change."""
    if new_status == 'Paid':
        template = STATUS_UPDATE_EMBEDS["paid"]
    elif new_status == 'Successful':
        template = STATUS_UPDATE_EMBEDS["successful"]
    elif 'Dispute' in new_status:
        template = STATUS_UPDATE_EMBEDS["disputed"]
    else:
        template = STATUS_UPDATE_EMBEDS["other"]

    if "title_format" in template:
        title = template["title_format"].format(status=new_status, owner_username=owner_username)
    else:
        title = template["title"].format(owner_username=owner_username)

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
    """Creates and sends a Discord embed for a new attachment."""
    template = ATTACHMENT_EMBED

    if bank_name:
        description = template["description_format"].format(
            trade_hash=trade_hash,
            author=author,
            bank_name=bank_name
        )
    else:
        description = template["description_no_bank_format"].format(
            trade_hash=trade_hash,
            author=author
        )

    embed = {
        "title": template["title_format"].format(owner_username=owner_username),
        "color": COLORS[template["color"]],
        "description": description,
        "fields": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "🤖 WillGang Bot"}
    }
    send_discord_embed_with_image(embed, image_path, alert_type="attachments", trade_hash=trade_hash)




def create_amount_validation_embed(trade_hash, owner_username, expected, found, currency):
    """Builds and sends an amount validation embed using templates."""
    if found is None:
        template = AMOUNT_VALIDATION_EMBEDS["not_found"]
        fields = []
    elif float(expected) == float(found):
        template = AMOUNT_VALIDATION_EMBEDS["matched"]
        fields = [{"name": f["name"], "value": f["value"].format(expected=float(expected), found=found, currency=currency), "inline": f.get("inline", True)} for f in template["fields"]]
    else:
        template = AMOUNT_VALIDATION_EMBEDS["mismatch"]
        fields = [{"name": f["name"], "value": f["value"].format(expected=float(expected), found=found, currency=currency), "inline": f.get("inline", True)} for f in template["fields"]]

    embed = {
        "title": template["title"].format(owner_username=owner_username),
        "color": COLORS["success"] if "✅" in template["title"] else (COLORS["warning"] if "⚠️" in template["title"] else COLORS["error"]),
        "description": template.get("description", ""),
        "fields": fields,
        "footer": {"text": f"Trade: {trade_hash}"}
    }
    send_discord_embed(embed, alert_type="attachments", trade_hash=trade_hash)

# --- EMAIL MODULE DISABLED ---
# def create_email_validation_embed(trade_hash, success, account_name, details=None):
#     (entire function commented out — re-enable when email module is restored)


def create_chat_message_embed(trade_hash, owner_username, author, message, platform):
    """Creates and sends a visually improved Discord embed for a new chat message."""
    is_bot_owner = author in BOT_OWNER_USERNAMES
    is_automated = message in AUTOMATED_MESSAGES

    # Determine message type and get template
    if is_bot_owner and is_automated:
        template = CHAT_MESSAGE_EMBEDS["automated"]
    elif is_bot_owner and not is_automated:
        template = CHAT_MESSAGE_EMBEDS["manual"]
    else:
        template = CHAT_MESSAGE_EMBEDS["buyer"]

    embed_color = COLORS[template["color"]]

    # Truncate long messages
    message_preview = message if len(message) <= 900 else message[:900] + "..."

    embed = {
        "author": {"name": template["author_format"].format(author=author)},
        "color": embed_color,
        "description": template["description_format"].format(
            trade_hash=trade_hash,
            owner_username=owner_username,
            message=message_preview,
            author=author
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "🤖 WillGang Bot"}
    }
    
    # Add title for bot owner messages
    if is_bot_owner:
        embed['title'] = template["title"]
         
    send_discord_embed(embed, alert_type="chat_log", trade_hash=trade_hash)


def create_name_validation_embed(trade_hash, success, account_name):
    """Builds and sends a name validation embed using templates."""
    template = NAME_VALIDATION_EMBEDS["success"] if success else NAME_VALIDATION_EMBEDS["failure"]

    embed = {
        "title": template["title"].format(account_name=account_name),
        "color": COLORS["success"] if success else COLORS["error"],
        "description": template.get("description", ""),
        "fields": [],
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


def send_binance_email_alert(account_name, subject, sender, date_str, snippet, is_banorte=False):
    """Sends a Discord embed for a Binance, BBVA, or Banorte email notification."""
    is_bbva = "bbva" in sender.lower() or "bbvabancomer" in sender.lower()
    is_bank = is_banorte or is_bbva

    # Bank payments (Banorte, BBVA) go to their own channel; Binance stays on the binance channel
    if is_bank:
        webhook_url = (
            DISCORD_WEBHOOKS.get("bank_payments")
            or DISCORD_WEBHOOKS.get("binance")
            or DISCORD_WEBHOOKS.get("default")
        )
    else:
        webhook_url = DISCORD_WEBHOOKS.get("binance") or DISCORD_WEBHOOKS.get("default")

    if not webhook_url:
        logger.error("No Discord webhook configured for email alert.")
        return

    if is_banorte:
        title = f"🏦 BANORTE BANK ALERT — {account_name}"
        color = 11674146  # #B22222 dark red — Banorte brand color
        footer_text = "🤖 WillGang Banorte Notification"
    elif is_bbva:
        title = f"🔹 BBVA BANK ALERT — {account_name}"
        color = 17537  # #004481 BBVA Blue
        footer_text = "🤖 WillGang BBVA Notification"
    else:
        title = f"🔸 BINANCE EMAIL ALERT — {account_name}"
        color = 15776011  # #F0B90B Binance Yellow
        footer_text = "🤖 WillGang Binance Notification"

    embed = {
        "title": title,
        "color": color,
        "description": f"👤 **From**: {sender}\n📝 **Subject**: {subject}\n\n**Content Snippet**:\n{snippet}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": footer_text}
    }
    
    success, error_msg, _ = _send_discord_request(webhook_url, {"embeds": [embed]})
    if success:
        logger.info(f"Discord email alert sent successfully.")
    else:
        logger.error(f"Failed to send Discord email alert: {error_msg}")


def send_payment_match_alert(binance_order, banorte_deposit, time_diff_str):
    """Sends a Discord embed when a Binance order and Banorte deposit match."""
    webhooks = [
        DISCORD_WEBHOOKS.get("bank_payments"),
        DISCORD_WEBHOOKS.get("binance"),
        DISCORD_WEBHOOKS.get("default")
    ]
    unique_webhooks = list(set([w for w in webhooks if w]))
    
    embed = {
        "title": "✅ PAYMENT VALIDATED (Binance ↔️ Banorte Match)",
        "color": 3066993,  # Green (#2ECC71)
        "description": "Successfully matched a Binance P2P order with a Banorte bank deposit.",
        "fields": [
            {
                "name": "🔸 Binance P2P Order",
                "value": f"**Order ID**: `{binance_order['order_number']}`\n**Amount**: `${binance_order['amount']:.2f} MXN`\n**Order Time**: `{binance_order['timestamp']}`",
                "inline": True
            },
            {
                "name": "🏦 Banorte Deposit",
                "value": f"**Customer**: `{banorte_deposit['name']}`\n**Operation ID**: `{banorte_deposit['operation_id']}`\n**Deposit Time**: `{banorte_deposit['timestamp']}`",
                "inline": True
            },
            {
                "name": "⏱️ Validation Summary",
                "value": f"**Time Difference**: `{time_diff_str}`\n**Status**: `Match Confirmed`",
                "inline": False
            }
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "🤖 WillGang Payment Validation Monitor"}
    }
    
    for webhook_url in unique_webhooks:
        success, error_msg, _ = _send_discord_request(webhook_url, {"embeds": [embed]})
        if success:
            logger.info(f"Discord match alert sent successfully to webhook.")
        else:
            logger.error(f"Failed to send Discord match alert to webhook: {error_msg}")


def send_discord_text(message, alert_type="default"):
    """
    Sends a raw text message to Discord using a resolved webhook.
    Converts Telegram MarkdownV2 escaping to clean Discord markdown.
    Splits messages longer than 2000 characters into smaller chunks.
    """
    import re
    webhook_url_base, thread_id, webhook_url = _resolve_webhook(alert_type, None)
    if not webhook_url_base:
        return False
        
    # Clean Telegram markdown backslashes for Discord
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    cleaned_message = re.sub(f'\\\\([{re.escape(escape_chars)}])', r'\1', message)
    
    # Discord text length limit is 2000 characters.
    # Split the message into chunks of <= 1900 characters to be safe, splitting on newlines.
    chunks = []
    current_chunk = []
    current_length = 0
    
    lines = cleaned_message.split("\n")
    for line in lines:
        if current_length + len(line) + 1 > 1900:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_length = len(line)
        else:
            current_chunk.append(line)
            current_length += len(line) + 1
            
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    # Send each chunk as a separate message
    all_success = True
    for chunk in chunks:
        payload = {"content": chunk}
        success, err_msg, _ = _send_discord_request(webhook_url, payload)
        if success:
            logger.info(f"Discord text alert ('{alert_type}') chunk sent successfully.")
        else:
            logger.error(f"Failed to send Discord text alert ('{alert_type}') chunk: {err_msg}")
            all_success = False
            
    return all_success

