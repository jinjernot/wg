import os
import logging
import atexit
from flask import Flask
from core.utils.log_config import setup_logging
from config import PAYMENT_ACCOUNTS_PATH, DISCORD_WEBHOOKS
from core.utils.bot_process_manager import start_trading
from core.utils.heartbeat import HeartbeatMonitor
from core.utils.http_client import get_http_client, close_http_client
from core.utils.api_metrics import get_api_metrics

# Import blueprints
from routes.main import main_bp
from routes.wallet import wallet_bp
from routes.settings import settings_bp
from routes.trades import trades_bp
from routes.offers import offers_bp
from routes.user import user_bp
from routes.bitso import bitso_bp
from routes.charts import charts_bp
from routes.bot import bot_bp
from routes.giftcards import giftcards_bp


app = Flask(__name__)
setup_logging()
logger = logging.getLogger(__name__)

# Initialize HTTP client for connection pooling
http_client = get_http_client()
logger.info("HTTP client initialized with connection pooling")

if not os.path.exists(PAYMENT_ACCOUNTS_PATH):
    os.makedirs(PAYMENT_ACCOUNTS_PATH)

# Initialize heartbeat monitor
heartbeat = None
if DISCORD_WEBHOOKS.get("logs"):
    heartbeat = HeartbeatMonitor(
        webhook_url=DISCORD_WEBHOOKS["logs"],
        interval_seconds=300  # Update every 5 minutes
    )
    heartbeat.start()
    logger.info("Heartbeat monitoring enabled")
else:
    logger.warning("No logs webhook configured, heartbeat disabled")

# Cleanup on shutdown
def cleanup():
    logger.info("Application shutting down...")
    
    if heartbeat:
        heartbeat.stop()
    
    # Save API metrics
    api_metrics = get_api_metrics()
    api_metrics.save_to_file('data/api_metrics.json')
    api_metrics.log_summary()
    
    # Close HTTP client
    close_http_client()
    logger.info("Cleanup completed")

atexit.register(cleanup)

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(wallet_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(trades_bp)
app.register_blueprint(offers_bp)
app.register_blueprint(user_bp)
app.register_blueprint(bitso_bp)
app.register_blueprint(charts_bp)
app.register_blueprint(bot_bp)
app.register_blueprint(giftcards_bp)

with app.app_context():
    start_trading()


if __name__ == "__main__":
    app.run(debug=True, port=5001, host='0.0.0.0', use_reloader=False)