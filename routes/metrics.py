from flask import Blueprint, jsonify
from core.utils.customer_metrics import get_new_customers_this_month, get_customer_growth_metrics
import logging

metrics_bp = Blueprint('metrics', __name__)
logger = logging.getLogger(__name__)


@metrics_bp.route("/new_customers")
def new_customers():
    """
    Get new customers for the current month.
    A new customer is someone whose first trade ever was in the current month.
    """
    try:
        data = get_new_customers_this_month()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching new customers metric: {e}")
        return jsonify({"error": str(e), "count": 0}), 500


@metrics_bp.route("/customer_growth")
def customer_growth():
    """
    Get customer growth metrics over the past 6 months.
    """
    try:
        data = get_customer_growth_metrics(months_back=6)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error fetching customer growth metrics: {e}")
        return jsonify({"error": str(e)}), 500
