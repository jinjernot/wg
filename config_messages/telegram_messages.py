# --- Helper Function ---
def format_currency(amount, currency=""):
    """Format currency with commas and optional abbreviation for large amounts."""
    try:
        num = float(amount)
        if num >= 10000:
            return f"{num/1000:.1f}K {currency}".strip()
        return f"{num:,.2f} {currency}".strip()
    except (ValueError, TypeError):
        return f"{amount} {currency}".strip()


# --- New Trade Template ---
# First line shows in the mobile notification preview → account name visible immediately
NOONES_ALERT_MESSAGE = """\
━━━━━ 🔔 NEW TRADE ━━━━━
👤 {buyer_line}
💰 *{amount_formatted}*  •  💳 {payment_method_name}
🏷 {owner_username}  •  🔑 `{trade_hash}`
"""

# --- Chat Message Template ---
NEW_CHAT_ALERT_MESSAGE = """\
💬 *{author}*  ›  {owner_username}
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
{chat_message}
└ 🔑 `{trade_hash}`
"""

# --- Attachment Templates ---
NEW_ATTACHMENT_WITH_BANK_ALERT_MESSAGE = """\
📎 *RECEIPT*  •  {owner_username}
👤 {author}  •  🏦 {bank_name}
🔑 `{trade_hash}`
"""

NEW_ATTACHMENT_ALERT_MESSAGE = """\
📎 *RECEIPT*  •  {owner_username}
👤 {author}  •  🔑 `{trade_hash}`
"""

# --- Amount Validation Templates ---
AMOUNT_VALIDATION_MATCH_ALERT = """\
✅ *VERIFIED*  •  {owner_username}
└ Expected *{expected_amount} {currency}*  →  Got *{found_amount} {currency}*
"""

AMOUNT_VALIDATION_MISMATCH_ALERT = """\
❌ *MISMATCH*  •  {owner_username}
├ Expected: *{expected_amount} {currency}*
└ Found:      *{found_amount} {currency}*
"""

AMOUNT_VALIDATION_NOT_FOUND_ALERT = """\
⚠️ *AMOUNT NOT FOUND*  •  {owner_username}
└ Could not extract amount from receipt
"""

# --- Email Validation Templates ---
EMAIL_VALIDATION_SUCCESS_ALERT = """\
✅ *EMAIL VERIFIED*  •  {account_name}
"""

EMAIL_VALIDATION_FAILURE_ALERT = """\
❌ *EMAIL NOT FOUND*  •  {account_name}
└ Manual verification required
"""

# --- Name Validation Templates ---
NAME_VALIDATION_SUCCESS_ALERT = """\
✅ *NAME VERIFIED*  •  {account_name}
"""

NAME_VALIDATION_FAILURE_ALERT = """\
❌ *NAME NOT FOUND*  •  {account_name}
└ Name not found on receipt
"""

# --- Low Balance Alert ---
LOW_BALANCE_ALERT_MESSAGE = (
    "💸 *LOW BALANCE*  •  `{account_name}`\n"
    "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
    "Balance `${total_balance_usd}` is below threshold `${threshold}`\n\n"
    "{balance_details}"
)

# --- Duplicate Receipt Template ---
DUPLICATE_RECEIPT_ALERT_MESSAGE = """\
🚨 *DUPLICATE RECEIPT*  •  {owner_username}
├ Current:   🔑 `{trade_hash}`
└ Previous:  🔑 `{previous_trade_hash}`  ({previous_owner})
"""

# --- Status Update Templates ---
STATUS_UPDATE_PAID = """\
💰 *PAID*  •  {owner_username}  •  🔑 `{trade_hash}`
"""

STATUS_UPDATE_SUCCESSFUL = """\
✅ *COMPLETED*  •  {owner_username}  •  🔑 `{trade_hash}`
"""

STATUS_UPDATE_DISPUTED = """\
⚠️ *DISPUTED*  •  {owner_username}  •  🔑 `{trade_hash}`
"""

STATUS_UPDATE_OTHER = """\
🔄 *{status}*  •  {owner_username}  •  🔑 `{trade_hash}`
"""

# --- High-Value Trade Alert (>5000 MXN) ---
HIGH_VALUE_TRADE_ALERT_MESSAGE = """\
━━━━ 🚨 HIGH VALUE ━━━━
👤 {buyer_username}  •  🏷 {owner_username}
💰 *{amount_formatted}*  •  💳 {payment_method_name}
🔑 `{trade_hash}`
"""

# --- Buyer Risk Flag Alert ---
BUYER_RISK_FLAG_ALERT_MESSAGE = """\
━━━━━ ⚠️ RISK FLAG ━━━━━
👤 {buyer_username} has dispute history\!
💰 *{amount_formatted}*  •  💳 {payment_method_name}
🏷 {owner_username}  •  🔑 `{trade_hash}`
"""

# --- Bot Status Alerts ---
BOT_ONLINE_ALERT_MESSAGE = """\
🟢 *WILL GANG TRADING — ONLINE*
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
👥 Accounts: {accounts}
⏱ {timestamp}
"""

BOT_OFFLINE_ALERT_MESSAGE = """\
🔴 *WILL GANG TRADING — OFFLINE*
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
🔎 Reason: {reason}
⏱ {timestamp}
"""
