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
from config_messages.email_validation_details import EMAIL_ACCOUNT_DETAILS

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

def extract_oxxo_details(html_body):
    """Parses the OXXO HTML email to extract payment amount and recipient name."""
    try:
        soup = BeautifulSoup(html_body, 'html.parser')
        
        # --- Extract Amount ---
        amount_tag = soup.find('strong', string=re.compile(r'depósito de efectivo'))
        found_amount = None
        if amount_tag:
            money_pattern = r'\$\s*(\d{1,3}(?:,?\d{3})*\.\d{2})'
            match = re.search(money_pattern, amount_tag.get_text(strip=True))
            if match:
                amount_str = match.group(1).replace(',', '').strip()
                found_amount = float(amount_str)
                logger.info(f"Successfully parsed OXXO amount: {found_amount}")

        # --- Extract Name ---
        name_tag = soup.find('span', string=re.compile(r'Hola,'))
        found_name = None
        if name_tag:
            # Extract text, remove "Hola,", trailing period, and trim whitespace
            name_text = name_tag.get_text(strip=True)
            found_name = name_text.replace("Hola,", "").replace(".", "").strip()
            logger.info(f"Successfully parsed OXXO recipient name: {found_name}")

        return found_amount, found_name
        
    except Exception as e:
        logger.error(f"An error occurred while parsing the OXXO email: {e}")
        return None, None


def extract_scotiabank_details(html_body):
    """Parses the Scotiabank HTML email to extract amount and beneficiary name."""
    try:
        soup = BeautifulSoup(html_body, 'html.parser')

        # --- Extract Amount ---
        amount_span = soup.find('span', style=lambda v: v and 'font-weight:bold' in v and '18.0pt' in v)
        found_amount = None
        if amount_span:
            amount_match = re.search(r'(\d{1,3}(?:,?\d{3})*\.\d{2})', amount_span.get_text(strip=True))
            if amount_match:
                found_amount = float(amount_match.group(1).replace(',', ''))

        # --- Extract Beneficiary Name ---
        beneficiary_header_td = soup.find('td', string=re.compile(r'Nombre o raz(ó|o)n social del beneficiario'))
        found_name = None
        if beneficiary_header_td and beneficiary_header_td.find_next_sibling('td'):
            found_name = beneficiary_header_td.find_next_sibling('td').get_text(strip=True)

        logger.info(f"Parsed Scotiabank details - Amount: {found_amount}, Name: {found_name}")
        return found_amount, found_name

    except Exception as e:
        logger.error(f"Error parsing Scotiabank email: {e}")
        return None, None

def check_for_payment_email(service, trade_details, platform, credential_identifier):
    """Searches for, saves, and validates a payment confirmation email."""
    if not service: return False

    payment_method_slug = trade_details.get("payment_method_slug", "").lower()
    
    # Get expected details from the config file
    account_config = EMAIL_ACCOUNT_DETAILS.get(credential_identifier)
    if not account_config:
        logger.warning(f"No email validation config found for '{credential_identifier}'. Skipping.")
        return False

    query, log_folder, validator, expected_name = None, None, None, None

    if payment_method_slug == "oxxo":
        query = 'from:noreply@spinbyoxxo.com.mx subject:("Recibiste un depósito de efectivo; (OXXO)")'
        log_folder, validator = "oxxo", "oxxo"
        expected_name = account_config.get("name_oxxo")
    elif payment_method_slug in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]:
        query = 'from:avisosScotiabank@scotiabank.mx subject:("Aviso Scotiabank - Envio de Transferencia SPEI")'
        log_folder, validator = "bank-transfer", "scotiabank"
        expected_name = account_config.get("name_scotiabank")
    else:
        return False

    if not expected_name:
        logger.warning(f"Missing expected name in config for '{credential_identifier}' and method '{payment_method_slug}'.")
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

            found_amount, found_name = None, None
            if validator == "scotiabank":
                found_amount, found_name = extract_scotiabank_details(email_body)
            elif validator == "oxxo":
                found_amount, found_name = extract_oxxo_details(email_body)
            
            # --- Save Email Log ---
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

            # --- Validation Check ---
            is_amount_match = found_amount is not None and found_amount == expected_amount
            is_name_match = found_name is not None and found_name == expected_name

            if is_amount_match and is_name_match:
                logger.info(f"✅ SUCCESS: Amount and Name in email match for trade {trade_details['trade_hash']}.")
                return True
            else:
                logger.warning(
                    f"Validation failed for trade {trade_details['trade_hash']}: "
                    f"Amount Match: {is_amount_match} (Expected: {expected_amount}, Found: {found_amount}), "
                    f"Name Match: {is_name_match} (Expected: '{expected_name}', Found: '{found_name}')"
                )

        logger.info(f"Found emails for trade {trade_details['trade_hash']}, but none passed validation.")
        return False

    except HttpError as error:
        logger.error(f"An error occurred while searching emails: {error}")
        return False
