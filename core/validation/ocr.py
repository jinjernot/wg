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

# --- NEW: Define the path for OCR logs ---
OCR_LOG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ocr_logs')
os.makedirs(OCR_LOG_PATH, exist_ok=True) # Ensures the directory exists

# --- NEW: Load OCR Templates from JSON ---
def load_ocr_templates():
    """Loads OCR keyword templates from a JSON file."""
    try:
        # **PATH UPDATED TO LOOK INSIDE THE 'data' FOLDER**
        templates_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ocr_templates.json')
        with open(templates_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Could not load or parse ocr_templates.json from the data folder: {e}")
        # Return a default structure to prevent crashes
        return {"bank_keywords": {}, "amount_keywords": {"priority": []}}

OCR_TEMPLATES = load_ocr_templates()
# -----------------------------------------

try:
    # NOTE: The path to tesseract may need to be adjusted depending on your system.
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except FileNotFoundError:
    logger.warning("Tesseract executable not found at the specified path. Make sure it's in your system's PATH or update the path in ocr_processor.py.")

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
    """
    Applies pre-processing techniques to an image to improve OCR accuracy.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Could not read image from path: {image_path}")
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        denoised = cv2.medianBlur(binary, 3)
        return denoised
    except Exception as e:
        logger.error(f"An error occurred during image pre-processing for {image_path}: {e}")
        return None

def extract_text_from_image(image_path):
    """
    Opens an image file, pre-processes it, and uses Tesseract to extract the text.
    """
    try:
        preprocessed_image = preprocess_image_for_ocr(image_path)
        
        if preprocessed_image is None:
            logger.warning("Pre-processing failed. Falling back to original image.")
            with Image.open(image_path) as img:
                text = pytesseract.image_to_string(img)
        else:
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(preprocessed_image, config=custom_config)

        logger.info(f"Successfully extracted text from {image_path}")
        logger.debug(f"Extracted Text Snippet: {text[:250]}")
        return text
    except Exception as e:
        logger.error(f"Could not read or process image {image_path}: {e}")
        return ""

def identify_bank_from_text(text):
    """
    Identifies the bank or payment provider based on keywords from the template file.
    """
    if not text:
        return None

    text_lower = text.lower()
    bank_keywords = OCR_TEMPLATES.get("bank_keywords", {})

    for bank, keywords in bank_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            logger.info(f"Identified receipt source as: {bank}")
            return bank

    logger.warning("Could not identify the bank from the receipt text.")
    return None

def find_amount_in_text(text, trade_amount):
    """
    Searches extracted text for a monetary value that matches the trade amount.
    It uses priority keywords from the template file.
    """
    if not text:
        return None

    money_pattern = r'\$\s*(\d{1,3}(?:,?\d{3})*\.\d{2})\b'
    # Use keywords from the loaded JSON template
    priority_keywords = OCR_TEMPLATES.get("amount_keywords", {}).get("priority", [])
    priority_amounts = []
    all_amounts = []

    for line in text.lower().split('\n'):
        found_amounts = re.findall(money_pattern, line)
        if not found_amounts:
            continue
        is_priority_line = any(keyword in line for keyword in priority_keywords)
        for amount_str in found_amounts:
            amount = float(amount_str.replace(',', ''))
            all_amounts.append(amount)
            if is_priority_line:
                priority_amounts.append(amount)
                logger.info(f"Found priority amount '{amount}' on line: '{line.strip()}'")
    
    all_found_floats = sorted(list(set(all_amounts)), reverse=True)
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
    """
    if not text or not name_keywords:
        return False
    
    for keyword in name_keywords:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
            logger.info(f"SUCCESS: Found name keyword '{keyword}' in receipt text.")
            return True
            
    logger.warning(f"Could not find any of the expected name keywords: {name_keywords}")
    return False