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
# First line shows in the mobile notification preview → put account + amount there
NOONES_ALERT_MESSAGE = """💠 *NEW TRADE* — {owner_username}

👤 {buyer_line}
💰 *{amount_formatted}*
💳 {payment_method_name}

🔑 `{trade_hash}`
"""

# --- Chat Message Template ---
NEW_CHAT_ALERT_MESSAGE = """💬 *{author}* → {owner_username}
`{trade_hash}`

{chat_message}
"""

# --- Attachment Templates ---
NEW_ATTACHMENT_WITH_BANK_ALERT_MESSAGE = """📎 *RECEIPT* — {owner_username}
{author} • {bank_name}
`{trade_hash}`

📸 Review Required
"""

NEW_ATTACHMENT_ALERT_MESSAGE = """📎 *RECEIPT* — {owner_username}
{author}
`{trade_hash}`

📸 Review Required
"""

# --- Amount Validation Templates ---
AMOUNT_VALIDATION_MATCH_ALERT = """✅ *VERIFIED* — {owner_username}
Expected: *{expected_amount} {currency}*
Received: *{found_amount} {currency}* ✓
"""

AMOUNT_VALIDATION_MISMATCH_ALERT = """❌ *MISMATCH* — {owner_username}
Expected: *{expected_amount} {currency}*
Found: *{found_amount} {currency}* ❌

⚠️ Review Required
"""

AMOUNT_VALIDATION_NOT_FOUND_ALERT = """⚠️ *AMOUNT NOT FOUND* — {owner_username}

Could not extract amount from receipt
"""

# --- Email Validation Templates ---
EMAIL_VALIDATION_SUCCESS_ALERT = """✅ *EMAIL VERIFIED* — {account_name}
Status: CONFIRMED ✓
"""

EMAIL_VALIDATION_FAILURE_ALERT = """❌ *EMAIL NOT FOUND* — {account_name}
Status: NOT FOUND
Action: Manual verification required
"""

# --- Name Validation Templates ---
NAME_VALIDATION_SUCCESS_ALERT = """✅ *NAME VERIFIED* — {account_name}
Status: MATCH ✓
"""

NAME_VALIDATION_FAILURE_ALERT = """❌ *NAME NOT FOUND* — {account_name}
Issue: Name not found on receipt
⚠️ Manual review required
"""

# --- Low Balance Alert ---
LOW_BALANCE_ALERT_MESSAGE = (
    "⚠️ *LOW BALANCE* — `{account_name}`\n"
    "Balance: `${total_balance_usd}` (threshold: `${threshold}`)\n\n"
    "{balance_details}"
)

# --- Duplicate Receipt Template ---
DUPLICATE_RECEIPT_ALERT_MESSAGE = """🚨 *DUPLICATE RECEIPT* — {owner_username}
`{trade_hash}`

Previously used in:
`{previous_trade_hash}` ({previous_owner})

⚠️ Immediate action required
"""

# --- Status Update Templates ---
STATUS_UPDATE_PAID = """💰 *PAID* — {owner_username}
`{trade_hash}`
"""

STATUS_UPDATE_SUCCESSFUL = """✅ *COMPLETED* — {owner_username}
`{trade_hash}`
"""

STATUS_UPDATE_DISPUTED = """⚠️ *DISPUTED* — {owner_username}
`{trade_hash}`
Action required
"""

STATUS_UPDATE_OTHER = """🔄 *{status}* — {owner_username}
`{trade_hash}`
"""
