# core/email_checker.py
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
from bs4 import BeautifulSoup # <-- Import BeautifulSoup

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    """Authenticates with the Gmail API and returns a service object."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    try:
        service = build("gmail", "v1", credentials=creds)
        logger.info("Successfully connected to Gmail API.")
        return service
    except HttpError as error:
        logger.error(f"An error occurred connecting to Gmail API: {error}")
        return None

def get_email_body(message_payload):
    """
    Recursively searches for the HTML or plain text part of an email and decodes it.
    It prioritizes HTML.
    """
    plain_text_body = None
    html_body = None
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
    money_pattern = r'\$\s*(\d{1,3}(?:,\d{3})*\.\d{2})'
    match = re.search(money_pattern, body)
    if match:
        amount_str = match.group(1).replace(',', '').strip()
        return float(amount_str)
    return None

def extract_scotiabank_details(html_body):
    """
    Parses the Scotiabank HTML email to extract amount and concept.
    Returns: (amount, concept) or (None, None) if not found.
    """
    try:
        soup = BeautifulSoup(html_body, 'html.parser')
        
        # --- 1. Find the Amount ---
        # The amount is in a span with a specific style.
        amount_span = soup.find('span', style=lambda value: value and 'font-weight:bold' in value and '18.0pt' in value)
        if not amount_span:
            logger.warning("Could not find the specific amount span in Scotiabank email.")
            return None, None
            
        amount_text = amount_span.get_text(strip=True)
        # Use regex to be safe and extract only the number
        amount_match = re.search(r'(\d{1,3}(?:,?\d{3})*\.\d{2})', amount_text)
        found_amount = float(amount_match.group(1).replace(',', '')) if amount_match else None

        # --- 2. Find the Concept ---
        # The concept is in the table. We find the cell with "Concepto" and get the next sibling cell.
        concept_header_td = soup.find('td', string=lambda text: text and 'Concepto' in text.strip())
        found_concept = None
        if concept_header_td and concept_header_td.find_next_sibling('td'):
            found_concept = concept_header_td.find_next_sibling('td').get_text(strip=True)
        else:
            logger.warning("Could not find the concept <td> in Scotiabank email.")

        logger.info(f"Scotiabank Parser | Amount: {found_amount}, Concept: '{found_concept}'")
        return found_amount, found_concept

    except Exception as e:
        logger.error(f"Error parsing Scotiabank email template: {e}")
        return None, None


def check_for_payment_email(service, trade_details):
    """
    Searches for a payment confirmation email, validates it, and returns True if it matches.
    """
    if not service:
        return False

    payment_method_slug = trade_details.get("payment_method_slug", "").lower()
    query, log_folder, validator = None, None, None

    if payment_method_slug == "oxxo":
        query = 'from:noreply@spinbyoxxo.com.mx subject:("Recibiste un depósito de efectivo; (OXXO)") newer_than:1d'
        log_folder = "oxxo"
        validator = "generic" # Use the generic regex finder
    elif payment_method_slug in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]:
        query = 'from:avisosScotiabank@scotiabank.mx subject:("Aviso Scotiabank - Envio de Transferencia SPEI") newer_than:1d'
        log_folder = "bank-transfer"
        validator = "scotiabank" # Use the new specific parser
    else:
        logger.info(f"No email checking configuration for payment method: {payment_method_slug}")
        return False
    
    try:
        logger.info(f"Searching Gmail with query: {query}")
        result = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
        messages = result.get("messages", [])

        if not messages:
            logger.info(f"No matching emails found for trade {trade_details['trade_hash']}.")
            return False

        expected_amount = float(trade_details.get('fiat_amount_requested', '0.00'))

        for message_summary in messages:
            msg_id = message_summary['id']
            full_message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            email_body = get_email_body(full_message['payload'])
            
            if not email_body:
                logger.warning(f"Could not extract body from email ID: {msg_id}")
                continue

            # Save the email log regardless of validation outcome
            if log_folder:
                # (The code for saving logs remains the same)
                log_directory = os.path.join("data", "logs", log_folder)
                if not os.path.exists(log_directory):
                    os.makedirs(log_directory)
                sanitized_trade_hash = "".join(c for c in trade_details['trade_hash'] if c.isalnum())
                sender, subject = "UnknownSender", "NoSubject"
                for header in full_message['payload']['headers']:
                    if header['name'] == 'From': sender = header['value']
                    if header['name'] == 'Subject': subject = header['value']
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(log_directory, f"{sanitized_trade_hash}_{timestamp}.html")
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(f"\n")
                        f.write(f"\n")
                        f.write(email_body)
                    logger.info(f"Saved email body for trade {trade_details['trade_hash']} to {filename}")
                except Exception as e:
                    logger.error(f"Could not save email body for trade {trade_details['trade_hash']}: {e}")

            # --- VALIDATION LOGIC ---
            found_amount = None
            if validator == "scotiabank":
                found_amount, found_concept = extract_scotiabank_details(email_body)
                # Future logic for concept validation would go here
            else: # Generic validator for OXXO and others
                found_amount = find_amount_in_email_body(email_body)
            
            if found_amount is not None:
                logger.info(f"Found amount in email: {found_amount}. Expected: {expected_amount}")
                if found_amount == expected_amount:
                    logger.info(f"✅ SUCCESS: Amount in email matches trade {trade_details['trade_hash']}.")
                    return True
            else:
                logger.warning(f"Found a matching email but could not extract an amount from the body. Email ID: {msg_id}")

        logger.info(f"Found emails for trade {trade_details['trade_hash']}, but none matched the expected amount.")
        return False

    except HttpError as error:
        logger.error(f"An error occurred while searching emails: {error}")
        return False