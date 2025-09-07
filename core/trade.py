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
            self.account = account
            self.headers = headers
            self.gmail_service = gmail_service

            self.trade_hash = trade_data.get("trade_hash")
            self.owner_username = trade_data.get("owner_username", "unknown_user")
            self.platform = "Paxful" if "_Paxful" in self.account["name"] else "Noones"
            
            all_trades = load_processed_trades(self.owner_username, self.platform)
            existing_data = all_trades.get(self.trade_hash, {})
            self.trade_state = {**existing_data, **trade_data}
            self.trade_state.setdefault('processed_attachments', []) # Add this line
            
    def save(self):
        """Saves the current, complete state of the trade."""
        save_processed_trade(self.trade_state, self.platform)

    def process(self):
        """Main entry point to process a trade's lifecycle."""
        if not self.trade_hash or not self.owner_username:
            logger.error(f"Missing trade_hash or owner_username for trade: {self.trade_state}")
            return

        # Check if the trade has been seen before by looking for our timestamp.
        is_new = 'first_seen_utc' not in self.trade_state
        
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
        send_telegram_alert(self.trade_state, self.platform)
        create_new_trade_embed(self.trade_state, self.platform)
        
        # Add the crucial timestamp to the unified state.
        self.trade_state['first_seen_utc'] = datetime.now(timezone.utc).isoformat()
        
        send_welcome_message(self.trade_state, self.account, self.headers)

        payment_method_slug = self.trade_state.get("payment_method_slug", "").lower()
        if payment_method_slug in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios","domestic-wire-transfer"]:
            chat_url = CHAT_URL_PAXFUL if self.platform == "Paxful" else CHAT_URL_NOONES
            send_payment_details_message(self.trade_hash, payment_method_slug, self.headers, chat_url, self.owner_username)

        self.trade_state['status_history'] = [self.trade_state.get("trade_status")]

    def check_status_change(self):
        """Checks for and handles changes in the trade's status."""
        current_status = self.trade_state.get("trade_status")
        if current_status not in self.trade_state.get('status_history', []):
            logger.info(f"Trade {self.trade_hash} has a new status: '{current_status}'")
            if current_status == 'Successful':
                send_trade_completion_message(self.trade_hash, self.account, self.headers)
            elif current_status == 'Paid':
                send_payment_received_message(self.trade_hash, self.account, self.headers)
                if 'paid_timestamp' not in self.trade_state:
                    self.trade_state['paid_timestamp'] = datetime.now(timezone.utc).timestamp()
            
            self.trade_state.setdefault('status_history', []).append(current_status)

    def check_for_email_confirmation(self):
        """Checks for payment confirmation emails if the trade is marked as Paid."""
        is_paid = self.trade_state.get("trade_status") == 'Paid'
        is_relevant_method = self.trade_state.get("payment_method_slug", "").lower() in ["oxxo", "bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]
        is_pending = not self.trade_state.get('email_verified') and not self.trade_state.get('email_check_timed_out')

        if not (is_paid and is_relevant_method and is_pending):
            return

        paid_timestamp = self.trade_state.get('paid_timestamp')
        if not paid_timestamp: return
            
        elapsed_time = datetime.now(timezone.utc).timestamp() - paid_timestamp
        if elapsed_time < EMAIL_CHECK_DURATION:
            logger.info(f"Trade {self.trade_hash} is Paid. Re-checking for confirmation email...")
            if self.gmail_service and check_for_payment_email(self.gmail_service, self.trade_state, self.platform):
                logger.info(f"PAYMENT VERIFIED via email for trade {self.trade_hash}.")
                send_email_validation_alert(self.trade_hash, success=True)
                create_email_validation_embed(self.trade_hash, success=True)
                self.trade_state['email_verified'] = True
        else:
            logger.warning(f"Email check for trade {self.trade_hash} timed out.")
            send_email_validation_alert(self.trade_hash, success=False)
            create_email_validation_embed(self.trade_hash, success=False)
            self.trade_state['email_check_timed_out'] = True

    def check_chat_and_attachments(self):
            """Fetches chat history and processes any new attachments."""
            attachment_found, _, last_buyer_ts, new_attachments = fetch_trade_chat_messages(
                self.trade_hash, 
                self.account, 
                self.headers, 
                processed_attachments=self.trade_state['processed_attachments']
            )
            
            if last_buyer_ts: self.trade_state['last_buyer_ts'] = last_buyer_ts

            if not new_attachments:
                return

            if not self.trade_state.get('attachment_message_sent'):
                logger.info(f"New attachment found for trade {self.trade_hash}. Processing.")
                send_attachment_message(self.trade_hash, self.account, self.headers)
                self.trade_state['attachment_message_sent'] = True
            
            for attachment in new_attachments:
                path = attachment['path']
                url = attachment['url']
                author = attachment['author']

                send_attachment_alert(self.trade_hash, author, path)
                create_attachment_embed(self.trade_hash, author, path)
                
                logger.info(f"Performing OCR on {path}...")
                text = extract_text_from_image(path)
                found_amount = find_amount_in_text(text, self.trade_state.get("fiat_amount_requested"))
                
                expected = self.trade_state.get("fiat_amount_requested")
                currency = self.trade_state.get("fiat_currency_code")
                send_amount_validation_alert(self.trade_hash, expected, found_amount, currency)
                create_amount_validation_embed(self.trade_hash, expected, found_amount, currency)

                self.trade_state['processed_attachments'].append(url)
            
    def check_for_inactivity(self):
        """Sends a payment reminder if the trade has been inactive for too long."""
        is_active = self.trade_state.get("trade_status", "").startswith('Active')
        if not is_active or self.trade_state.get('reminder_sent'):
            return

        reference_time = None
        if self.trade_state.get('last_buyer_ts'):
            reference_time = datetime.fromtimestamp(self.trade_state['last_buyer_ts'], tz=timezone.utc)
        elif self.trade_state.get("start_date"):
            try:
                reference_time = datetime.fromisoformat(self.trade_state["start_date"]).replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                logger.error(f"Could not parse start_date for trade {self.trade_hash}.")
        
        if reference_time and (datetime.now(timezone.utc) - reference_time).total_seconds() > PAYMENT_REMINDER_DELAY:
            logger.info(f"Sending payment reminder for trade {self.trade_hash} due to inactivity.")
            send_payment_reminder_message(self.trade_hash, self.account, self.headers)
            self.trade_state['reminder_sent'] = True