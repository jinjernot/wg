import pytesseract
import re
from PIL import Image
import logging
import cv2
import numpy as np
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

OCR_LOG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ocr_logs')
os.makedirs(OCR_LOG_PATH, exist_ok=True)

def load_ocr_templates():
    """Loads OCR keyword templates from a JSON file."""
    try:
        templates_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ocr_templates.json')
        with open(templates_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Could not load or parse ocr_templates.json from the data folder: {e}")
        return {"bank_templates": {}, "generic_amount_keywords": []}

OCR_TEMPLATES = load_ocr_templates()

try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except FileNotFoundError:
    logger.warning("Tesseract executable not found. Update the path in ocr.py if needed.")

def save_ocr_text(trade_hash, text, identified_bank=None):
    """Saves the extracted OCR text to a file for analysis."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bank_suffix = f"_{identified_bank}" if identified_bank else ""
        filename = f"{trade_hash}{bank_suffix}_{timestamp}.txt"
        filepath = os.path.join(OCR_LOG_PATH, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"Saved OCR text for trade {trade_hash} to {filename}")
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
    """Identifies the source bank from the text using the structured templates."""
    if not text: return None
    text_lower = text.lower()
    
    found_banks = set()
    destination_bank = None
    
    bank_templates = OCR_TEMPLATES.get("bank_templates", {})

    # Identify all banks mentioned and the destination bank
    for bank_name, template in bank_templates.items():
        if any(keyword in text_lower for keyword in template.get("keywords", [])):
            found_banks.add(bank_name)
        if any(ctx in text_lower for ctx in template.get("destination_context", [])):
             destination_bank = bank_name
    
    source_banks = found_banks - {destination_bank}
    
    if len(source_banks) == 1:
        source = source_banks.pop()
        logger.info(f"Identified SOURCE bank: {source} (Destination was {destination_bank})")
        return source
    elif len(found_banks) == 1:
        source = found_banks.pop()
        logger.info(f"Identified the only available bank as SOURCE: {source}")
        return source
    else:
        logger.warning(f"Ambiguous or no bank identification. Found: {found_banks}, Destination: {destination_bank}")
        return None


def find_amount_in_text(text, trade_amount):
    """
    Finds the trade amount in the text, using bank-specific keywords if possible.
    """
    if not text: return None

    identified_bank = identify_bank_from_text(text)
    priority_keywords = OCR_TEMPLATES.get("generic_amount_keywords", [])

    if identified_bank:
        bank_template = OCR_TEMPLATES.get("bank_templates", {}).get(identified_bank, {})
        bank_specific_keywords = bank_template.get("amount_priority", [])
        # Prepend bank-specific keywords to give them higher priority
        priority_keywords = bank_specific_keywords + priority_keywords

    money_pattern = r'\$\s*(\d{1,3}(?:,?\d{3})*\.\d{2})\b'
    all_amounts = []
    priority_amounts = []

    for line in text.lower().split('\n'):
        found_amounts = re.findall(money_pattern, line)
        if not found_amounts: continue

        is_priority_line = any(keyword in line for keyword in priority_keywords)
        for amount_str in found_amounts:
            amount = float(amount_str.replace(',', ''))
            all_amounts.append(amount)
            if is_priority_line:
                priority_amounts.append(amount)

    expected_amount = float(trade_amount)

    # Check priority amounts first, then all amounts
    for amount in priority_amounts:
        if amount == expected_amount:
            logger.info(f"SUCCESS: Found matching priority amount on receipt: {amount}")
            return amount
    for amount in all_amounts:
        if amount == expected_amount:
            logger.info(f"SUCCESS: Found matching amount on receipt: {amount}")
            return amount
            
    logger.warning(f"Amount mismatch. Expected: {expected_amount}, Found on receipt: {all_amounts}")
    return max(all_amounts) if all_amounts else None


def find_name_in_text(text, name_keywords):
    """Searches the extracted text for any of the provided name keywords."""
    if not text or not name_keywords: return False
    
    for keyword in name_keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
            logger.info(f"SUCCESS: Found name keyword '{keyword}' in receipt text.")
            return True
            
    logger.warning(f"Could not find any of the expected name keywords: {name_keywords}")
    return False