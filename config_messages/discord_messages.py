# --- Color Codes for Different Alert Types ---
COLORS = {
    "info": 3447003, 
    "success": 3066993,
    "warning": 15105570, 
    "error": 15158332,  
    "chat": 8359053,  
    "NOONES_GREEN": 2044896
}

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


# --- New Trade Notification ---
NEW_TRADE_EMBED = {
    "title_format": "{platform_emoji} NEW TRADE STARTED",
    "description_format": "══════════════════════════════\n\n**BUYER**\n{buyer_line}",
    "fields": [
        {"name": "\u200b", "value": "**TRADE DETAILS**", "inline": False},
        {"name": "💰 Amount", "value_format": "**{amount_formatted}**", "inline": True},
        {"name": "💳 Method", "value_format": "**{payment_method}**", "inline": True},
        {"name": "🏦 Account", "value_format": "**{owner_username}**", "inline": True},
        {"name": "\u200b", "value_format": "**TRADE ID**\n[{trade_hash}]({trade_url})", "inline": False}
    ],
    "footer": "🤖 WillGang Bot"
}

# --- Chat Messages ---
CHAT_MESSAGE_EMBEDS = {
    "automated": {
        "title": "🤖 AUTOMATED MESSAGE",
        "author_format": "FROM: {author}",
        "description_format": "**TRADE:** {trade_hash} • **{owner_username}**\n\n\"{message}\"",
        "color_type": "info"
    },
    "manual": {
        "title": "📤 MESSAGE SENT",
        "author_format": "FROM: {author}",
        "description_format": "**TRADE:** {trade_hash} • **{owner_username}**\n\n\"{message}\"",
        "color_type": "info"
    },
    "buyer": {
        "title": "💬 CHAT MESSAGE",
        "author_format": "FROM: {author}",
        "description_format": "**TRADE:** {trade_hash} • **{owner_username}**\n\n\"{message}\"",
        "color_type": "platform"
    }
}

# --- Attachment Notifications ---
ATTACHMENT_EMBED = {
    "title": "📎 PAYMENT RECEIPT",
    "description_format": "**TRADE:** {trade_hash}\n**FROM:** {author} → {owner_username}",
    "bank_field": {"name": "**BANK:**", "value": "{bank_name}", "inline": False},
    "image_field": {"name": "📸 Receipt Image", "value": "Review Required", "inline": False}
}

# --- Trade Status Updates ---
STATUS_UPDATE_EMBEDS = {
    "paid": {
        "title": "💰 TRADE PAID",
        "description_format": "**TRADE:** {trade_hash} • **{owner_username}**\n\nStatus: **PAID** ✅",
        "color": "warning"
    },
    "successful": {
        "title": "✅ TRADE COMPLETED",
        "description_format": "**TRADE:** {trade_hash} • **{owner_username}**\n\nStatus: **COMPLETED** ✅",
        "color": "success"
    },
    "disputed": {
        "title": "⚠️ TRADE DISPUTED",
        "description_format": "**TRADE:** {trade_hash} • **{owner_username}**\n\nStatus: **DISPUTE** ⚠️",
        "color": "error"
    },
    "other": {
        "title_format": "🔄 STATUS UPDATE: {status}",
        "description_format": "**TRADE:** {trade_hash} • **{owner_username}**\n\nStatus: **{status}**",
        "color": "info"
    }
}

# --- General Messages ---
SERVER_UNREACHABLE = "⚠️ **Web server is unreachable.**\nMake sure the Flask app (`app.py`) is running."

# --- /status Command ---
STATUS_EMBED = {
    "running": {
        "title": "Bot Status",
        "description": "✅ Trading process is **Running**.",
        "color": COLORS["success"]
    },
    "stopped": {
        "title": "Bot Status",
        "description": "❌ Trading process is **Stopped**.",
        "color": COLORS["error"]
    },
    "error": {
        "title": "Bot Status",
        "description": "⚠️ **Could not get status.** The web server responded with: {status_code}",
        "color": COLORS["warning"]
    },
    "unreachable": {
        "title": "Bot Status",
        "description": SERVER_UNREACHABLE,
        "color": COLORS["warning"]
    }
}


