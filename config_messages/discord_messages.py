# --- Color Codes for Different Alert Types ---
COLORS = {
    # Core status colors
    "success": 5763207,    # #57F287 bright green
    "warning": 16766720,   # #FFD700 gold
    "error": 15548485,     # #ED4245 red
    "info": 5793266,       # #5865F2 Discord blurple

    # Per-event colors
    "new_trade": 16766720,   # #FFD700 gold  — stands out immediately
    "receipt": 16744448,     # #FF8C00 orange — payment action needed
    "buyer_msg": 5793266,    # #5865F2 blurple — buyer talking
    "bot_msg": 10066069,     # #99AAB5 gray   — automated/bot output
    "paid": 16766720,        # #FFD700 gold   — money moving
    "completed": 5763207,    # #57F287 green  — all done
    "disputed": 15548485,    # #ED4245 red    — alert
    "duplicate": 15548485,   # #ED4245 red    — alert
    "low_balance": 16744448, # #FF8C00 orange — warning
    "high_value": 16737095,  # #FF6F17 bold orange-gold — high-value trade

    # Legacy keys (kept for compatibility)
    "chat": 5793266,
    "NOONES_GREEN": 5763207
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
    "title_format": "{platform_emoji} NEW TRADE — {owner_username}",
    "description_format": "👤 {buyer_line}\n💰 **{amount_formatted}**\n💳 {payment_method}\n🔑 `{trade_hash}`",
    "fields": [],
    "color": "new_trade",
    "footer": "🤖 WillGang Bot"
}

# --- High-Value Trade Notification (>5000 MXN) ---
HIGH_VALUE_TRADE_EMBED = {
    "title_format": "🚨💰 HIGH VALUE TRADE — {owner_username}",
    "description_format": "👤 {buyer_line}\n💰 **{amount_formatted}**\n💳 {payment_method}\n🔑 `{trade_hash}`",
    "fields": [],
    "color": "high_value",
    "footer": "🤖 WillGang Bot — High Value Alert"
}

# --- Chat Messages ---
CHAT_MESSAGE_EMBEDS = {
    "automated": {
        "title": "🤖 AUTOMATED MESSAGE",
        "author_format": "{author}",
        "description_format": "💬 **{author}** › {owner_username}\n\n{message}",
        "color": "bot_msg"
    },
    "manual": {
        "title": "📤 MESSAGE SENT",
        "author_format": "{author}",
        "description_format": "💬 **{author}** › {owner_username}\n\n{message}",
        "color": "bot_msg"
    },
    "buyer": {
        "title": "💬 NEW MESSAGE",
        "author_format": "{author}",
        "description_format": "💬 **{author}** › {owner_username}\n\n{message}",
        "color": "buyer_msg"
    }
}

# --- Attachment Notifications ---
ATTACHMENT_EMBED = {
    "title_format": "📎 RECEIPT — {owner_username}",
    "description_format": "👤 {author}\n🏦 {bank_name}",
    "description_no_bank_format": "👤 {author}",
    "color": "receipt"
}

# --- Trade Status Updates ---
STATUS_UPDATE_EMBEDS = {
    "paid": {
        "title": "💰 TRADE PAID — {owner_username}",
        "description_format": "",
        "color": "paid"
    },
    "successful": {
        "title": "✅ TRADE COMPLETED — {owner_username}",
        "description_format": "",
        "color": "completed"
    },
    "disputed": {
        "title": "⚠️ TRADE DISPUTED — {owner_username}",
        "description_format": "",
        "color": "disputed"
    },
    "other": {
        "title_format": "🔄 {status} — {owner_username}",
        "description_format": "",
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
        "title": "✅ PAYMENT VERIFIED — {owner_username}",
        "fields": [
            {"name": "Expected", "value": "**{expected:.2f} {currency}**", "inline": True},
            {"name": "Received", "value": "**{found:.2f} {currency}** ✓", "inline": True}
        ]
    },
    "mismatch": {
        "title": "❌ AMOUNT MISMATCH — {owner_username}",
        "description": "⚠️ Review Required",
        "fields": [
            {"name": "Expected", "value": "**{expected:.2f} {currency}**", "inline": True},
            {"name": "Found", "value": "**{found:.2f} {currency}** ❌", "inline": True}
        ]
    },
    "not_found": {
        "title": "⚠️ AMOUNT NOT FOUND — {owner_username}",
        "description": "Could not extract amount from receipt",
        "fields": []
    }
}


EMAIL_VALIDATION_EMBEDS = {
    "success": {
        "title": "✅ EMAIL VERIFIED — {account_name}",
        "description": "Status: CONFIRMED ✓",
        "fields": []
    },
    "failure": {
        "title": "❌ EMAIL NOT FOUND — {account_name}",
        "description": "Status: NOT FOUND\nAction: Manual verification required",
        "fields": []
    }
}

NAME_VALIDATION_EMBEDS = {
    "success": {
        "title": "✅ NAME VERIFIED — {account_name}",
        "description": "Status: MATCH ✓",
        "fields": []
    },
    "failure": {
        "title": "❌ NAME NOT FOUND — {account_name}",
        "description": "Issue: Name not found on receipt\n⚠️ Manual review required",
        "fields": []
    }
}

LOW_BALANCE_ALERT_EMBED = {
    "title": "⚠️ Low Balance Alert",
    "color": COLORS["warning"],
    "description": (
        "The total balance for **{account_name}** has dropped below the threshold.\n\n"
        "**Available Funds (MXN)**\n"
        "{progress_bar}\n"
        "`${mxn_amount}` of `$60,000 MXN` &nbsp;·&nbsp; {pct:.1f}%\n\n"
        "**Total Balance (USD):** `${total_balance_usd}`\n"
        "**Alert Threshold:** `${threshold}`\n\n"
        "**Balance Details:**\n{balance_details}"
    ),
    "footer": {"text": "WillGang Bot"}
}

DUPLICATE_RECEIPT_EMBEDS = {
    "warning": {
        "title": "🚨 DUPLICATE RECEIPT 🚨",
        "description": "⚠️ **IMMEDIATE ACTION REQUIRED** ⚠️\n\nThis receipt has been used before",
        "fields": [
            {"name": "**CURRENT TRADE:**", "value": "{owner_username}", "inline": True},
            {"name": "**PREVIOUS TRADE:**", "value": "{previous_owner}", "inline": True}
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