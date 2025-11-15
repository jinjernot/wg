import os
import logging
from flask import Flask
from core.utils.log_config import setup_logging
from config import JSON_PATH
from core.utils.bot_process_manager import start_trading

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


app = Flask(__name__)
setup_logging()
logger = logging.getLogger(__name__)

if not os.path.exists(JSON_PATH):
    os.makedirs(JSON_PATH)

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

with app.app_context():
    start_trading()


if __name__ == "__main__":
    app.run(debug=True, port=5001, hotst='0.0.0.0')