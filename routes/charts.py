import logging
import glob
import json
import os
from datetime import datetime, timezone, timedelta
from dateutil.parser import isoparse
from flask import Blueprint, jsonify, send_from_directory
from core.utils import trade_history
# --- NEW IMPORTS ---
from core.utils.market_report import generate_mxn_market_report
from core.utils.client_profitability import generate_client_profitability_report
from config import TRADE_HISTORY_DIR
# --- END NEW IMPORTS ---

charts_bp = Blueprint('charts', __name__)
logger = logging.getLogger(__name__)


@charts_bp.route("/get_weekly_volume")
def get_weekly_volume():
    """Daily MXN volume for the past 7 days from the most recent normalized trade files."""
    try:
        pattern = os.path.join(TRADE_HISTORY_DIR, "*_noones_normalized_trades_*.json")
        files = glob.glob(pattern)

        # Pick the newest file per account prefix
        account_files = {}
        for f in files:
            basename = os.path.basename(f)
            parts = basename.split("_normalized_trades_")
            if len(parts) == 2:
                key = parts[0]
                date_str = parts[1].replace(".json", "")
                if key not in account_files or date_str > account_files[key][1]:
                    account_files[key] = (f, date_str)

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=7)

        # Initialise 7-day buckets (oldest → newest)
        daily_volume = {}
        daily_count  = {}
        for i in range(7):
            day = (now - timedelta(days=6 - i)).strftime("%Y-%m-%d")
            daily_volume[day] = 0.0
            daily_count[day]  = 0

        for key, (filepath, _) in account_files.items():
            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    trades = json.load(fh)
                for trade in trades:
                    if trade.get("status") != "successful":
                        continue
                    completed_at = trade.get("completed_at")
                    if not completed_at:
                        continue
                    try:
                        dt = isoparse(completed_at)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        if dt < cutoff:
                            continue
                        day_key = dt.strftime("%Y-%m-%d")
                        if day_key in daily_volume:
                            if (trade.get("fiat_currency_code") or "").upper() == "MXN":
                                amt = float(trade.get("fiat_amount_requested") or 0)
                                daily_volume[day_key] += amt
                                daily_count[day_key]  += 1
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Could not read {filepath}: {e}")

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        labels, volumes, counts = [], [], []
        for day_str in sorted(daily_volume):
            dt = datetime.strptime(day_str, "%Y-%m-%d")
            labels.append(day_names[dt.weekday()])
            volumes.append(round(daily_volume[day_str], 2))
            counts.append(daily_count[day_str])

        total = sum(volumes)
        return jsonify({
            "success": True,
            "labels": labels,
            "volumes": volumes,
            "counts": counts,
            "total_volume": round(total, 2),
            "total_trades": sum(counts),
        })

    except Exception as e:
        logger.error(f"get_weekly_volume error: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500



# --- NEW ROUTE ---
@charts_bp.route("/generate_market_report", methods=["POST"])
def generate_market_report_route():
    try:
        filepath, filename = generate_mxn_market_report()
        if filepath and filename:
            return jsonify({
                "success": True, 
                "filename": filename
            })
        else:
            return jsonify({"success": False, "error": "Failed to generate report or no data found."}), 500
    except Exception as e:
        logger.error(f"Failed to generate market report: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected server error occurred."}), 500

@charts_bp.route("/generate_client_report", methods=["POST"])
def generate_client_report_route():
    try:
        filepath, filename = generate_client_profitability_report()
        if filepath and filename:
            return jsonify({
                "success": True, 
                "filename": filename
            })
        else:
            return jsonify({"success": False, "error": "Failed to generate report or no data found."}), 500
    except Exception as e:
        logger.error(f"Failed to generate client profitability report: {e}", exc_info=True)
        return jsonify({"success": False, "error": "An unexpected server error occurred."}),500
# --- END NEW ROUTE ---


@charts_bp.route("/generate_charts", methods=["POST"])
def generate_charts():
    try:
        plot_paths = trade_history.main()
        return jsonify({"success": True, "charts": plot_paths})
    except Exception as e:
        logger.error(f"Failed to generate charts: {e}")
        return jsonify({"success": False, "error": "Failed to generate charts."}), 500


@charts_bp.route('/charts/<filename>')
def get_chart(filename):
    return send_from_directory(TRADE_HISTORY_DIR, filename, as_attachment=True) 
