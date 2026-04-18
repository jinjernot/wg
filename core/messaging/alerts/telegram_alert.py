import requests
import json
import re
import os
import time
import threading
import logging
import random
from datetime import datetime, timezone
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOPICS, PLATFORM_ACCOUNTS
from config_messages.telegram_messages import (
    NOONES_ALERT_MESSAGE,
    NEW_CHAT_ALERT_MESSAGE,
    NEW_ATTACHMENT_ALERT_MESSAGE,
    NEW_ATTACHMENT_WITH_BANK_ALERT_MESSAGE,
    AMOUNT_VALIDATION_NOT_FOUND_ALERT,
    AMOUNT_VALIDATION_MATCH_ALERT,
    AMOUNT_VALIDATION_MISMATCH_ALERT,
    EMAIL_VALIDATION_SUCCESS_ALERT,
    EMAIL_VALIDATION_FAILURE_ALERT,
    NAME_VALIDATION_SUCCESS_ALERT,
    NAME_VALIDATION_FAILURE_ALERT,
    LOW_BALANCE_ALERT_MESSAGE,
    DUPLICATE_RECEIPT_ALERT_MESSAGE,
    HIGH_VALUE_TRADE_ALERT_MESSAGE,
    BUYER_RISK_FLAG_ALERT_MESSAGE,
    BOT_ONLINE_ALERT_MESSAGE,
    BOT_OFFLINE_ALERT_MESSAGE,
    format_currency,
    STATUS_UPDATE_PAID,
    STATUS_UPDATE_SUCCESSFUL,
    STATUS_UPDATE_DISPUTED,
    STATUS_UPDATE_OTHER
)
from core.utils.profile import generate_user_profile
from .telegram_thread_manager import (
    save_message_id, get_message_id, 
    save_chat_message_id, get_chat_message_id
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alert flood filter
# Prevents the same message type from spamming Telegram in a tight loop.
# Keyed by the first 120 chars of the message; value is last-sent timestamp.
# ---------------------------------------------------------------------------
_FLOOD_WINDOW = 5 * 60        # 5 minutes
_FLOOD_SIG_LEN = 120          # characters used as the message "signature"
_flood_cache: dict[str, float] = {}
_flood_lock = threading.Lock()
_telegram_api_lock = threading.Lock()

def escape_markdown(text):
    """Escapes special characters for Telegram's MarkdownV2 parse mode."""
    if not isinstance(text, str):
        text = str(text)
    # Characters to escape for Telegram MarkdownV2.
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    # Use re.sub with a function to handle already escaped characters
    def replace(match):
        char = match.group(1)
        # Check if the character is already escaped (preceded by \\)
        if match.start() > 0 and text[match.start()-1] == '\\':
            return char # Already escaped, return as is
        else:
            return '\\' + char # Escape it
    # Use negative lookbehind to avoid double escaping
    return re.sub(f'(?<!\\\\)([{re.escape(escape_chars)}])', r'\\\1', text)

def get_inline_keyboard(trade_hash):
    """Generates an inline keyboard (Currently disabled)."""
    return None

def _send_text_alert(message, disable_web_page_preview=True, thread_id=None, reply_to_message_id=None, reply_markup=None):
    """Internal helper function to send a text message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram Bot Token or Chat ID is not configured.")
        return None

    # --- Flood filter ---
    # Suppress identical alerts sent within _FLOOD_WINDOW seconds.
    # Uses the first _FLOOD_SIG_LEN chars as the message signature so that
    # minor variations (e.g. different timestamps) are still grouped.
    sig = message[:_FLOOD_SIG_LEN]
    with _flood_lock:
        last_sent = _flood_cache.get(sig, 0)
        if time.time() - last_sent < _FLOOD_WINDOW:
            logger.debug(
                f"[FloodFilter] Suppressed duplicate Telegram alert "
                f"(cooldown: {_FLOOD_WINDOW // 60}m): {sig[:60]}..."
            )
            return None
        _flood_cache[sig] = time.time()
        # Evict old entries to prevent unbounded memory growth
        stale_cutoff = time.time() - _FLOOD_WINDOW * 2
        for k in [k for k, v in _flood_cache.items() if v < stale_cutoff]:
            del _flood_cache[k]

    message = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', message)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": disable_web_page_preview
    }
    
    if reply_to_message_id is not None:
        payload["reply_to_message_id"] = reply_to_message_id
        # Don't try to override thread_id with live_trades root_thread if thread_id is already specifically provided (like action_required)
        root_thread = TELEGRAM_TOPICS.get("live_trades")
        if thread_id is not None:
            payload["message_thread_id"] = thread_id
        elif root_thread is not None:
            payload["message_thread_id"] = root_thread
    elif thread_id is not None:
        payload["message_thread_id"] = thread_id
        
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
        
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with _telegram_api_lock:
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    logger.info("Telegram text alert sent successfully.")
                    return response.json().get("result", {}).get("message_id")
                if response.status_code == 429:
                    try:
                        retry_after = float(response.json().get("parameters", {}).get("retry_after", 1.0))
                    except (ValueError, AttributeError, KeyError):
                        retry_after = 1.0
                    
                    jitter = random.uniform(0.1, 0.5) * (attempt + 1)
                    total_sleep = retry_after + jitter
                    
                    logger.warning(
                        f"[RATE LIMIT] Telegram rate limited (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying after {total_sleep:.2f}s (base {retry_after:.2f}s + jitter). Lock held."
                    )
                    time.sleep(total_sleep)
                    continue
                
            logger.error(f"Failed to send Telegram text alert: {response.status_code} - {response.text}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Telegram request: {e}")
            return None
    logger.error(f"Telegram text alert failed after {max_retries} retries (rate limited).")
    return None

def _send_photo_alert(caption_text, image_path, thread_id=None, reply_to_message_id=None, reply_markup=None):
    """Internal helper function to send a photo message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram Bot Token or Chat ID is not configured.")
        return None
        
    if not os.path.exists(image_path):
        logger.error(f"Error: Image path does not exist: {image_path}")
        # Fallback to a text alert if the image is missing
        return _send_text_alert(f"⚠️ Image File Not Found ⚠️\n{caption_text}\n(Expected at: {image_path})", thread_id=thread_id, reply_to_message_id=reply_to_message_id, reply_markup=reply_markup)
        
    caption_text = re.sub(r'(?<!\\)([\.\(\)\-\|])', r'\\\1', caption_text)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption_text,
        "parse_mode": "MarkdownV2"
    }
    
    if reply_to_message_id is not None:
        data["reply_to_message_id"] = reply_to_message_id
        root_thread = TELEGRAM_TOPICS.get("live_trades")
        if thread_id is not None:
            data["message_thread_id"] = thread_id
        elif root_thread is not None:
            data["message_thread_id"] = root_thread
    elif thread_id is not None:
        data["message_thread_id"] = thread_id
        
    if reply_markup is not None:
        data["reply_markup"] = json.dumps(reply_markup)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            with _telegram_api_lock:
                with open(image_path, 'rb') as photo_file:
                    files = {'photo': photo_file}
                    response = requests.post(url, data=data, files=files, timeout=20)
                
                if response.status_code == 200:
                    logger.info("Attachment alert with image sent successfully.")
                    return response.json().get("result", {}).get("message_id")
                if response.status_code == 429:
                    try:
                        retry_after = float(response.json().get("parameters", {}).get("retry_after", 1.0))
                    except (ValueError, AttributeError, KeyError):
                        retry_after = 1.0
                        
                    jitter = random.uniform(0.1, 0.5) * (attempt + 1)
                    total_sleep = retry_after + jitter
                    
                    logger.warning(
                        f"[RATE LIMIT] Telegram rate limited on photo (attempt {attempt + 1}/{max_retries}). "
                        f"Retrying after {total_sleep:.2f}s (base {retry_after:.2f}s + jitter). Lock held."
                    )
                    time.sleep(total_sleep)
                    continue
                    
            logger.error(f"Failed to send attachment alert with image: {response.status_code} - {response.text}")
            return None
        except IOError as e:
            logger.error(f"Error opening image file {image_path}: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Telegram request with image: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while sending attachment alert: {e}")
            return None
    logger.error(f"Telegram photo alert failed after {max_retries} retries (rate limited).")
    return None

