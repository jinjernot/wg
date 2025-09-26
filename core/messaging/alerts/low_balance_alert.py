import logging
from core.api.wallet import get_wallet_balances
from core.messaging.alerts.discord_alert import send_discord_embed
from core.messaging.alerts.telegram_alert import send_low_balance_alert
from config_messages.discord_messages import LOW_BALANCE_ALERT_EMBED

logger = logging.getLogger(__name__)

EXCHANGE_RATES = {
    "USD_TO_MXN": 17.0,
    "BTC_TO_USD": 65000.0,
    "USDT_TO_USD": 1.00,
    "SOL_TO_USD": 150.0,
}
LOW_BALANCE_THRESHOLD_USD = 1000

def check_wallet_balances_and_alert():
    """
    Checks wallet balances, converts them to USD, and sends alerts if any balance is below the threshold.
    """
    logger.info("--- Running Low Balance Check ---")
    balances = get_wallet_balances()
    if not balances:
        logger.info("No balances found to check.")
        return

    for account_name, balance_data in balances.items():
        logger.info(f"Processing account: {account_name}")
        if "error" in balance_data:
            logger.error(f"Could not check balance for {account_name}: {balance_data['error']}")
            continue

        total_balance_usd = 0
        balance_details_for_alert = [] # List to hold raw data for the alert function

        for currency, amount_str in balance_data.items():
            try:
                amount = float(amount_str)
                if amount == 0:
                    continue

                balance_usd = 0
                if currency.upper() == "MXN":
                    balance_usd = amount / EXCHANGE_RATES["USD_TO_MXN"]
                elif currency.upper() == "BTC":
                    if "Paxful" in account_name:
                        btc_amount = amount / 100_000_000
                        balance_usd = btc_amount * EXCHANGE_RATES["BTC_TO_USD"]
                    else:
                        balance_usd = amount * EXCHANGE_RATES["BTC_TO_USD"]
                elif currency.upper() == "USDT":
                    balance_usd = amount * EXCHANGE_RATES["USDT_TO_USD"]
                elif currency.upper() == "SOL":
                    balance_usd = amount * EXCHANGE_RATES["SOL_TO_USD"]
                else:
                    logger.warning(f"  Unsupported currency '{currency}' for account {account_name}. Skipping.")

                if balance_usd > 0:
                    total_balance_usd += balance_usd
                    # Append raw data tuple for the alert function
                    balance_details_for_alert.append((amount_str, currency.upper(), balance_usd))
            except (ValueError, TypeError) as e:
                logger.error(f"  Could not process balance for {currency} in {account_name}: Invalid amount '{amount_str}' - {e}")

        logger.info(f"--- TOTAL BALANCE FOR {account_name}: ${total_balance_usd:,.2f} USD ---")
        logger.info(f"Comparing to threshold: ${LOW_BALANCE_THRESHOLD_USD:,.2f} USD")

        if total_balance_usd < LOW_BALANCE_THRESHOLD_USD:
            logger.warning(
                f"ALERT TRIGGERED for {account_name}: "
                f"Total balance of ${total_balance_usd:,.2f} USD is below the threshold of "
                f"${LOW_BALANCE_THRESHOLD_USD:,.2f} USD."
            )
            
            # --- Discord Alert (uses a different formatting) ---
            discord_balance_details = [
                f"- `{amount} {currency}` (approx. `${usd:,.2f}`)"
                for amount, currency, usd in balance_details_for_alert
            ]
            
            embed_data = LOW_BALANCE_ALERT_EMBED.copy()
            embed_data["description"] = embed_data["description"].format(
                account_name=account_name,
                total_balance_usd=f"{total_balance_usd:,.2f}",
                threshold=f"{LOW_BALANCE_THRESHOLD_USD:,.2f}",
                balance_details="\n".join(discord_balance_details)
            )
            send_discord_embed(embed_data, alert_type="trades")

            # --- Telegram Alert (passes raw data) ---
            send_low_balance_alert(
                account_name,
                total_balance_usd,
                LOW_BALANCE_THRESHOLD_USD,
                balance_details_for_alert # Pass the list of tuples
            )
        else:
            logger.info(f"No alert needed for {account_name}. Balance is sufficient.")
    logger.info("--- Low Balance Check Finished ---")