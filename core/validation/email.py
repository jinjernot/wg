# core/validation/email.py
import os.path
import logging
import base64
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service(name_identifier):
    """Authenticates with the Gmail API using a specific name identifier."""
    if not name_identifier:
        logger.error("No name identifier provided for Gmail service.")
        return None

    # Sanitize the name to create a valid filename (e.g., "Roberto Quintero" -> "Roberto_Quintero")
    sanitized_name = name_identifier.replace(" ", "_")

    creds = None
    token_file = f"token_{sanitized_name}.json"
    creds_file = f"credentials_{sanitized_name}.json"

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh token for {sanitized_name}: {e}")
                creds = None # Force re-authentication
        
        if not creds:
            if os.path.exists(creds_file):
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                logger.error(f"Credentials file not found for '{sanitized_name}': {creds_file}")
                return None
        
        with open(token_file, "w") as token:
            token.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        logger.info(f"Successfully connected to Gmail API for '{sanitized_name}'.")
        return service
    except HttpError as error:
        logger.error(f"An error occurred connecting to Gmail API for '{sanitized_name}': {error}")
        return None

def get_email_body(message_payload):
    """Recursively searches for and decodes the HTML part of an email."""
    html_body = None
    plain_text_body = None
    parts_to_check = [message_payload]
    while parts_to_check:
        part = parts_to_check.pop()
        mime_type = part.get('mimeType', '')
        body_data = part.get('body', {}).get('data')
        if not body_data:
            if 'parts' in part:
                parts_to_check.extend(part['parts'])
            continue
        if mime_type == 'text/html':
            html_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
            break
        elif mime_type == 'text/plain':
            plain_text_body = base64.urlsafe_b64decode(body_data).decode('utf-8')

    return html_body or plain_text_body or ""

def find_amount_in_email_body(body):
    """Generic fallback function to find amount using regex."""
    money_pattern = r'\$\s*(\d{1,3}(?:,?\d{3})*\.\d{2})'
    match = re.search(money_pattern, str(body))
    if match:
        amount_str = match.group(1).replace(',', '').strip()
        return float(amount_str)
    return None

def extract_scotiabank_details(html_body):
    """Parses the Scotiabank HTML email to extract amount and concept."""
    try:
        soup = BeautifulSoup(html_body, 'html.parser')
        amount_span = soup.find('span', style=lambda v: v and 'font-weight:bold' in v and '18.0pt' in v)
        if not amount_span:
            return None, None
        amount_match = re.search(r'(\d{1,3}(?:,?\d{3})*\.\d{2})', amount_span.get_text(strip=True))
        found_amount = float(amount_match.group(1).replace(',', '')) if amount_match else None
        
        concept_header_td = soup.find('td', string=lambda text: text and 'Concepto' in text.strip())
        found_concept = None
        if concept_header_td and concept_header_td.find_next_sibling('td'):
            found_concept = concept_header_td.find_next_sibling('td').get_text(strip=True)

        return found_amount, found_concept
    except Exception as e:
        logger.error(f"Error parsing Scotiabank email: {e}")
        return None, None

def check_for_payment_email(service, trade_details, platform):
    """Searches for, saves, and validates a payment confirmation email."""
    if not service: return False

    payment_method_slug = trade_details.get("payment_method_slug", "").lower()
    query, log_folder, validator = None, None, None

    if payment_method_slug == "oxxo":
        query = 'from:noreply@spinbyoxxo.com.mx subject:("Recibiste un depósito de efectivo; (OXXO)")'
        log_folder, validator = "oxxo", "generic"
    elif payment_method_slug in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]:
        query = 'from:avisosScotiabank@scotiabank.mx subject:("Aviso Scotiabank - Envio de Transferencia SPEI")'
        log_folder, validator = "bank-transfer", "scotiabank"
    else:
        return False

    try:
        result = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
        messages = result.get("messages", [])
        if not messages: return False

        expected_amount = float(trade_details.get('fiat_amount_requested', '0.00'))
        owner_username = trade_details.get("owner_username", "unknown_user")

        for msg_summary in messages:
            full_message = service.users().messages().get(userId='me', id=msg_summary['id'], format='full').execute()
            email_body = get_email_body(full_message['payload'])
            if not email_body: continue

            found_amount = None
            if validator == "scotiabank":
                found_amount, _ = extract_scotiabank_details(email_body)
            else: # Generic validator
                found_amount = find_amount_in_email_body(email_body)
            
            account_folder_name = f"{owner_username}_{platform}"
            log_directory = os.path.join("data", "logs", log_folder, account_folder_name)
            os.makedirs(log_directory, exist_ok=True)
            
            sanitized_hash = "".join(c for c in trade_details['trade_hash'] if c.isalnum())
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            amount_str = f"_{found_amount:.2f}_" if found_amount is not None else "_"
            filename = os.path.join(log_directory, f"{sanitized_hash}{amount_str}{timestamp}.html")

            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(email_body)
                logger.info(f"Saved email body for trade {trade_details['trade_hash']} to {filename}")
            except Exception as e:
                logger.error(f"Could not save email body: {e}")

            if found_amount and found_amount == expected_amount:
                logger.info(f"✅ SUCCESS: Amount in email matches trade {trade_details['trade_hash']}.")
                return True

        logger.info(f"Found emails for trade {trade_details['trade_hash']}, but none matched expected amount.")
        return False

    except HttpError as error:
        logger.error(f"An error occurred while searching emails: {error}")
        return False