def extract_placeholders(message_template):
    """Extracts placeholders from the message template."""
    return re.findall(r"{(.*?)}", message_template)

def send_telegram_alert(trade, platform):
    """Sends a Telegram alert for a new trade with buyer stats and formatted amount."""
    if isinstance(trade, str):
        try:
            trade = json.loads(trade)
        except json.JSONDecodeError:
            logger.error("Error: Trade data is not a valid JSON string.")
            return
    if not isinstance(trade, dict):
        logger.error("Error: Trade data is not a dictionary.")
        return

    # Get buyer stats — capture profile_data at function scope for risk check below
    buyer_username = trade.get('responder_username', 'N/A')
    buyer_line = f"*{escape_markdown(buyer_username)}*"
    profile_data = None

    if buyer_username != 'N/A':
        profile_data = generate_user_profile(buyer_username)
        if profile_data:
            trades_count = profile_data.get('successful_trades', 0)
            volume = profile_data.get('total_volume', 0.0)
            currency = trade.get('fiat_currency_code', '')
            volume_formatted = format_currency(volume, currency)
            buyer_line = f"*{escape_markdown(buyer_username)}* • {trades_count} trades • ${escape_markdown(volume_formatted)} volume"


    # Format amount
    amount = trade.get('fiat_amount_requested', '0')
    currency = trade.get('fiat_currency_code', '')
    amount_formatted = format_currency(amount, currency)

    message_template = NOONES_ALERT_MESSAGE
    
    # Build formatted data with escaped values
    formatted_data = {
        'buyer_line': buyer_line,
        'amount_formatted': escape_markdown(amount_formatted),
        'payment_method_name': escape_markdown(trade.get('payment_method_name', 'N/A')),
        'owner_username': escape_markdown(trade.get('owner_username', 'N/A')),
        'trade_hash': escape_markdown(trade.get('trade_hash', 'N/A'))
    }
    
    message = message_template.format(**formatted_data)
    trade_hash = trade.get('trade_hash')
    reply_markup = get_inline_keyboard(trade_hash)
    
    msg_id = _send_text_alert(message, disable_web_page_preview=True, thread_id=TELEGRAM_TOPICS.get("live_trades"), reply_markup=reply_markup)
    if msg_id and trade_hash:
        save_message_id(trade_hash, msg_id)

    # Fire risk flag to Important channel if buyer has any dispute history this month
    if profile_data and profile_data.get('disputed_trades', 0) > 0:
        send_buyer_risk_flag_alert(trade, platform)

