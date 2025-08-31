import pytesseract
import re
from PIL import Image
import logging

try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # Example for Windows
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
    Searches the extracted text for a monetary value that matches the trade amount.
    Returns the found amount as a float, or None if not found.
    """
    if not text:
        return None

    money_pattern = r'(\d{1,3}(?:,\d{3})*\.\d{2})'
    
    potential_amounts = re.findall(money_pattern, text)
    
    logging.info(f"Potential amounts found in receipt: {potential_amounts}")

    # Convert found strings to float for comparison
    found_floats = [float(amount.replace(',', '')) for amount in potential_amounts]
    
    # Check if any of the found amounts match the trade amount
    expected_amount = float(trade_amount)
    for amount in found_floats:
        if amount == expected_amount:
            logging.info(f"SUCCESS: Found matching amount on receipt: {amount}")
            return amount
            
    logging.warning(f"Amount mismatch. Expected: {expected_amount}, Found on receipt: {found_floats}")
    # Return the largest amount found if no exact match, or None
    return max(found_floats) if found_floats else None