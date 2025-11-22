import logging
from core.api.wallet import get_wallet_balances
from core.messaging.alerts.discord_alert import send_discord_embed
from core.messaging.alerts.telegram_alert import send_low_balance_alert
from config_messages.discord_messages import LOW_BALANCE_ALERT_EMBED
from core.api.trade_list import get_trade_list
from core.api.auth import fetch_token_with_retry
from config import ACCOUNTS

logger = logging.getLogger(__name__)

EXCHANGE_RATES = {
    "USD_TO_MXN": 20.0,
    "BTC_TO_USD": 100000.0,
    "USDT_TO_USD": 1.00,
    "SOL_TO_USD": 150.0,
}
LOW_BALANCE_THRESHOLD_USD = 1000


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
    logger.info("--- Running Low Balance Check ---")
    balances = get_wallet_balances()
    if not balances:
        logger.info("No balances found to check.")
        return

    for account in ACCOUNTS:
        account_name = account.get("name", "Unknown")
        
        # SKIP ALL PAXFUL ACCOUNTS
        if "paxful" in account_name.lower():
            logger.info(f"Skipping Paxful account: {account_name}")
            continue
        
        logger.info(f"Processing account: {account_name}")

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
            logger.info(
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

        logger.info(
            f"--- TOTAL EFFECTIVE BALANCE FOR {account_name}: ${total_balance_usd:,.2f} USD ---")
        logger.info(
            f"Comparing to threshold: ${LOW_BALANCE_THRESHOLD_USD:,.2f} USD")

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

            embed_data = LOW_BALANCE_ALERT_EMBED.copy()
            embed_data["description"] = embed_data["description"].format(
                account_name=account_name,
                total_balance_usd=f"{total_balance_usd:,.2f}",
                threshold=f"{LOW_BALANCE_THRESHOLD_USD:,.2f}",
                balance_details="\n".join(discord_balance_details)
            )
            send_discord_embed(embed_data, alert_type="wallet")

            send_low_balance_alert(
                account_name,
                total_balance_usd,
                LOW_BALANCE_THRESHOLD_USD,
                balance_details_for_alert
            )
        else:
            logger.info(
                f"No alert needed for {account_name}. Balance is sufficient.")
    logger.info("--- Low Balance Check Finished ---")