# --- /active_trades Command ---
ACTIVE_TRADES_EMBED = {
    "title": "📊 Active Trades ({trade_count})",
    "description": "( ͡° ͜ʖ ͡°)",
    "color": COLORS["info"],
    "footer": "Last updated"
}

NO_ACTIVE_TRADES_EMBED = {
    "title": "📊 Active Trades",
    "description": "No active trades found at the moment.",
    "color": COLORS["success"]
}

USER_PROFILE_EMBED = {
    "title": "👤 User Profile: {username}",
    "color": COLORS["info"],
    "description": "First trade on **{first_trade_date}** • Last trade on **{last_trade_date}**",
    "fields": [
        {"name": "Total Volume", "value": "${total_volume:.2f} MXN", "inline": True},
        {"name": "Avg. Trade Size", "value": "${avg_trade_size:.2f} MXN", "inline": True},
        {"name": "Success Rate", "value": "{success_rate}%", "inline": True},
        {"name": "✅ Successful Trades", "value": "{successful_trades}", "inline": True},
        {"name": "❌ Issues (Canceled/Disputed)", "value": "{issues}", "inline": True},
    ]
}

USER_NOT_FOUND_EMBED = {
    "title": "⚠️ User Not Found",
    "description": "Could not find any trading history for the user `{username}`.",
    "color": COLORS["warning"]
}


# --- /toggle_offers Command ---
TOGGLE_OFFERS_EMBED = {
    "success": {
        "title": "✅ Offers Toggled {status}",
        "description": "{message}",
        "color": COLORS["success"]
    },
    "error": {
        "title": "❌ Error Toggling Offers",
        "description": "The server responded with: {status_code}",
        "color": COLORS["error"]
    }
}


# --- /summary Command ---
SUMMARY_EMBED = {
    "title": "📊 Daily Summary for {date}",
    "color": COLORS["info"],
    "fields": {
        "total_trades": {"name": "Total Trades Today", "value": "**{total_trades}**", "inline": True},
        "total_volume": {"name": "Total Volume", "value": "**${total_volume:.2f}**", "inline": True},
        "divider": {"name": "\u200b", "value": "\u200b", "inline": False},
        "successful": {"name": "✅ Successful", "value": "**{successful_trades}**", "inline": True},
        "paid": {"name": "💰 Paid (Pending BTC)", "value": "**{paid_trades}**", "inline": True},
        "active": {"name": "🏃 Active", "value": "**{active_trades}**", "inline": True}
    }
}

# --- /bot Command ---
BOT_CONTROL_EMBEDS = {
    "start_success": {
        "title": "Bot Started Successfully",
        "description": "{message}",
        "color": COLORS["success"]
    },
    "stop_success": {
        "title": "Bot Stopped Successfully",
        "description": "{message}",
        "color": COLORS["error"]
    },
    "error": {
        "title": "Error {action}ing Bot",
        "description": "{message}",
        "color": COLORS["warning"]
    }
}

# --- /settings Command ---
SETTINGS_EMBEDS = {
    "success": {
        "title": "⚙️ Setting Updated",
        "description": "**{setting_name}** has been turned **{status_name}**.",
        "color": COLORS["success"]
    },
    "error": {
        "title": "❌ Error Updating Setting",
        "description": "{error}",
        "color": COLORS["error"]
    }
}

# --- /send_message Command ---
SEND_MESSAGE_EMBEDS = {
    "success": {
        "title": "✉️ Message Sent",
        "description": "Successfully sent message to `{trade_hash}`.",
        "color": COLORS["info"],
        "field_name": "Message"
    },
    "error": {
        "title": "❌ Failed to Send Message",
        "description": "{error}",
        "color": COLORS["error"]
    }
}

