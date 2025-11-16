import logging
from flask import Blueprint, jsonify, send_from_directory
from core.utils import trade_history
# --- NEW IMPORTS ---
from core.utils.market_report import generate_mxn_market_report
from config import TRADE_HISTORY 
# --- END NEW IMPORTS ---

charts_bp = Blueprint('charts', __name__)
logger = logging.getLogger(__name__)

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
    return send_from_directory(TRADE_HISTORY, filename, as_attachment=True) 