def send_high_value_trade_alert(trade, platform):
    """Sends a high-priority Telegram alert when a trade exceeds 5000 MXN."""
    if isinstance(trade, str):
        try:
            trade = json.loads(trade)
        except json.JSONDecodeError:
            logger.error("Error: Trade data is not a valid JSON string.")
            return
    if not isinstance(trade, dict):
        logger.error("Error: Trade data is not a dictionary.")
        return

    amount = trade.get('fiat_amount_requested', '0')
    currency = trade.get('fiat_currency_code', '')
    amount_formatted = format_currency(amount, currency)

    buyer_username = trade.get('responder_username', 'N/A')
    trade_hash = trade.get('trade_hash')
    message = HIGH_VALUE_TRADE_ALERT_MESSAGE.format(
        owner_username=escape_markdown(trade.get('owner_username', 'N/A')),
        buyer_username=escape_markdown(buyer_username),
        amount_formatted=escape_markdown(amount_formatted),
        payment_method_name=escape_markdown(trade.get('payment_method_name', 'N/A')),
        trade_hash=escape_markdown(trade_hash if trade_hash else 'N/A')
    )
    reply_markup = get_inline_keyboard(trade_hash)
    
    msg_id = _send_text_alert(message, disable_web_page_preview=True, thread_id=TELEGRAM_TOPICS.get("action_required"), reply_markup=reply_markup)
    if msg_id and trade_hash:
        save_message_id(trade_hash, msg_id)