# --- Amount and Email Validation Embeds ---
AMOUNT_VALIDATION_EMBEDS = {
    "matched": {
        "title": "✅ PAYMENT VERIFIED",
        "fields": [
            {"name": "**ACCOUNT:**", "value": "{owner_username}", "inline": False},
            {"name": "\u200b", "value": "**AMOUNT CHECK**", "inline": False},
            {"name": "Expected", "value": "**{expected:.2f} {currency}** ✓", "inline": True},
            {"name": "Received", "value": "**{found:.2f} {currency}** ✓", "inline": True},
            {"name": "\u200b", "value": "Status: **MATCH** ✓", "inline": False}
        ]
    },
    "mismatch": {
        "title": "❌ AMOUNT MISMATCH",
        "description": "⚠️ **REVIEW REQUIRED** ⚠️",
        "fields": [
            {"name": "**ACCOUNT:**", "value": "{owner_username}", "inline": False},
            {"name": "\u200b", "value": "**AMOUNT CHECK**", "inline": False},
            {"name": "Expected", "value": "**{expected:.2f} {currency}**", "inline": True},
            {"name": "Found", "value": "**{found:.2f} {currency}** ❌", "inline": True}
        ]
    },
    "not_found": {
        "title": "⚠️ AMOUNT NOT FOUND",
        "fields": [
            {"name": "**ACCOUNT:**", "value": "{owner_username}", "inline": False},
            {"name": "**OCR RESULT:**", "value": "Could not extract amount from receipt", "inline": False}
        ]
    }
}


EMAIL_VALIDATION_EMBEDS = {
    "success": {
        "title": "✅ EMAIL PAYMENT VERIFIED",
        "description": "**Status:** CONFIRMED ✓",
        "fields": [
            {"name": "**VALIDATED IN:**", "value": "{account_name}", "inline": False}
        ]
    },
    "failure": {
        "title": "❌ EMAIL NOT FOUND",
        "description": "**Status:** NOT FOUND",
        "fields": [
            {"name": "**SEARCHED IN:**", "value": "{account_name}", "inline": False},
            {"name": "**ACTION:**", "value": "Manual verification required", "inline": False}
        ]
    }
}

NAME_VALIDATION_EMBEDS = {
    "success": {
        "title": "✅ NAME VERIFIED",
        "description": "**Status:** MATCH ✓",
        "fields": [
            {"name": "**Account Verified:**", "value": "{account_name}", "inline": False}
        ]
    },
    "failure": {
        "title": "❌ NAME NOT FOUND",
        "description": "⚠️ **MANUAL REVIEW REQUIRED** ⚠️",
        "fields": [
            {"name": "**Expected Account:**", "value": "{account_name}", "inline": False},
            {"name": "**Issue:**", "value": "Account name not found on receipt", "inline": False}
        ]
    }
}

LOW_BALANCE_ALERT_EMBED = {
    "title": "⚠️ Low Balance Alert",
    "color": COLORS["warning"],
    "description": (
        "The total balance for **{account_name}** is below the threshold.\n\n"
        "**Total Balance:** `${total_balance_usd}`\n"
        "**Threshold:** `${threshold}`\n\n"
        "**Balance Details:**\n{balance_details}"
    ),
    "footer": {"text": "WillGang Bot"}
}

DUPLICATE_RECEIPT_EMBEDS = {
    "warning": {
        "title": "🚨 DUPLICATE RECEIPT 🚨",
        "description": "⚠️ **IMMEDIATE ACTION REQUIRED** ⚠️\n\nThis receipt has been used before",
        "fields": [
            {"name": "**CURRENT TRADE:**", "value": "{trade_hash} ({owner_username})", "inline": True},
            {"name": "**PREVIOUS TRADE:**", "value": "{previous_trade_hash} ({previous_owner})", "inline": True}
        ]
    }
}


RELEASE_TRADE_EMBEDS = {
    "success": {
        "title": "✅ Trade Released",
        "description": "Successfully released the crypto for trade {trade_hash}.",
        "color": COLORS["success"]
    },
    "error": {
        "title": "❌ Failed to Release Trade",
        "description": "Could not release the trade.\n**Reason**: {error}",
        "color": COLORS["error"]
    }
}