import logging
from flask import Blueprint, jsonify, request
from datetime import datetime
from dateutil.parser import parse as date_parse
from core.bitso.fetch_funding import fetch_funding_transactions_for_user
from core.bitso.filter_data import filter_fundings_by_month
from core.bitso.fallback_loader import load_eduardo_fallback_data
import bitso_config

bitso_bp = Blueprint('bitso', __name__)
logger = logging.getLogger(__name__)


@bitso_bp.route("/bitso_summary")
def get_bitso_summary():
    try:
        month_str = request.args.get('month')
        if month_str:
            try:
                target_date = date_parse(month_str)
            except (ValueError, TypeError):
                return jsonify({"success": False, "error": "Invalid month format."}), 400
        else:
            target_date = datetime.now()

        year, month = target_date.year, target_date.month

        all_fundings = []
        for user, (api_key, api_secret) in bitso_config.API_KEYS.items():
            if not api_key or not api_secret:
                print(f"Missing credentials for {user}. Skipping...")
                continue
            
            # WORKAROUND: eduardo_ramirez account is gone, go directly to fallback CSV to avoid API timeout
            if user == 'eduardo_ramirez':
                print(f"Skipping API call for {user}, using fallback data directly...")
                fundings = load_eduardo_fallback_data(year, month)
            else:
                fundings = fetch_funding_transactions_for_user(
                    user, api_key, api_secret)
            
            all_fundings.extend(fundings)

        filtered_fundings = filter_fundings_by_month(
            all_fundings, year, month)

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
            "total_deposits": sum(deposits_by_sender.values()),
            "month_str": target_date.strftime('%B %Y')
        })

    except Exception as e:
        logger.error(f"Failed to get Bitso summary: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve Bitso summary."}), 500