def send_chat_message_alert(chat_message, trade_hash, owner_username, author):
    """Sends a Telegram alert for a new chat message."""
    chat_data = {
        "chat_message": escape_markdown(chat_message),
        "author": escape_markdown(author),
        "trade_hash": escape_markdown(trade_hash),
        "owner_username": escape_markdown(owner_username)
    }
    message = NEW_CHAT_ALERT_MESSAGE.format(**chat_data)
    
    # Identify if a thread already exists for this trade's chats
    reply_to = get_chat_message_id(trade_hash)
    topic = TELEGRAM_TOPICS.get("buyer_chats")
    
    msg_id = _send_text_alert(message, disable_web_page_preview=True, thread_id=topic, reply_to_message_id=reply_to, reply_markup=get_inline_keyboard(trade_hash))
    
    # If this is the very first chat message, save its ID so all future messages become a thread under it
    if msg_id and not reply_to:
        save_chat_message_id(trade_hash, msg_id)

def send_attachment_alert(trade_hash, owner_username, author, image_path, bank_name=None):
    """Sends a Telegram alert for a new attachment."""
    caption_text = ""
    if bank_name:
        template = NEW_ATTACHMENT_WITH_BANK_ALERT_MESSAGE
        caption_text = template.format(
            bank_name=escape_markdown(bank_name),
            trade_hash=escape_markdown(trade_hash),
            owner_username=escape_markdown(owner_username),
            author=escape_markdown(author)
        )
    else:
        template = NEW_ATTACHMENT_ALERT_MESSAGE
        caption_text = template.format(
            trade_hash=escape_markdown(trade_hash),
            owner_username=escape_markdown(owner_username),
            author=escape_markdown(author)
        )
    
    # 1. Send as a reply in the original trade thread
    reply_to = get_message_id(trade_hash)
    _send_photo_alert(caption_text, image_path, thread_id=TELEGRAM_TOPICS.get("live_trades"), reply_to_message_id=reply_to, reply_markup=get_inline_keyboard(trade_hash))
    
    # 2. Dump a copy separately into the attachments folder (topic)
    if TELEGRAM_TOPICS.get("attachments") is not None:
        _send_photo_alert(caption_text, image_path, thread_id=TELEGRAM_TOPICS.get("attachments"), reply_markup=get_inline_keyboard(trade_hash))

def send_amount_validation_alert(trade_hash, owner_username, expected_amount, found_amount, currency):
    """Sends a Telegram alert for amount validation."""
    message = ""
    try:
        expected_amount_float = float(expected_amount)
    except (ValueError, TypeError):
        logger.error(f"Invalid expected amount type for trade {trade_hash}: {expected_amount}")
        expected_amount_float = 0.0

    if found_amount is None:
        message = AMOUNT_VALIDATION_NOT_FOUND_ALERT.format(
            owner_username=escape_markdown(owner_username)
        )
    else:
        try:
            found_amount_float = float(found_amount)
            if expected_amount_float == found_amount_float:
                message = AMOUNT_VALIDATION_MATCH_ALERT.format(
                    owner_username=escape_markdown(owner_username),
                    expected_amount=escape_markdown(f"{expected_amount_float:,.2f}"),
                    found_amount=escape_markdown(f"{found_amount_float:,.2f}"),
                    currency=escape_markdown(currency)
                )
            else:
                message = AMOUNT_VALIDATION_MISMATCH_ALERT.format(
                    owner_username=escape_markdown(owner_username),
                    expected_amount=escape_markdown(f"{expected_amount_float:,.2f}"),
                    found_amount=escape_markdown(f"{found_amount_float:,.2f}"),
                    currency=escape_markdown(currency)
                )
        except (ValueError, TypeError):
            logger.error(f"Invalid found amount type for trade {trade_hash}: {found_amount}")
            message = AMOUNT_VALIDATION_NOT_FOUND_ALERT.format(
                owner_username=escape_markdown(owner_username)
            )

    if not message:
         logger.error(f"Amount validation message could not be formatted for trade {trade_hash}")
         return

    reply_to = get_message_id(trade_hash)
    topic = "action_required" if "Mismatch" in message or "Not Found" in message else "live_trades"
    _send_text_alert(message, thread_id=TELEGRAM_TOPICS.get(topic), reply_to_message_id=reply_to, reply_markup=get_inline_keyboard(trade_hash))

