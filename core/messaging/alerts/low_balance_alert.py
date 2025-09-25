# core/messaging/alerts/low_balance_alert.py
import logging
from core.api.wallet import get_wallet_balances
from core.messaging.alerts.discord_alert import send_discord_embed
from core.messaging.alerts.telegram_alert import send_low_balance_alert
from config_messages.discord_messages import LOW_BALANCE_ALERT_EMBED

logger = logging.getLogger(__name__)

USD_TO_MXN_EXCHANGE_RATE = 18.48
LOW_BALANCE_THRESHOLD_USD = 1000

def check_wallet_balances_and_alert():
    """
    Checks wallet balances, converts them to USD, and sends a Discord alert
    if any balance is below the low balance threshold.
    """
    logger.info("Checking wallet balances for low balance alerts...")
    balances = get_wallet_balances()

    for account_name, balance_data in balances.items():
        if "error" in balance_data:
            logger.error(f"Could not check balance for {account_name}: {balance_data['error']}")
            continue

        for currency, amount in balance_data.items():
            if currency.upper() == "MXN":
                amount_usd = float(amount) / USD_TO_MXN_EXCHANGE_RATE
                if amount_usd < LOW_BALANCE_THRESHOLD_USD:
                    logger.warning(
                        f"Low balance detected for {account_name}: "
                        f"{amount} MXN (${amount_usd:,.2f} USD) is below the threshold of "
                        f"${LOW_BALANCE_THRESHOLD_USD:,.2f} USD."
                    )
                    
                    # Send Discord Alert
                    embed_data = LOW_BALANCE_ALERT_EMBED.copy()
                    embed_data["description"] = embed_data["description"].format(
                        account_name=account_name,
                        amount=f"{float(amount):,.2f}",
                        currency=currency,
                        amount_usd=f"{amount_usd:,.2f}",
                        threshold=f"{LOW_BALANCE_THRESHOLD_USD:,.2f}"
                    )
                    send_discord_embed(embed_data, alert_type="trades")

                    # Send Telegram Alert
                    send_low_balance_alert(
                        account_name,
                        float(amount),
                        currency,
                        amount_usd,
                        LOW_BALANCE_THRESHOLD_USD
                    )