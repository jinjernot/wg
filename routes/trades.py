import os
import json
import logging
from flask import Blueprint, jsonify, request
from core.api.auth import fetch_token_with_retry
from core.messaging.message_sender import send_message_with_retry
from config import PLATFORM_ACCOUNTS, CHAT_URL_PAXFUL, CHAT_URL_NOONES, TRADES_ACTIVE_DIR
from core.api.trade_chat import get_all_messages_from_chat, release_trade

trades_bp = Blueprint('trades', __name__)
logger = logging.getLogger(__name__)


@trades_bp.route("/get_active_trades")
def get_active_trades():
    active_trades_data = []
    if not os.path.exists(TRADES_ACTIVE_DIR):
        return jsonify([])

    for filename in os.listdir(TRADES_ACTIVE_DIR):
        if filename.endswith("_trades.json"):
            try:
                filepath = os.path.join(TRADES_ACTIVE_DIR, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    trades_list = data.get("data", {}).get("trades", [])
                    if trades_list:
                        account_name_source = filename.replace(
                            "_trades.json", "").replace("_", " ").title()
                        for trade in trades_list:
                            trade['account_name_source'] = account_name_source
                            
                            # Check for attachments for ALL trades (not just Paid)
                            # Use original filename for lookup (case-sensitive match)
                            account_name_for_lookup = filename.replace("_trades.json", "")
                            account = next(
                                (acc for acc in PLATFORM_ACCOUNTS if acc["name"] == account_name_for_lookup), None)
                            if account:
                                token = fetch_token_with_retry(account)
                                if token:
                                    headers = {"Authorization": f"Bearer {token}"}
                                    all_messages = get_all_messages_from_chat(
                                        trade.get("trade_hash"), account, headers)
                                    
                                    # Debug logging
                                    logger.info(f"[ATTACHMENT CHECK] Trade {trade.get('trade_hash')}: Got {len(all_messages) if all_messages else 0} messages")
                                    
                                    if all_messages:
                                        attachment_messages = [msg for msg in all_messages if msg.get("type") == "trade_attach_uploaded"]
                                        logger.info(f"[ATTACHMENT CHECK] Trade {trade.get('trade_hash')}: Found {len(attachment_messages)} attachment messages")
                                        trade['has_attachment'] = len(attachment_messages) > 0
                                    else:
                                        logger.warning(f"[ATTACHMENT CHECK] Trade {trade.get('trade_hash')}: No messages returned!")
                                        trade['has_attachment'] = False
                                else:
                                    logger.error(f"[ATTACHMENT CHECK] Trade {trade.get('trade_hash')}: Failed to get token")
                                    trade['has_attachment'] = False
                            else:
                                logger.error(f"[ATTACHMENT CHECK] Trade {trade.get('trade_hash')}: Account not found")
                                trade['has_attachment'] = False
                        active_trades_data.extend(trades_list)
            except Exception as e:
                logger.error(
                    f"Could not read or parse trades file {filename}: {e}")
    return jsonify(active_trades_data)


@trades_bp.route("/send_manual_message", methods=["POST"])
def send_manual_message():
    data = request.json
    trade_hash = data.get("trade_hash")
    account_name = data.get("account_name")
    message = data.get("message")

    if not all([trade_hash, account_name, message]):
        return jsonify({"success": False, "error": "Missing trade hash, account name, or message."}), 400

    # --- ADDED TEMPORARY CHECK ---
    if "_Paxful" in account_name:
        logger.warning(f"Temporarily skipping manual message for Paxful account: {account_name}")
        return jsonify({"success": False, "error": "Paxful actions are temporarily disabled."}), 400
    # --- END OF CHECK ---

    formatted_account_name = account_name.replace(" ", "_")
    target_account = next((acc for acc in PLATFORM_ACCOUNTS if acc["name"].lower(
    ) == formatted_account_name.lower()), None)

    if not target_account:
        return jsonify({"success": False, "error": f"Account '{account_name}' not found."}), 404

    token = fetch_token_with_retry(target_account)
    if not token:
        return jsonify({"success": False, "error": "Could not authenticate."}), 500

    headers = {"Authorization": f"Bearer {token}",
               "Content-Type": "application/x-www-form-urlencoded"}
    chat_url = CHAT_URL_PAXFUL if "_Paxful" in target_account["name"] else CHAT_URL_NOONES
    body = {"trade_hash": trade_hash, "message": message}

    if send_message_with_retry(chat_url, body, headers):
        return jsonify({"success": True, "message": "Message sent successfully!"})
    else:
        return jsonify({"success": False, "error": "Failed to send message via API."}), 500

@trades_bp.route("/release_trade", methods=["POST"])
def release_trade_route():
    data = request.json
    trade_hash = data.get("trade_hash")
    account_name = data.get("account_name")

    if not all([trade_hash, account_name]):
        return jsonify({"success": False, "error": "Missing trade hash or account name."}), 400

    # --- ADDED TEMPORARY CHECK ---
    if "_Paxful" in account_name:
        logger.warning(f"Temporarily skipping trade release for Paxful account: {account_name}")
        return jsonify({"success": False, "error": "Paxful actions are temporarily disabled."}), 400
    # --- END OF CHECK ---

    formatted_account_name = account_name.replace(" ", "_")
    target_account = next((acc for acc in PLATFORM_ACCOUNTS if acc["name"].lower() == formatted_account_name.lower()), None)

    if not target_account:
        return jsonify({"success": False, "error": f"Account '{account_name}' not found."}), 404

    result = release_trade(trade_hash, target_account)
    return jsonify(result)