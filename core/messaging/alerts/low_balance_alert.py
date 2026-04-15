import json
import logging
import requests
from datetime import datetime, timezone
from core.api.wallet import get_wallet_balances
from core.messaging.alerts.discord_alert import send_discord_embed
from core.messaging.alerts.telegram_alert import send_low_balance_alert
from config_messages.discord_messages import LOW_BALANCE_ALERT_EMBED
from core.api.trade_list import get_trade_list
from core.api.auth import fetch_token_with_retry
from config import PLATFORM_ACCOUNTS, DISCORD_BOT_TOKEN, DISCORD_ACTIVE_TRADES_CHANNEL_ID, STATE_DIR
from core.utils.web_utils import get_app_settings

logger = logging.getLogger(__name__)

EXCHANGE_RATES = {
    "USD_TO_MXN": 20.0,
    "BTC_TO_USD": 100000.0,
    "USDT_TO_USD": 1.00,
    "SOL_TO_USD": 150.0,
}
LOW_BALANCE_THRESHOLD_USD = 1000

# State file that stores the Discord message ID for the pinned fund meter
WALLET_METER_STATE_FILE = STATE_DIR / "wallet_meter_msg.json"

FUND_MAX_MXN   = 60_000
FUND_ALERT_MXN = 10_000
BAR_SEGMENTS   = 20


def _load_meter_message_id() -> str | None:
    """Load the saved Discord message ID for the fund meter embed."""
    try:
        with open(WALLET_METER_STATE_FILE) as f:
            return json.load(f).get("message_id")
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_meter_message_id(message_id: str) -> None:
    """Persist the Discord message ID so we can edit it on the next run."""
    with open(WALLET_METER_STATE_FILE, "w") as f:
        json.dump({"message_id": message_id}, f)


def _build_fund_bar(mxn_amount: float) -> tuple[str, float]:
    """Build a Unicode block-character progress bar. Returns (bar_string, pct 0-1)."""
    pct = min(mxn_amount / FUND_MAX_MXN, 1.0)
    filled = round(pct * BAR_SEGMENTS)
    alert_pos = round((FUND_ALERT_MXN / FUND_MAX_MXN) * BAR_SEGMENTS)

    chars = []
    for i in range(BAR_SEGMENTS):
        if i == alert_pos:
            chars.append("▲")   # threshold marker
        elif i < filled:
            chars.append("█")
        else:
            chars.append("░")
    return "".join(chars), pct


