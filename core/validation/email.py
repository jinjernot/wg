import os.path
import logging
import base64
import re
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from config_messages.email_validation_details import EMAIL_ACCOUNT_DETAILS
from config import GMAIL_CREDENTIALS_DIR

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service(name_identifier):
    """Authenticates with the Gmail API using a specific name identifier."""
    if not name_identifier:
        logger.error("No name identifier provided for Gmail service.")
        return None

    sanitized_name = name_identifier.replace(" ", "_")
    creds = None
    token_file = os.path.join(GMAIL_CREDENTIALS_DIR, f"token_{sanitized_name}.json")
    creds_file = os.path.join(GMAIL_CREDENTIALS_DIR, f"credentials_{sanitized_name}.json")

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Failed to refresh token for {sanitized_name}: {e}")
                creds = None
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

def batch_get_messages(service, message_ids):
    """Fetches multiple messages in a single batch request."""
    if not message_ids:
        return []

    full_messages = []
    # The batch API has a limit of 100 requests per batch.
    for i in range(0, len(message_ids), 100):
        batch = service.new_batch_http_request()
        chunk = message_ids[i:i+100]

        def callback(request_id, response, exception):
            if exception is not None:
                logger.error(f"Error in batch request for id {request_id}: {exception}")
            else:
                full_messages.append(response)

        for msg_id in chunk:
            batch.add(service.users().messages().get(userId='me', id=msg_id['id'], format='metadata'), callback=callback)
        batch.execute()
    return full_messages

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
        amount_tag = soup.find('strong', string=re.compile(r'depósito de efectivo'))
        found_amount = None
        if amount_tag:
            money_pattern = r'\$\s*(\d{1,3}(?:,?\d{3})*\.\d{2})'
            match = re.search(money_pattern, amount_tag.get_text(strip=True))
            if match:
                amount_str = match.group(1).replace(',', '').strip()
                found_amount = float(amount_str)
                logger.info(f"Successfully parsed OXXO amount: {found_amount}")

        name_tag = soup.find('span', string=re.compile(r'Hola,'))
        found_name = None
        if name_tag:
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
        amount_span = soup.find('span', style=lambda v: v and 'font-weight:bold' in v and '18.0pt' in v)
        found_amount = None
        if amount_span:
            amount_match = re.search(r'(\d{1,3}(?:,?\d{3})*\.\d{2})', amount_span.get_text(strip=True))
            if amount_match:
                found_amount = float(amount_match.group(1).replace(',', ''))

        beneficiary_header_td = soup.find('td', string=re.compile(r'Nombre o raz(ó|o)n social del beneficiario'))
        found_name = None
        if beneficiary_header_td and beneficiary_header_td.find_next_sibling('td'):
            found_name = beneficiary_header_td.find_next_sibling('td').get_text(strip=True)

        logger.info(f"Parsed Scotiabank details - Amount: {found_amount}, Name: {found_name}")
        return found_amount, found_name
    except Exception as e:
        logger.error(f"Error parsing Scotiabank email: {e}")
        return None, None

