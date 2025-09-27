import pytesseract
import logging
import json
import cv2
import re
import os

from datetime import datetime
from PIL import Image

from config import OCR_LOG_PATH

logger = logging.getLogger(__name__)

os.makedirs(OCR_LOG_PATH, exist_ok=True)

def load_ocr_templates():
    """Loads OCR keyword templates from a JSON file."""
    try:
        templates_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ocr_templates.json')
        with open(templates_path, 'r', encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Could not load or parse ocr_templates.json from the data folder: {e}")
        return {"bank_templates": {}, "generic_amount_keywords": []}

OCR_TEMPLATES = load_ocr_templates()

try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except FileNotFoundError:
    logger.warning("Tesseract executable not found. Update the path in ocr.py if needed.")

def save_ocr_text(trade_hash, owner_username, text, identified_bank=None):
    """Saves the extracted OCR text to a structured folder."""
    try:
        now = datetime.now()
        date_folder = now.strftime("%Y-%m-%d")
        
        # Create the new directory structure
        log_directory = os.path.join(OCR_LOG_PATH, owner_username, date_folder)
        os.makedirs(log_directory, exist_ok=True)
        
        timestamp = now.strftime("%H%M%S")
        bank_suffix = f"_{identified_bank}" if identified_bank else ""
        filename = f"{trade_hash}{bank_suffix}_{timestamp}.txt"
        filepath = os.path.join(log_directory, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Saved OCR text for trade {trade_hash} to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save OCR text for trade {trade_hash}: {e}")

def preprocess_image_for_ocr(image_path):
    """Applies pre-processing techniques to an image to improve OCR accuracy."""
    try:
        img = cv2.imread(image_path)
        if img is None: return None
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        denoised = cv2.medianBlur(binary, 3)
        return denoised
    except Exception as e:
        logger.error(f"An error occurred during image pre-processing for {image_path}: {e}")
        return None

def extract_text_from_image(image_path):
    """Extracts text from an image using Tesseract OCR."""
    try:
        preprocessed_image = preprocess_image_for_ocr(image_path)
        img_to_process = preprocessed_image if preprocessed_image is not None else Image.open(image_path)
        text = pytesseract.image_to_string(img_to_process, config=r'--oem 3 --psm 6')
        logger.info(f"Successfully extracted text from {image_path}")
        return text
    except Exception as e:
        logger.error(f"Could not read or process image {image_path}: {e}")
        return ""

def identify_bank_from_text(text):
    """Identifies the source bank using a detailed fingerprinting method."""
    if not text: return None
    text_lower = text.lower()
    bank_templates = OCR_TEMPLATES.get("bank_templates", {})
    
    # --- Fingerprint Identification ---
    best_match_bank = None
    highest_score = 0

    for bank_name, template in bank_templates.items():
        fingerprint = template.get("fingerprint", [])
        if not fingerprint:
            continue

        score = 0
        for phrase in fingerprint:
            if phrase.lower() in text_lower:
                score += 1
        
        normalized_score = score / len(fingerprint) if len(fingerprint) > 0 else 0

        if normalized_score > highest_score:
            highest_score = normalized_score
            best_match_bank = bank_name

    if highest_score > 0.5:
        logger.info(f"Identified bank via fingerprint: {best_match_bank} with score {highest_score:.2f}")
        return best_match_bank

    logger.warning("Fingerprint identification failed. Falling back to keyword search.")
    
    found_banks = set()
    for bank_name, template in bank_templates.items():
        if any(keyword.lower() in text_lower for keyword in template.get("keywords", [])):
            found_banks.add(bank_name)

    if not found_banks:
        logger.warning("No known bank keywords found in the text.")
        return None
    
    if len(found_banks) == 1:
        source_bank = found_banks.pop()
        logger.info(f"Identified the only available bank as SOURCE: {source_bank}")
        return source_bank

    return list(found_banks)[0] if found_banks else None


def find_details_with_parsers(text, identified_bank):
    """Attempts to extract details (amount, name) using bank-specific regex patterns."""
    bank_template = OCR_TEMPLATES.get("bank_templates", {}).get(identified_bank, {})
    parsers = bank_template.get("parsers", {})
    found_details = {"amount": None, "name": None}

    if not parsers:
        return found_details

    amount_parser = parsers.get("amount", {})
    amount_pattern = amount_parser.get("pattern")
    if amount_pattern:
        match = re.search(amount_pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                amount_str = match.group(1).replace(',', '').strip()
                found_details["amount"] = float(amount_str)
                logger.info(f"[{identified_bank} Parser] Found amount using pattern: {found_details['amount']}")
            except (ValueError, IndexError):
                logger.warning(f"[{identified_bank} Parser] Pattern matched but failed to extract amount from groups: {match.groups()}")

    name_parser = parsers.get("name", {})
    name_pattern = name_parser.get("pattern")
    if name_pattern:
        match = re.search(name_pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                found_details["name"] = match.group(1).strip()
                logger.info(f"[{identified_bank} Parser] Found name using pattern: '{found_details['name']}'")
            except IndexError:
                logger.warning(f"[{identified_bank} Parser] Pattern matched but failed to extract name from groups: {match.groups()}")

    return found_details

def find_amount_in_text(text, trade_amount):
    """Finds amount, prioritizing bank-specific parsers then falling back to generic search."""
    if not text: return None
    identified_bank = identify_bank_from_text(text)
    
    if identified_bank:
        parsed_details = find_details_with_parsers(text, identified_bank)
        parsed_amount = parsed_details.get("amount")
        if parsed_amount is not None:
            if float(parsed_amount) != float(trade_amount):
                 logger.warning(f"Amount mismatch. Expected: {trade_amount}, Parser found: {parsed_amount}")
            return parsed_amount
    
    logger.info("Parser failed. Falling back to generic amount search.")
    priority_keywords = [k.lower() for k in OCR_TEMPLATES.get("generic_amount_keywords", [])]
    if identified_bank:
        bank_template = OCR_TEMPLATES.get("bank_templates", {}).get(identified_bank, {})
        kw = bank_template.get("parsers", {}).get("amount", {}).get("line_keyword")
        if kw: priority_keywords.insert(0, kw.lower())

    money_pattern = r'\$\s*(\d{1,3}(?:,?\d{3})*\.\d{2})\b'
    all_amounts, priority_amounts = [], []

    for line in text.lower().split('\n'):
        found = re.findall(money_pattern, line)
        if not found: continue
        is_priority = any(keyword in line for keyword in priority_keywords)
        for amount_str in found:
            amount = float(amount_str.replace(',', ''))
            all_amounts.append(amount)
            if is_priority: priority_amounts.append(amount)

    expected_amount = float(trade_amount)
    for amount in priority_amounts:
        if amount == expected_amount:
            logger.info(f"SUCCESS (Fallback): Found matching priority amount: {amount}")
            return amount
    for amount in all_amounts:
        if amount == expected_amount:
            logger.info(f"SUCCESS (Fallback): Found matching amount: {amount}")
            return amount
            
    logger.warning(f"Amount mismatch (Fallback). Expected: {expected_amount}, Found: {all_amounts}")
    return max(all_amounts) if all_amounts else None

def find_name_in_text(text, name_keywords):
    """Finds name, prioritizing bank-specific parsers then falling back to keyword search."""
    if not text or not name_keywords: return None
    identified_bank = identify_bank_from_text(text)
    
    if identified_bank:
        parsed_details = find_details_with_parsers(text, identified_bank)
        parsed_name = parsed_details.get("name")
        if parsed_name:
            for keyword in name_keywords:
                if keyword.lower() in parsed_name.lower():
                    logger.info(f"SUCCESS: Parsed name '{parsed_name}' contains expected keyword '{keyword}'.")
                    return parsed_name
            logger.warning(f"Parsed name '{parsed_name}' did not contain expected keywords: {name_keywords}")
    
    logger.info("Parser failed. Falling back to generic name keyword search.")
    for keyword in name_keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
            logger.info(f"SUCCESS (Fallback): Found name keyword '{keyword}'.")
            return keyword
            
    logger.warning(f"Could not find any of the expected name keywords: {name_keywords}")
    return None