# core/validation/ocr.py
import pytesseract
import re
from PIL import Image
import logging

logger = logging.getLogger(__name__)

try:
    # NOTE: The path to tesseract may need to be adjusted depending on your system.
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except FileNotFoundError:
    logger.warning("Tesseract executable not found at the specified path. Make sure it's in your system's PATH or update the path in ocr_processor.py.")

def extract_text_from_image(image_path):
    """
    Opens an image file and uses Tesseract to extract the text.
    """
    try:
        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img)
            logger.info(f"Successfully extracted text from {image_path}")
            logger.debug(f"Extracted Text Snippet: {text[:250]}")
            return text
    except Exception as e:
        logger.error(f"Could not read or process image {image_path}: {e}")
        return ""

def find_amount_in_text(text, trade_amount):
    """
    Searches extracted text for a monetary value that matches the trade amount.
    It prioritizes amounts found on lines with keywords like 'total' or 'monto'.
    """
    if not text:
        return None

    money_pattern = r'\b(\d{1,3}(?:,?\d{3})*\.\d{2})\b'
    
    priority_keywords = ['pago total', 'total a pagar', 'monto', 'total']
    
    priority_amounts = []
    
    for line in text.lower().split('\n'):
        for keyword in priority_keywords:
            if keyword in line:
                found = re.search(money_pattern, line)
                if found:
                    amount_str = found.group(1).replace(',', '')
                    priority_amounts.append(float(amount_str))
                    logger.info(f"Found priority amount '{amount_str}' on line: '{line.strip()}'")
                    break

    all_potential_amounts = re.findall(money_pattern, text)
    all_found_floats = sorted(list(set([float(amount.replace(',', '')) for amount in all_potential_amounts])), reverse=True)
    
    logger.info(f"Priority amounts found: {priority_amounts}")
    logger.info(f"All potential amounts found: {all_found_floats}")

    expected_amount = float(trade_amount)

    for amount in priority_amounts:
        if amount == expected_amount:
            logger.info(f"SUCCESS: Found matching priority amount on receipt: {amount}")
            return amount

    for amount in all_found_floats:
        if amount == expected_amount:
            logger.info(f"SUCCESS: Found matching amount on receipt: {amount}")
            return amount
            
    logger.warning(f"Amount mismatch. Expected: {expected_amount}, Found on receipt: {all_found_floats}")
    
    return max(all_found_floats) if all_found_floats else None

def find_name_in_text(text, name_keywords):
    """
    Searches the extracted text for any of the provided name keywords.
    Returns True if a match is found, False otherwise.
    """
    if not text or not name_keywords:
        return False
    
    for keyword in name_keywords:
        # Using word boundaries to avoid partial matches (e.g., 'Robert' in 'Roberta')
        if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
            logger.info(f"SUCCESS: Found name keyword '{keyword}' in receipt text.")
            return True
            
    logger.warning(f"Could not find any of the expected name keywords: {name_keywords}")
    return False