def send_email_validation_alert(trade_hash, success, account_name, details=None):
    """Sends a Telegram alert about the email validation result."""
    if success:
        message = EMAIL_VALIDATION_SUCCESS_ALERT.format(account_name=escape_markdown(account_name))
        if details:
            validator = details.get('validator', 'Unknown').replace('_', ' ').title()
            found_amount = details.get('found_amount', 0)
            found_name = details.get('found_name', 'Unknown')
            
            message += f"\n\n🏦 *Bank:* {escape_markdown(validator)}"
            message += f"\n💰 *Amount:* ${escape_markdown(f'{found_amount:,.2f}')}"
            message += f"\n👤 *Name:* {escape_markdown(found_name)}"
    else:
        message = EMAIL_VALIDATION_FAILURE_ALERT.format(account_name=escape_markdown(account_name))
    
    reply_to = get_message_id(trade_hash)
    topic = "live_trades" if success else "action_required"
    _send_text_alert(message, thread_id=TELEGRAM_TOPICS.get(topic), reply_to_message_id=reply_to, reply_markup=get_inline_keyboard(trade_hash))

def send_name_validation_alert(trade_hash, success, account_name):
    """Sends a Telegram alert about the OCR name validation result."""
    if success:
        message = NAME_VALIDATION_SUCCESS_ALERT.format(account_name=escape_markdown(account_name))
    else:
        message = NAME_VALIDATION_FAILURE_ALERT.format(account_name=escape_markdown(account_name))

    reply_to = get_message_id(trade_hash)
    topic = "live_trades" if success else "action_required"
    _send_text_alert(message, thread_id=TELEGRAM_TOPICS.get(topic), reply_to_message_id=reply_to, reply_markup=get_inline_keyboard(trade_hash))

def send_status_update_alert(trade_hash, owner_username, new_status):
    """Sends a Telegram alert for trade status changes."""
    if new_status == 'Paid':
        template = STATUS_UPDATE_PAID
    elif new_status == 'Successful':
        template = STATUS_UPDATE_SUCCESSFUL
    elif 'Dispute' in new_status:
        template = STATUS_UPDATE_DISPUTED
    else:
        template = STATUS_UPDATE_OTHER
    
    message = template.format(
        trade_hash=escape_markdown(trade_hash),
        owner_username=escape_markdown(owner_username),
        status=escape_markdown(new_status)
    )
    
    reply_to = get_message_id(trade_hash)
    topic = "action_required" if 'Dispute' in new_status else "live_trades"
    _send_text_alert(message, thread_id=TELEGRAM_TOPICS.get(topic), reply_to_message_id=reply_to, reply_markup=get_inline_keyboard(trade_hash))

