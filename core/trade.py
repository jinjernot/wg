import logging
from datetime import datetime, timezone
from config import CHAT_URL_PAXFUL, CHAT_URL_NOONES, PAYMENT_REMINDER_DELAY, EMAIL_CHECK_DURATION
from .get_files import load_processed_trades, save_processed_trade
from .get_trade_chat import fetch_trade_chat_messages
from .email_checker import check_for_payment_email
from .ocr_processor import extract_text_from_image, find_amount_in_text
from .messaging.welcome_message import send_welcome_message
from .messaging.payment_details import send_payment_details_message
from .messaging.trade_lifecycle_messages import (
    send_trade_completion_message,
    send_payment_received_message,
    send_payment_reminder_message
)
from .messaging.attachment_message import send_attachment_message
from .messaging.telegram_alert import (
    send_telegram_alert,
    send_attachment_alert,
    send_amount_validation_alert,
    send_email_validation_alert
)
from .messaging.discord_alert import (
    create_new_trade_embed,
    create_attachment_embed,
    create_amount_validation_embed,
    create_email_validation_embed
)

logger = logging.getLogger(__name__)

class Trade:
    def __init__(self, trade_data, account, headers, gmail_service):
        self.data = trade_data
        self.account = account
        self.headers = headers
        self.gmail_service = gmail_service

        self.trade_hash = self.data.get("trade_hash")
        self.owner_username = self.data.get("owner_username", "unknown_user")
        self.platform = "Paxful" if "_Paxful" in self.account["name"] else "Noones"
        
        all_processed = load_processed_trades(self.owner_username, self.platform)
        self.processed_data = all_processed.get(self.trade_hash, {})

    def save(self):
        """Saves the current state of the trade's processed data."""
        save_processed_trade(self.data, self.platform, self.processed_data)

    def process(self):
        """Main entry point to process a trade's lifecycle."""
        if not self.trade_hash or not self.owner_username:
            logger.error(f"Missing trade_hash or owner_username for trade: {self.data}")
            return

        is_new = not self.processed_data
        if is_new:
            self.handle_new_trade()

        self.check_status_change()
        self.check_for_email_confirmation()
        self.check_chat_and_attachments()
        self.check_for_inactivity()
        
        self.save()

    def handle_new_trade(self):
            """Handles logic for a trade seen for the first time."""
            logger.info(f"New trade found: {self.trade_hash}. Handling initial messages.")
            send_telegram_alert(self.data, self.platform)
            create_new_trade_embed(self.data, self.platform)
            
            self.processed_data['first_seen_utc'] = datetime.now(timezone.utc).isoformat()
            
            send_welcome_message(self.data, self.account, self.headers)

            payment_method_slug = self.data.get("payment_method_slug", "").lower()
            if payment_method_slug in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios","domestic-wire-transfer"]:
                chat_url = CHAT_URL_PAXFUL if self.platform == "Paxful" else CHAT_URL_NOONES
                send_payment_details_message(self.trade_hash, payment_method_slug, self.headers, chat_url, self.owner_username)

            self.processed_data['status_history'] = [self.data.get("trade_status")]

    def check_status_change(self):
        """Checks for and handles changes in the trade's status."""
        current_status = self.data.get("trade_status")
        if current_status not in self.processed_data.get('status_history', []):
            logger.info(f"Trade {self.trade_hash} has a new status: '{current_status}'")
            if current_status == 'Successful':
                send_trade_completion_message(self.trade_hash, self.account, self.headers)
            elif current_status == 'Paid':
                send_payment_received_message(self.trade_hash, self.account, self.headers)
                if 'paid_timestamp' not in self.processed_data:
                    self.processed_data['paid_timestamp'] = datetime.now(timezone.utc).timestamp()
            
            self.processed_data.setdefault('status_history', []).append(current_status)

    def check_for_email_confirmation(self):
        """Checks for payment confirmation emails if the trade is marked as Paid."""
        is_paid = self.data.get("trade_status") == 'Paid'
        is_relevant_method = self.data.get("payment_method_slug", "").lower() in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]
        is_pending = not self.processed_data.get('email_verified') and not self.processed_data.get('email_check_timed_out')

        if not (is_paid and is_relevant_method and is_pending):
            return

        paid_timestamp = self.processed_data.get('paid_timestamp')
        if not paid_timestamp: return
            
        elapsed_time = datetime.now(timezone.utc).timestamp() - paid_timestamp
        if elapsed_time < EMAIL_CHECK_DURATION:
            logger.info(f"Trade {self.trade_hash} is Paid. Re-checking for confirmation email...")
            if self.gmail_service and check_for_payment_email(self.gmail_service, self.data, self.platform):
                logger.info(f"PAYMENT VERIFIED via email for trade {self.trade_hash}.")
                send_email_validation_alert(self.trade_hash, success=True)
                create_email_validation_embed(self.trade_hash, success=True)
                self.processed_data['email_verified'] = True
        else:
            logger.warning(f"Email check for trade {self.trade_hash} timed out.")
            send_email_validation_alert(self.trade_hash, success=False)
            create_email_validation_embed(self.trade_hash, success=False)
            self.processed_data['email_check_timed_out'] = True

    def check_chat_and_attachments(self):
        """Fetches chat history and processes any new attachments."""
        if self.processed_data.get('attachment_message_sent'):
            return

        attachment_found, author, last_buyer_ts, new_paths = fetch_trade_chat_messages(self.trade_hash, self.account, self.headers)
        
        if last_buyer_ts: self.processed_data['last_buyer_ts'] = last_buyer_ts

        if attachment_found:
            logger.info(f"New attachment found for trade {self.trade_hash}. Processing.")
            send_attachment_message(self.trade_hash, self.account, self.headers)
            
            for path in new_paths:
                send_attachment_alert(self.trade_hash, author, path)
                create_attachment_embed(self.trade_hash, author, path)
                
                logger.info(f"Performing OCR on {path}...")
                text = extract_text_from_image(path)
                found_amount = find_amount_in_text(text, self.data.get("fiat_amount_requested"))
                
                # Send alerts to both services
                expected = self.data.get("fiat_amount_requested")
                currency = self.data.get("fiat_currency_code")
                send_amount_validation_alert(self.trade_hash, expected, found_amount, currency)
                create_amount_validation_embed(self.trade_hash, expected, found_amount, currency)

            self.processed_data['attachment_message_sent'] = True

    def check_for_inactivity(self):
        """Sends a payment reminder if the trade has been inactive for too long."""
        is_active = self.data.get("trade_status", "").startswith('Active')
        if not is_active or self.processed_data.get('reminder_sent'):
            return

        reference_time = None
        if self.processed_data.get('last_buyer_ts'):
            reference_time = datetime.fromtimestamp(self.processed_data['last_buyer_ts'], tz=timezone.utc)
        elif self.data.get("start_date"):
            try:
                reference_time = datetime.fromisoformat(self.data["start_date"]).replace(tzinfo=timezone.utc)
            except ValueError:
                logger.error(f"Could not parse start_date for trade {self.trade_hash}.")
        
        if reference_time and (datetime.now(timezone.utc) - reference_time).total_seconds() > PAYMENT_REMINDER_DELAY:
            logger.info(f"Sending payment reminder for trade {self.trade_hash} due to inactivity.")
            send_payment_reminder_message(self.trade_hash, self.account, self.headers)
            self.processed_data['reminder_sent'] = True