def extract_banco_azteca_details(html_body):
    """Parses the Banco Azteca HTML email to extract payment amount and recipient name."""
    try:
        soup = BeautifulSoup(html_body, 'html.parser')
        
        # --- Find Amount ---
        amount_tag = soup.find('b', string=re.compile(r'\$\s*[\d,]+\.?\d*'))
        found_amount = None
        if amount_tag:
            amount_text = amount_tag.get_text(strip=True)
            # Match numbers with commas (e.g., $6,300 or $6,300.00)
            amount_match = re.search(r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', amount_text)
            if amount_match:
                amount_str = amount_match.group(1).replace(',', '')
                found_amount = float(amount_str)
                logger.info(f"Successfully parsed Banco Azteca amount: {found_amount}")

        # --- Find Name ---
        found_name = None
        
        # Method 1: Search through all TDs for one containing "Beneficiario:"
        all_tds = soup.find_all('td')
        for td in all_tds:
            td_text = td.get_text(strip=True)
            if 'Beneficiario:' in td_text:
                # Look for font tags with size="4" which typically contains the name
                font_tags = td.find_all('font', size="4")
                for font in font_tags:
                    font_text = font.get_text(strip=True)
                    # Remove common disclaimer patterns
                    name_clean = re.sub(r'\(Dato no verificado.*?\)', '', font_text, flags=re.IGNORECASE)
                    name_clean = name_clean.strip()
                    # Check if this looks like a name (has letters and is not too short)
                    if name_clean and len(name_clean) > 5 and re.search(r'[A-Z]', name_clean):
                        found_name = name_clean.upper()
                        logger.info(f"Successfully parsed Banco Azteca recipient name: {found_name}")
                        break
                if found_name:
                    break
        
        # Method 2: Fallback - use regex on plain text
        if not found_name:
            full_text = soup.get_text()
            match = re.search(r'Beneficiario:\s*([A-Z][A-Z\s]+?)(?:\(|Concepto:|$)', full_text, re.MULTILINE)
            if match:
                found_name = match.group(1).strip()
                logger.info(f"Successfully parsed Banco Azteca recipient name (fallback): {found_name}")

        return found_amount, found_name
    except Exception as e:
        logger.error(f"An error occurred while parsing the Banco Azteca email: {e}")
        return None, None

def check_for_payment_email(service, trade_details, platform, credential_identifier):
    """Searches for, saves, and validates a payment confirmation email."""
    if not service:
        return False, None

    payment_method_slug = trade_details.get("payment_method_slug", "").lower()
    account_config = EMAIL_ACCOUNT_DETAILS.get(credential_identifier)
    if not account_config:
        logger.warning(f"No email validation config found for '{credential_identifier}'. Skipping.")
        return False, None

    # Define candidates to check: (validator_type, query_template, name_key)
    candidates = []
    
    if payment_method_slug == "oxxo":
        candidates.append((
            "oxxo", 
            'from:noreply@spinbyoxxo.com.mx subject:("Recibiste un depósito de efectivo;(OXXO)")', 
            "name_oxxo"
        ))
    elif payment_method_slug in ["bank-transfer", "spei-sistema-de-pagos-electronicos-interbancarios", "domestic-wire-transfer"]:
        # Generic Bank Transfer - Check BOTH Scotiabank and Banco Azteca
        # Priority 1: Scotiabank
        candidates.append((
            "scotiabank", 
            'from:avisosScotiabank@scotiabank.mx subject:("Aviso Scotiabank - Envio de Transferencia SPEI")', 
            "name_scotiabank"
        ))
        # Priority 2: Banco Azteca
        candidates.append((
            "banco_azteca", 
            'from:notificaciones@bazdigital.com subject:("Notificación Banco Azteca")', 
            "name_banco_azteca"
        ))
    elif payment_method_slug == "banco-azteca":
        candidates.append((
            "banco_azteca", 
            'from:notificaciones@bazdigital.com subject:("Notificación Banco Azteca")', 
            "name_banco_azteca"
        ))
    else:
        return False, None

    # Iterate through candidates until a match is found
    for validator, query_base, name_key in candidates:
        expected_name = account_config.get(name_key)
        
        if not expected_name:
            logger.debug(f"Skipping validator {validator} for {credential_identifier}: Missing {name_key}")
            continue

        try:
            # Get paid timestamp from trade_details to search from when payment was marked
            paid_timestamp = trade_details.get('paid_timestamp')
            if paid_timestamp:
                # Convert from Unix timestamp to datetime, timezone aware
                from datetime import timezone as tz
                search_start_time = datetime.fromtimestamp(paid_timestamp, tz=tz.utc)
                # Gmail search uses UTC time, so we need to format in UTC
                after_time = search_start_time.strftime('%Y/%m/%d %H:%M:%S')
            else:
                # Fallback: search last 3 hours if no paid_timestamp
                after_time = (datetime.utcnow() - timedelta(hours=3)).strftime('%Y/%m/%d %H:%M:%S')
            
            query = f"{query_base} after:{after_time}"
            
            logger.info(f"Searching ({validator}) with query: {query}")
            logger.info(f"Expected amount: {trade_details.get('fiat_amount_requested')}, Expected name: {expected_name}")

            # Increased maxResults to 50 to search more emails
            result = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
            message_ids = result.get("messages", [])
            
            # --- Save search summary immediately ---
            search_log_dir = os.path.join("email_logs", "_search_logs")
            if not os.path.exists(search_log_dir):
                os.makedirs(search_log_dir)
            
            search_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            search_log_file = os.path.join(search_log_dir, f"{search_timestamp}_{trade_details['trade_hash']}_{validator}_search.json")
            
            search_summary = {
                "timestamp": search_timestamp,
                "trade_hash": trade_details['trade_hash'],
                "validator": validator,
                "query": query,
                "expected_amount": float(trade_details.get("fiat_amount_requested", 0)),
                "expected_name": expected_name,
                "payment_method": payment_method_slug,
                "credential_identifier": credential_identifier,
                "emails_found": len(message_ids),
                "message_ids": [m.get('id') for m in message_ids] if message_ids else []
            }
            
            with open(search_log_file, "w", encoding="utf-8") as f:
                json.dump(search_summary, f, indent=2)
            logger.info(f"📝 Saved search summary to: {search_log_file}")
            
            logger.info(f"[EMAIL SEARCH DEBUG] Query: {query}")
            logger.info(f"[EMAIL SEARCH DEBUG] Found {len(message_ids)} emails matching query")
            
            if not message_ids:
                logger.warning(f"No emails found for {validator} matching query for trade {trade_details.get('trade_hash')}")
                continue # Try next candidate
            
            logger.info(f"Found {len(message_ids)} potential emails for {validator}")

            full_messages = batch_get_messages(service, message_ids)
            
            logger.info(f"[EMAIL SEARCH DEBUG] Successfully fetched {len(full_messages)} full message(s)")

            for idx, msg in enumerate(full_messages, 1):
                # Log email subject for debugging
                subject = ""
                for header in msg.get('payload', {}).get('headers', []):
                    if header['name'].lower() == 'subject':
                        subject = header['value']
                        break
                logger.info(f"[EMAIL {idx}/{len(full_messages)}] Subject: {subject}")
                
                email_body = get_email_body(msg['payload'])
                if not email_body:
                    logger.warning(f"[EMAIL {idx}] Could not extract email body, skipping")
                    continue

                logger.info(f"[EMAIL {idx}] Successfully extracted email body ({len(email_body)} chars)")

                expected_amount = float(trade_details.get("fiat_amount_requested", 0))
                
                found_amount, found_name = None, None
                if validator == "scotiabank":
                    found_amount, found_name = extract_scotiabank_details(email_body)
                elif validator == "oxxo":
                    found_amount, found_name = extract_oxxo_details(email_body)
                elif validator == "banco_azteca":
                    found_amount, found_name = extract_banco_azteca_details(email_body)

                # Enhanced logging for debugging
                logger.info(f"[EMAIL {idx}] Extracted from email ({validator}) - Amount: {found_amount}, Name: {found_name}")
                logger.info(f"[EMAIL {idx}] Expected values - Amount: {expected_amount}, Name: {expected_name}")

                # --- Save Email Log (ENHANCED FOR DEBUGGING) ---
                log_dir = os.path.join("email_logs", validator, trade_details['trade_hash'])
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Save HTML body
                html_filename = f"{timestamp}_email{idx}_body.html"
                html_path = os.path.join(log_dir, html_filename)
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(email_body)
                logger.info(f"[EMAIL {idx}] Saved email HTML to: {html_path}")
                
                # Save raw metadata as JSON for full debugging
                metadata_filename = f"{timestamp}_email{idx}_metadata.json"
                metadata_path = os.path.join(log_dir, metadata_filename)
                
                # Extract all headers
                headers_dict = {}
                for header in msg.get('payload', {}).get('headers', []):
                    headers_dict[header['name']] = header['value']
                
                metadata = {
                    "trade_hash": trade_details['trade_hash'],
                    "validator": validator,
                    "search_query": query,
                    "email_subject": subject,
                    "headers": headers_dict,
                    "message_id": msg.get('id'),
                    "internal_date": msg.get('internalDate'),
                    "found_amount": found_amount,
                    "found_name": found_name,
                    "expected_amount": expected_amount,
                    "expected_name": expected_name,
                    "body_length": len(email_body)
                }
                
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)
                logger.info(f"[EMAIL {idx}] Saved email metadata to: {metadata_path}")

                # --- Validate ---
                is_amount_match = False
                if found_amount is not None:
                    is_amount_match = abs(found_amount - expected_amount) < 1.0

                is_name_match = False
                if found_name and expected_name:
                    # Normalize names for comparison
                    def normalize(s):
                        return re.sub(r'[^A-Z]', '', str(s).upper())
                    
                    norm_found = normalize(found_name)
                    norm_expected = normalize(expected_name)
                    
                    # Check for exact match or if one contains the other (to handle partial names)
                    if norm_found == norm_expected or norm_expected in norm_found or norm_found in norm_expected:
                        is_name_match = True
                    
                    # Special case for "EDUARDO RAMIREZ" vs "RAMIREZ LAUREANO EDUARDO"
                    # Split into words and check if significant words match
                    if not is_name_match:
                        found_words = set(normalize(w) for w in found_name.split() if len(w) > 2)
                        expected_words = set(normalize(w) for w in expected_name.split() if len(w) > 2)
                        common_words = found_words.intersection(expected_words)
                        # If at least 2 significant words match, consider it a match
                        if len(common_words) >= 2:
                            is_name_match = True
                            logger.info(f"Fuzzy name match successful: {found_words} vs {expected_words}")

                if is_amount_match and is_name_match:
                    logger.info(f"✅ SUCCESS: Amount and Name in email match for trade {trade_details['trade_hash']}.")
                    return True, {"validator": validator, "found_amount": found_amount, "found_name": found_name, "expected_amount": expected_amount, "expected_name": expected_name}
                else:
                    # Detailed failure logging
                    if not is_amount_match:
                        logger.warning(f"❌ Amount mismatch: Expected {expected_amount}, Found {found_amount}")
                    if not is_name_match:
                        logger.warning(f"❌ Name mismatch: Expected '{expected_name}', Found '{found_name}'")
                    logger.warning(
                        f"Validation failed for trade {trade_details['trade_hash']}: "
                        f"Amount Match: {is_amount_match}, Name Match: {is_name_match}"
                    )

        except Exception as e:
            logger.error(f"Error checking {validator} email: {e}")
            continue

    # If we went through all candidates and found nothing
    return False, None