import logging
from flask import Blueprint, jsonify
from datetime import datetime
from core.bitso.fetch_funding import fetch_funding_transactions_for_user
from core.bitso.filter_data import filter_fundings_by_month
import bitso_config

bitso_bp = Blueprint('bitso', __name__)
logger = logging.getLogger(__name__)


@bitso_bp.route("/bitso_summary")
def get_bitso_summary():
    try:
        all_fundings = []
        for user, (api_key, api_secret) in bitso_config.API_KEYS.items():
            if not api_key or not api_secret:
                print(f"Missing credentials for {user}. Skipping...")
                continue
            fundings = fetch_funding_transactions_for_user(
                user, api_key, api_secret)
            all_fundings.extend(fundings)

        now = datetime.now()
        filtered_fundings = filter_fundings_by_month(
            all_fundings, now.year, now.month)

        deposits_by_sender = {}
        for funding in filtered_fundings:
            if funding.get('status') == 'complete':
                details = funding.get('details', {}) or {}
                clabe = details.get('sender_clabe')

                try:
                    amount = float(funding.get('amount', 0))
                except (ValueError, TypeError):
                    continue

                name = bitso_config.ACCOUNT.get(clabe, clabe)
                if name:
                    deposits_by_sender[name] = deposits_by_sender.get(
                        name, 0) + amount

        sorted_deposits = sorted(deposits_by_sender.items())

        return jsonify({
            "success": True,
            "deposits_by_sender": sorted_deposits,
            "total_deposits": sum(deposits_by_sender.values())
        })

    except Exception as e:
        logger.error(f"Failed to get Bitso summary: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve Bitso summary."}), 500
