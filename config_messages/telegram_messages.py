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
NOONES_ALERT_MESSAGE = """💠 *NEW TRADE*

*BUYER*
{buyer_line}

*TRADE DETAILS*
💰 Amount: *{amount_formatted}*
💳 Method: *{payment_method_name}*
🏦 Account: *{owner_username}*

*TRADE ID*
`{trade_hash}`
"""

# --- Chat Message Template ---
NEW_CHAT_ALERT_MESSAGE = """*FROM:* {author}
*TRADE:* `{trade_hash}` • *{owner_username}*

"{chat_message}"
"""

# --- Attachment Templates ---
NEW_ATTACHMENT_WITH_BANK_ALERT_MESSAGE = """📎 *PAYMENT RECEIPT*

*TRADE:* `{trade_hash}`
*FROM:* {author} → {owner_username}

*BANK:* {bank_name}

📸 Receipt Image
Review Required
"""

NEW_ATTACHMENT_ALERT_MESSAGE = """📎 *PAYMENT RECEIPT*

*TRADE:* `{trade_hash}`
*FROM:* {author} → {owner_username}

📸 Receipt Image
Review Required
"""

# --- Amount Validation Templates ---
AMOUNT_VALIDATION_MATCH_ALERT = """✅ *PAYMENT VERIFIED*

*ACCOUNT:* `{owner_username}`

*AMOUNT CHECK*
Expected: *{expected_amount} {currency}* ✓
Received: *{found_amount} {currency}* ✓

Status: *MATCH* ✓
"""

AMOUNT_VALIDATION_MISMATCH_ALERT = """❌ *AMOUNT MISMATCH*

⚠️ *REVIEW REQUIRED* ⚠️

*ACCOUNT:* `{owner_username}`

*AMOUNT CHECK*
Expected: *{expected_amount} {currency}*
Found: *{found_amount} {currency}* ❌
"""

AMOUNT_VALIDATION_NOT_FOUND_ALERT = """⚠️ *AMOUNT NOT FOUND*

*ACCOUNT:* `{owner_username}`

*OCR RESULT:*
Could not extract amount from receipt
"""

# --- Email Validation Templates ---
EMAIL_VALIDATION_SUCCESS_ALERT = """✅ *EMAIL PAYMENT VERIFIED*

*Status:* CONFIRMED ✓

*VALIDATED IN:* `{account_name}`
"""

EMAIL_VALIDATION_FAILURE_ALERT = """❌ *EMAIL NOT FOUND*

*Status:* NOT FOUND

*SEARCHED IN:* `{account_name}`
*ACTION:* Manual verification required
"""

# --- Name Validation Templates ---
NAME_VALIDATION_SUCCESS_ALERT = """✅ *NAME VERIFIED*

*Status:* MATCH ✓

*Account Verified:* {account_name}
"""

NAME_VALIDATION_FAILURE_ALERT = """❌ *NAME NOT FOUND*

⚠️ *MANUAL REVIEW REQUIRED* ⚠️

*Expected Account:* {account_name}
*Issue:* Account name not found on receipt
"""

# --- Low Balance Alert ---
LOW_BALANCE_ALERT_MESSAGE = (
    "⚠️ *Low Balance Alert* ⚠️\n\n"
    "The total balance for `{account_name}` is below the threshold.\n\n"
    "*Total Balance:* `${total_balance_usd}`\n"
    "*Threshold:* `${threshold}`\n\n"
    "*Balance Details:*\n{balance_details}"
)

# --- Duplicate Receipt Template ---
DUPLICATE_RECEIPT_ALERT_MESSAGE = """🚨 *DUPLICATE RECEIPT* 🚨

⚠️ *IMMEDIATE ACTION REQUIRED* ⚠️

This receipt has been used before

*CURRENT TRADE:* `{trade_hash}` ({owner_username})
*PREVIOUS TRADE:* `{previous_trade_hash}` ({previous_owner})
"""

# --- Status Update Templates ---
STATUS_UPDATE_PAID = """💰 *TRADE PAID*

*TRADE:* `{trade_hash}` • *{owner_username}*

Status: *PAID* ✅
"""

STATUS_UPDATE_SUCCESSFUL = """✅ *TRADE COMPLETED*

*TRADE:* `{trade_hash}` • *{owner_username}*

Status: *COMPLETED* ✅
"""

STATUS_UPDATE_DISPUTED = """⚠️ *TRADE DISPUTED*

*TRADE:* `{trade_hash}` • *{owner_username}*

Status: *DISPUTE* ⚠️
"""

STATUS_UPDATE_OTHER = """🔄 *STATUS UPDATE: {status}*

*TRADE:* `{trade_hash}` • *{owner_username}*

Status: *{status}*
"""