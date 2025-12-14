import logging
import json
import os
from flask import Blueprint, jsonify, request, send_file
from core.utils.gift_card_analytics import (
    get_gift_card_summary,
    filter_gift_card_trades,
    get_gift_card_trades_by_type,
    generate_gift_card_csv,
    GIFT_CARD_SLUGS
)
from config import TRADE_HISTORY_DIR

giftcards_bp = Blueprint('giftcards', __name__)
logger = logging.getLogger(__name__)


def load_all_trades():
    """Load all normalized trade data from the trade history directory."""
    all_trades = []
    
    if not os.path.exists(TRADE_HISTORY_DIR):
        logger.warning(f"Trade history directory not found: {TRADE_HISTORY_DIR}")
        return all_trades
    
    # Find all normalized trade JSON files
    for filename in os.listdir(TRADE_HISTORY_DIR):
        if "_normalized_trades_" in filename and filename.endswith(".json"):
            filepath = os.path.join(TRADE_HISTORY_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    trades = json.load(f)
                    all_trades.extend(trades)
            except Exception as e:
                logger.error(f"Error loading trade file {filename}: {e}")
    
    logger.info(f"Loaded {len(all_trades)} total trades from history")
    return all_trades


@giftcards_bp.route("/get_giftcard_stats", methods=["GET"])
def get_giftcard_stats():
    """
    Get gift card trade statistics.
    Query params:
        - days (optional): Number of days to look back
    """
    try:
        days = request.args.get('days', type=int)
        
        # Load all trade data
        all_trades = load_all_trades()
        
        if not all_trades:
            return jsonify({
                "success": False,
                "error": "No trade data found. Please run trade history generation first."
            }), 404
        
        # Get gift card summary
        stats = get_gift_card_summary(all_trades, days=days)
        
        return jsonify({
            "success": True,
            "stats": stats
        })
    
    except Exception as e:
        logger.error(f"Error getting gift card stats: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@giftcards_bp.route("/get_giftcard_trades", methods=["GET"])
def get_giftcard_trades():
    """
    Get list of gift card trades with optional filters.
    Query params:
        - card_type (optional): Filter by specific card type
        - account (optional): Filter by account name
        - start_date (optional): Start date filter (YYYY-MM-DD)
        - end_date (optional): End date filter (YYYY-MM-DD)
    """
    try:
        card_type = request.args.get('card_type')
        account = request.args.get('account')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Load all trade data
        all_trades = load_all_trades()
        
        if not all_trades:
            return jsonify({
                "success": False,
                "error": "No trade data found"
            }), 404
        
        # Filter by card type if specified
        if card_type:
            trades = get_gift_card_trades_by_type(all_trades, card_type)
        else:
            trades = filter_gift_card_trades(all_trades)
        
        # Filter by account if specified
        if account:
            trades = [t for t in trades if t.get("account_name", "").lower() == account.lower()]
        
        # Filter by date range if specified
        if start_date or end_date:
            from datetime import datetime
            filtered_trades = []
            
            for trade in trades:
                completed_at = trade.get("completed_at")
                if not completed_at:
                    continue
                
                try:
                    trade_date = datetime.strptime(completed_at, "%Y-%m-%d %H:%M:%S")
                    
                    if start_date:
                        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                        if trade_date < start_dt:
                            continue
                    
                    if end_date:
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        if trade_date > end_dt:
                            continue
                    
                    filtered_trades.append(trade)
                except Exception as e:
                    logger.warning(f"Could not parse date {completed_at}: {e}")
            
            trades = filtered_trades
        
        return jsonify({
            "success": True,
            "trades": trades,
            "count": len(trades)
        })
    
    except Exception as e:
        logger.error(f"Error getting gift card trades: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@giftcards_bp.route("/export_giftcard_report", methods=["POST"])
def export_giftcard_report():
    """
    Generate and download a CSV report of gift card trades.
    """
    try:
        # Load all trade data
        all_trades = load_all_trades()
        
        if not all_trades:
            return jsonify({
                "success": False,
                "error": "No trade data found"
            }), 404
        
        # Filter to gift card trades only
        gift_card_trades = filter_gift_card_trades(all_trades)
        
        if not gift_card_trades:
            return jsonify({
                "success": False,
                "error": "No gift card trades found"
            }), 404
        
        # Generate CSV
        csv_path = generate_gift_card_csv(gift_card_trades, TRADE_HISTORY_DIR)
        
        if csv_path and os.path.exists(csv_path):
            return send_file(
                csv_path,
                as_attachment=True,
                download_name=os.path.basename(csv_path),
                mimetype='text/csv'
            )
        else:
            return jsonify({
                "success": False,
                "error": "Failed to generate CSV report"
            }), 500
    
    except Exception as e:
        logger.error(f"Error exporting gift card report: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@giftcards_bp.route("/giftcard_types", methods=["GET"]) 
def get_giftcard_types():
    """Get list of available gift card types."""
    return jsonify({
        "success": True,
        "card_types": GIFT_CARD_SLUGS
    })
