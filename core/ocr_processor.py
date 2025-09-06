import pytesseract
import re
from PIL import Image
import logging

try:
    # NOTE: The path to tesseract may need to be adjusted depending on your system.
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except FileNotFoundError:
    logging.warning("Tesseract executable not found at the specified path. Make sure it's in your system's PATH or update the path in ocr_processor.py.")


def extract_text_from_image(image_path):
    """
    Opens an image file and uses Tesseract to extract the text.
    """
    try:
        with Image.open(image_path) as img:
            text = pytesseract.image_to_string(img)
            logging.info(f"Successfully extracted text from {image_path}")
            logging.debug(f"Extracted Text Snippet: {text[:250]}")
            return text
    except Exception as e:
        logging.error(f"Could not read or process image {image_path}: {e}")
        return ""

def find_amount_in_text(text, trade_amount):
    """
    Searches extracted text for a monetary value that matches the trade amount.
    It prioritizes amounts found on lines with keywords like 'total' or 'monto'.
    """
    if not text:
        return None

    # Regex to capture monetary values, allowing for optional commas.
    money_pattern = r'\b(\d{1,3}(?:,?\d{3})*\.\d{2})\b'
    
    # Keywords to identify lines containing the relevant amount.
    priority_keywords = ['pago total', 'total a pagar', 'monto', 'total']
    
    priority_amounts = []
    
    # First, search for amounts on lines containing priority keywords.
    for line in text.lower().split('\n'):
        for keyword in priority_keywords:
            if keyword in line:
                found = re.search(money_pattern, line)
                if found:
                    amount_str = found.group(1).replace(',', '')
                    priority_amounts.append(float(amount_str))
                    logging.info(f"Found priority amount '{amount_str}' on line: '{line.strip()}'")
                    break  # Move to the next line once a keyword is found and processed

    # As a fallback, find all potential amounts in the entire text.
    all_potential_amounts = re.findall(money_pattern, text)
    all_found_floats = sorted(list(set([float(amount.replace(',', '')) for amount in all_potential_amounts])), reverse=True)
    
    logging.info(f"Priority amounts found: {priority_amounts}")
    logging.info(f"All potential amounts found: {all_found_floats}")

    expected_amount = float(trade_amount)

    # Check for an exact match, starting with priority amounts.
    for amount in priority_amounts:
        if amount == expected_amount:
            logging.info(f"SUCCESS: Found matching priority amount on receipt: {amount}")
            return amount

    # If no priority match, check all other found amounts.
    for amount in all_found_floats:
        if amount == expected_amount:
            logging.info(f"SUCCESS: Found matching amount on receipt: {amount}")
            return amount
            
    logging.warning(f"Amount mismatch. Expected: {expected_amount}, Found on receipt: {all_found_floats}")
    
    # If no exact match is found, return the largest amount found as a last resort.
    return max(all_found_floats) if all_found_floats else None