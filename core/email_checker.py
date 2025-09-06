import os.path
import logging
import base64
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    """
    Authenticates with the Gmail API and returns a service object.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.error(f"Failed to refresh token: {e}")
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    try:
        service = build("gmail", "v1", credentials=creds)
        logging.info("Successfully connected to Gmail API.")
        return service
    except HttpError as error:
        logging.error(f"An error occurred connecting to Gmail API: {error}")
        return None

# --- THIS FUNCTION HAS BEEN UPDATED TO BE MORE ROBUST ---
def get_email_body(message_payload):
    """
    Recursively searches for the plain text or HTML part of an email and decodes it.
    Prefers plain text, but falls back to HTML.
    """
    plain_text_body = None
    html_body = None

    # Use a stack for an iterative search to handle nested parts
    parts_to_check = [message_payload]

    while parts_to_check:
        part = parts_to_check.pop()
        mime_type = part.get('mimeType', '')
        body_data = part.get('body', {}).get('data')

        if not body_data:
            # If there's no data in this part, check its sub-parts
            if 'parts' in part:
                parts_to_check.extend(part['parts'])
            continue

        if mime_type == 'text/plain':
            plain_text_body = base64.urlsafe_b64decode(body_data).decode('utf-8')
            # Found the best option (plain text), so we can stop searching.
            break
        elif mime_type == 'text/html':
            # Store HTML as a fallback option in case plain text isn't found.
            html_body = base64.urlsafe_b64decode(body_data).decode('utf-8')

    # Prioritize returning the plain text body, but use HTML if it's all we have.
    return plain_text_body or html_body or ""


def find_amount_in_email_body(body):
    """
    Uses regex to find the monetary value in the Scotiabank email body.
    """
    money_pattern = r'\$\s*(\d{1,3}(?:,\d{3})*\.\d{2})'
    match = re.search(money_pattern, body)
    if match:
        amount_str = match.group(1).replace(',', '')
        return float(amount_str)
    return None


def check_for_payment_email(service, trade_details):
    """
    Searches for a payment confirmation email, parses the body for the amount,
    and returns True if it matches the trade amount.
    """
    if not service:
        return False
        
    try:
        query = 'from:avisosScotiabank@scotiabank.mx subject:("Aviso Scotiabank - Envio de Transferencia SPEI") newer_than:1d'
        
        logging.info(f"Searching Gmail with query: {query}")
        
        result = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
        messages = result.get("messages", [])

        if not messages:
            logging.info("No matching Scotiabank emails found.")
            return False

        expected_amount = float(trade_details.get('fiat_amount_requested', '0.00'))

        for message_summary in messages:
            msg_id = message_summary['id']
            full_message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            
            email_body = get_email_body(full_message['payload'])
            
            if not email_body:
                logging.warning(f"Could not extract body from email ID: {msg_id}")
                continue

            found_amount = find_amount_in_email_body(email_body)
            
            if found_amount is not None:
                logging.info(f"Found amount in email: {found_amount}. Expected: {expected_amount}")
                if found_amount == expected_amount:
                    logging.info(f"SUCCESS: Amount in email matches trade {trade_details['trade_hash']}.")
                    return True
            else:
                logging.warning(f"Found a matching email but could not find an amount in the body. Email ID: {msg_id}")

        logging.info("Found Scotiabank emails, but none matched the expected trade amount.")
        return False

    except HttpError as error:
        logging.error(f"An error occurred while searching emails: {error}")
        return False