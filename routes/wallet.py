from flask import Blueprint, jsonify
from core.api.wallet import get_wallet_balances

wallet_bp = Blueprint('wallet', __name__)

@wallet_bp.route("/get_wallet_balances")
def get_wallet_balances_route():
    balances = get_wallet_balances()
    return jsonify(balances)