from flask import Blueprint, jsonify
from core.api.wallet import get_wallet_balances
from core.messaging.alerts.low_balance_alert import get_crypto_in_open_trades
from config import ACCOUNTS

wallet_bp = Blueprint('wallet', __name__)


@wallet_bp.route("/get_wallet_balances")
def get_wallet_balances_route():
    """
    Fetches wallet balances and adjusts them to include funds locked in open trades.
    """
    balances = get_wallet_balances()
    effective_balances = {}

    for account in ACCOUNTS:
        account_name = account['name']
        balance_data = balances.get(account_name, {})

        if "error" in balance_data:
            effective_balances[account_name] = balance_data
            continue

        # Get crypto locked in open trades
        crypto_in_trades = get_crypto_in_open_trades(account)
        
        # Start with the current wallet balances
        account_balances = {k: float(v) for k, v in balance_data.items() if v is not None}

        # Add the crypto from open trades to the balances
        for currency, amount in crypto_in_trades.items():
            account_balances[currency] = account_balances.get(currency, 0) + amount
        
        effective_balances[account_name] = {k: str(v) for k, v in account_balances.items()}

    return jsonify(effective_balances)