def send_low_balance_alert(account_name, total_balance_usd, threshold, balance_details_raw):
    """Builds and sends a Telegram alert for low wallet balance using a template."""
    balance_details_formatted = []
    for amount, currency, usd_value in balance_details_raw:
        try:
            amount_str = f"{float(amount):,.8f}".rstrip('0').rstrip('.')
        except ValueError:
             amount_str = str(amount)
        usd_str = f"{usd_value:,.2f}"
        currency_escaped = escape_markdown(currency)
        line = f"- `{amount_str} {currency_escaped}` (approx. ${usd_str})"
        balance_details_formatted.append(line)

    details_str = "\n".join(balance_details_formatted) if balance_details_formatted else "No balance details available."

    message = LOW_BALANCE_ALERT_MESSAGE.format(
        account_name=escape_markdown(account_name),
        total_balance_usd=escape_markdown(f"{total_balance_usd:,.2f}"),
        threshold=escape_markdown(f"{threshold:,.2f}"),
        balance_details=details_str
    )
    
    _send_text_alert(message, thread_id=TELEGRAM_TOPICS.get("low_balance"))

def send_duplicate_receipt_alert(trade_hash, owner_username, image_path, previous_trade_info):
    """Sends a Telegram alert for a duplicate receipt."""
    previous_trade_hash = previous_trade_info.get('trade_hash', 'N/A')
    previous_owner = previous_trade_info.get('owner_username', 'N/A')

    caption_text = DUPLICATE_RECEIPT_ALERT_MESSAGE.format(
        trade_hash=escape_markdown(trade_hash),
        owner_username=escape_markdown(owner_username),
        previous_trade_hash=escape_markdown(previous_trade_hash),
        previous_owner=escape_markdown(previous_owner)
    )
    
    reply_to = get_message_id(trade_hash)
    _send_photo_alert(caption_text, image_path, thread_id=TELEGRAM_TOPICS.get("action_required"), reply_to_message_id=reply_to, reply_markup=get_inline_keyboard(trade_hash))


def send_buyer_risk_flag_alert(trade, platform):
    """Sends a risk flag to the Important channel when a buyer has dispute history."""
    if isinstance(trade, str):
        try:
            trade = json.loads(trade)
        except json.JSONDecodeError:
            return
    if not isinstance(trade, dict):
        return

    amount = trade.get('fiat_amount_requested', '0')
    currency = trade.get('fiat_currency_code', '')
    amount_formatted = format_currency(amount, currency)
    buyer_username = trade.get('responder_username', 'N/A')
    trade_hash = trade.get('trade_hash')

    message = BUYER_RISK_FLAG_ALERT_MESSAGE.format(
        owner_username=escape_markdown(trade.get('owner_username', 'N/A')),
        buyer_username=escape_markdown(buyer_username),
        amount_formatted=escape_markdown(amount_formatted),
        payment_method_name=escape_markdown(trade.get('payment_method_name', 'N/A')),
        trade_hash=escape_markdown(trade_hash if trade_hash else 'N/A')
    )
    _send_text_alert(message, disable_web_page_preview=True, thread_id=TELEGRAM_TOPICS.get("action_required"))


def send_bot_online_alert():
    """Sends a notification to the Important channel that the bot has started."""
    account_names = ", ".join(
        escape_markdown(a["name"].split("_")[0]) for a in PLATFORM_ACCOUNTS
    )
    timestamp = datetime.now(timezone.utc).strftime("%Y\\-%m\\-%d %H:%M UTC")
    message = BOT_ONLINE_ALERT_MESSAGE.format(
        accounts=account_names,
        timestamp=timestamp
    )
    _send_text_alert(message, disable_web_page_preview=True, thread_id=TELEGRAM_TOPICS.get("action_required"))


def send_bot_offline_alert(reason="Shutdown"):
    """Sends a notification to the Important channel that the bot has stopped."""
    timestamp = datetime.now(timezone.utc).strftime("%Y\\-%m\\-%d %H:%M UTC")
    message = BOT_OFFLINE_ALERT_MESSAGE.format(
        timestamp=timestamp,
        reason=escape_markdown(reason)
    )
    _send_text_alert(message, disable_web_page_preview=True, thread_id=TELEGRAM_TOPICS.get("action_required"))
