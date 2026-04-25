import calendar
import logging
from flask import Blueprint, jsonify, request
from datetime import datetime
from dateutil.parser import parse as date_parse
from core.bitso.fetch_funding import fetch_funding_transactions_for_user
from core.bitso.filter_data import filter_fundings_by_month, filter_fundings_by_period
from core.bitso.fallback_loader import load_eduardo_fallback_data
import bitso_config

bitso_bp = Blueprint('bitso', __name__)
logger = logging.getLogger(__name__)


def _aggregate_deposits(fundings):
    """Aggregate completed fundings into {sender_name: total_amount} sorted dict."""
    deposits = {}
    for funding in fundings:
        if funding.get('status') != 'complete':
            continue
        details = funding.get('details', {}) or {}
        clabe = details.get('sender_clabe')
        try:
            amount = float(funding.get('amount', 0))
        except (ValueError, TypeError):
            continue
        name = bitso_config.ACCOUNT.get(clabe, clabe)
        if name:
            deposits[name] = deposits.get(name, 0) + amount
    return sorted(deposits.items())


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
        last_day = calendar.monthrange(year, month)[1]

        # Fetch from all accounts
        all_fundings = []
        for user, (api_key, api_secret) in bitso_config.API_KEYS.items():
            if not api_key or not api_secret:
                print(f"Missing credentials for {user}. Skipping...")
                continue
            if user == 'eduardo_ramirez':
                print(f"Skipping API call for {user}, using fallback data directly...")
                fundings = load_eduardo_fallback_data(year, month)
            else:
                fundings = fetch_funding_transactions_for_user(
                    user, api_key, api_secret, year=year, month=month)
            all_fundings.extend(fundings)

        # Filter to this month
        filtered = filter_fundings_by_month(all_fundings, year, month)

        # Split by half-month period
        p1_fundings = filter_fundings_by_period(filtered, year, month, period=1)
        p2_fundings = filter_fundings_by_period(filtered, year, month, period=2)

        p1_deposits = _aggregate_deposits(p1_fundings)
        p2_deposits = _aggregate_deposits(p2_fundings)

        p1_total = sum(v for _, v in p1_deposits)
        p2_total = sum(v for _, v in p2_deposits)
        grand_total = p1_total + p2_total

        month_abbr = target_date.strftime('%b')

        return jsonify({
            "success": True,
            "month_str": target_date.strftime('%B %Y'),
            "period1": {
                "label": f"{month_abbr} 1–15",
                "deposits_by_sender": p1_deposits,
                "total": p1_total,
            },
            "period2": {
                "label": f"{month_abbr} 16–{last_day}",
                "deposits_by_sender": p2_deposits,
                "total": p2_total,
            },
            "total_deposits": grand_total,
            # backward-compat flat list (all deposits combined)
            "deposits_by_sender": p1_deposits + p2_deposits,
        })

    except Exception as e:
        logger.error(f"Failed to get Bitso summary: {e}")
        return jsonify({"success": False, "error": "Failed to retrieve Bitso summary."}), 500