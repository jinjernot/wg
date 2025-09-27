import logging
from flask import Blueprint, jsonify, send_from_directory
from core.utils import trade_history
from config import TRADE_HISTORY

charts_bp = Blueprint('charts', __name__)
logger = logging.getLogger(__name__)

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
    return send_from_directory(TRADE_HISTORY, filename)