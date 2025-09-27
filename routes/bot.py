from flask import Blueprint, jsonify
import core.utils.bot_process_manager as bot_process_manager

bot_bp = Blueprint('bot', __name__)

@bot_bp.route("/start_trading", methods=["POST"])
def start_trading_route():
    result = bot_process_manager.start_trading()
    return jsonify(result)

@bot_bp.route("/stop_trading", methods=["POST"])
def stop_trading_route():
    result = bot_process_manager.stop_trading()
    return jsonify(result)

@bot_bp.route("/trading_status")
def trading_status_route():
    result = bot_process_manager.get_trading_status()
    return jsonify(result)