def send_wallet_fund_meter(balances: dict) -> None:
    """
    Posts (or silently edits) a "Available Funds" embed in the active trades
    channel showing a per-account MXN progress bar.
    The message is created once; on subsequent calls it is edited in-place
    so the channel stays clean.
    """
    if not DISCORD_BOT_TOKEN or not DISCORD_ACTIVE_TRADES_CHANNEL_ID:
        logger.warning("[FundMeter] Missing bot token or channel ID — skipping.")
        return

    fields = []
    has_any = False

    for account_name, balance_data in balances.items():
        if "paxful" in account_name.lower():
            continue
        if "error" in balance_data:
            continue

        # Balance keys may be lowercase or uppercase depending on the API
        mxn_raw = balance_data.get("mxn") or balance_data.get("MXN") or 0
        try:
            mxn_amount = float(mxn_raw)
        except (ValueError, TypeError):
            mxn_amount = 0.0

        bar, pct = _build_fund_bar(mxn_amount)

        if mxn_amount < FUND_ALERT_MXN:
            status = "🔴"
        elif mxn_amount < FUND_MAX_MXN / 2:
            status = "🟡"
        else:
            status = "🟢"

        formatted = f"{mxn_amount / 1000:.1f}K" if mxn_amount >= 1000 else f"{mxn_amount:.0f}"
        display_name = account_name.replace("_", " ")

        fields.append({
            "name": f"{status} {display_name}",
            "value": f"`{bar}`\n`${formatted} MXN` · `{pct * 100:.1f}%` of $60K",
            "inline": False,
        })
        has_any = True

    if not has_any:
        logger.debug("[FundMeter] No MXN balance data to display.")
        return

    embed = {
        "title": "💎 Available Funds",
        "color": 5793266,   # Discord blurple
        "fields": fields,
        "footer": {"text": "▲ = $10K alert threshold  •  Max: $60K MXN"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json",
    }
    channel_id = DISCORD_ACTIVE_TRADES_CHANNEL_ID
    payload = {"embeds": [embed]}

    # Try to edit the existing pinned message first
    message_id = _load_meter_message_id()
    if message_id:
        edit_url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
        resp = requests.patch(edit_url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            logger.debug("[FundMeter] Embed updated in active trades channel.")
            return
        logger.warning(
            f"[FundMeter] Could not edit message {message_id} "
            f"({resp.status_code}) — will post a new one."
        )

    # Post a fresh message and save its ID
    post_url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    resp = requests.post(post_url, headers=headers, json=payload, timeout=15)
    if resp.status_code == 200:
        new_id = resp.json()["id"]
        _save_meter_message_id(new_id)
        logger.info(f"[FundMeter] Fund meter posted (message ID: {new_id}).")
    else:
        logger.error(f"[FundMeter] Failed to post fund meter: {resp.status_code} — {resp.text}")



def get_crypto_in_open_trades(account):
    """
    Calculates the total amount of cryptocurrency locked in open trades for a specific account.
    """
    total_crypto_locked = {}
    access_token = fetch_token_with_retry(account)
    if not access_token:
        logger.error(f"Failed to fetch access token for {account['name']}.")
        return total_crypto_locked

    headers = {"Authorization": f"Bearer {access_token}"}
    trades = get_trade_list(account, headers, limit=50, page=1)

    if trades:
        for trade in trades:
            # Consider trades that are active but not yet completed or canceled
            if trade.get('trade_status') not in ['Successful', 'Cancelled', 'Dispute closed']:
                try:
                    crypto_amount = float(
                        trade.get('crypto_amount_requested', 0))
                    crypto_code = trade.get(
                        'crypto_currency_code', '').upper()

                    if crypto_code == 'BTC':
                        # Convert from satoshis to BTC
                        crypto_amount /= 100_000_000
                    elif crypto_code == 'USDT':
                        # Convert from the smallest unit to USDT
                        crypto_amount /= 1_000_000

                    if crypto_amount > 0 and crypto_code:
                        total_crypto_locked[crypto_code] = total_crypto_locked.get(
                            crypto_code, 0) + crypto_amount
                except (ValueError, TypeError):
                    continue
    logger.info(
        f"Found {total_crypto_locked} crypto locked in open trades for {account['name']}.")
    return total_crypto_locked


def check_wallet_balances_and_alert():
    """
    Checks wallet balances, adds funds from open trades, converts to USD,
    and sends alerts if any balance is below the threshold.
    """
    # Check if wallet alerts are enabled
    app_settings = get_app_settings()
    if not app_settings.get("wallet_alerts_enabled", True):
        logger.info("Wallet alerts are disabled. Skipping balance check.")
        return
    
    logger.debug("--- Running Low Balance Check ---")
    balances = get_wallet_balances()
    if not balances:
        logger.debug("No balances found to check.")
        return

    for account in PLATFORM_ACCOUNTS:
        account_name = account.get("name", "Unknown")
        logger.debug(f"Processing account: {account_name}")

        balance_data = balances.get(account_name, {})
        if "error" in balance_data:
            logger.error(
                f"Could not check balance for {account_name}: {balance_data['error']}")
            continue

        # --- Get crypto locked in open trades ---
        crypto_in_trades = get_crypto_in_open_trades(account)

        # --- Create a mutable copy of the balance data to include funds in escrow ---
        effective_balances = {k: float(
            v) for k, v in balance_data.items() if v is not None}

        for currency, amount in crypto_in_trades.items():
            effective_balances[currency] = effective_balances.get(
                currency, 0) + amount
            logger.debug(
                f"Adjusted {currency} balance for {account_name} by {amount} from open trades.")

        total_balance_usd = 0
        balance_details_for_alert = []

        for currency, amount in effective_balances.items():
            try:
                if amount == 0:
                    continue

                balance_usd = 0
                currency_upper = currency.upper()

                if currency_upper == "MXN":
                    balance_usd = amount / EXCHANGE_RATES["USD_TO_MXN"]
                elif currency_upper == "BTC":
                    balance_usd = amount * EXCHANGE_RATES["BTC_TO_USD"]
                elif currency_upper == "USDT":
                    balance_usd = amount * EXCHANGE_RATES["USDT_TO_USD"]
                elif currency_upper == "SOL":
                    balance_usd = amount * EXCHANGE_RATES["SOL_TO_USD"]
                else:
                    logger.warning(
                        f"  Unsupported currency '{currency}' for account {account_name}. Skipping.")

                if balance_usd > 0:
                    total_balance_usd += balance_usd
                    balance_details_for_alert.append(
                        (str(amount), currency_upper, balance_usd))
            except (ValueError, TypeError) as e:
                logger.error(
                    f"  Could not process balance for {currency} in {account_name}: Invalid amount '{amount}' - {e}")

        logger.debug(
            f"TOTAL EFFECTIVE BALANCE FOR {account_name}: ${total_balance_usd:,.2f} USD (threshold: ${LOW_BALANCE_THRESHOLD_USD:,.2f})")

        if total_balance_usd < LOW_BALANCE_THRESHOLD_USD:
            logger.warning(
                f"ALERT TRIGGERED for {account_name}: "
                f"Total balance of ${total_balance_usd:,.2f} USD is below the threshold of "
                f"${LOW_BALANCE_THRESHOLD_USD:,.2f} USD."
            )

            discord_balance_details = [
                f"- `{amount} {currency}` (approx. `${usd:,.2f}`)"
                for amount, currency, usd in balance_details_for_alert
            ]

            # --- Build Unicode progress bar for Discord ---
            FUND_MAX_MXN = 60_000
            FUND_ALERT_MXN = 10_000
            BAR_SEGMENTS = 20

            mxn_amount = effective_balances.get("mxn", effective_balances.get("MXN", 0))
            mxn_pct = min(mxn_amount / FUND_MAX_MXN, 1.0)
            filled = round(mxn_pct * BAR_SEGMENTS)
            alert_pos = round((FUND_ALERT_MXN / FUND_MAX_MXN) * BAR_SEGMENTS)

            bar_chars = []
            for i in range(BAR_SEGMENTS):
                if i == alert_pos:
                    bar_chars.append("▲")  # threshold marker
                elif i < filled:
                    bar_chars.append("█")
                else:
                    bar_chars.append("░")

            progress_bar = f"`{''.join(bar_chars)}`"

            embed_data = LOW_BALANCE_ALERT_EMBED.copy()
            embed_data["description"] = embed_data["description"].format(
                account_name=account_name,
                total_balance_usd=f"{total_balance_usd:,.2f}",
                threshold=f"{LOW_BALANCE_THRESHOLD_USD:,.2f}",
                balance_details="\n".join(discord_balance_details),
                progress_bar=progress_bar,
                mxn_amount=f"{mxn_amount:,.0f}",
                pct=mxn_pct * 100,
            )
            send_discord_embed(embed_data, alert_type="wallet")

            send_low_balance_alert(
                account_name,
                total_balance_usd,
                LOW_BALANCE_THRESHOLD_USD,
                balance_details_for_alert
            )
        else:
            logger.debug(
                f"No alert needed for {account_name}. Balance is sufficient.")

    # Always update the fund meter embed in the active trades channel
    send_wallet_fund_meter(balances)
    logger.debug("Low balance check finished.")