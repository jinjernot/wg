import logging
import csv
import os
from datetime import datetime, timezone
from config import TRADE_HISTORY # Use TRADE_HISTORY to match the download route
from core.api.offers import search_public_offers

logger = logging.getLogger(__name__)

# --- UPDATED LIST ---
# Corrected Amazon slug based on your feedback and removed -mxn from Google Play.
MXN_PAYMENT_METHODS = [
    "bank-transfer",
    "oxxo",
    "spei-sistema-de-pagos-electronicos-interbancarios",
    "domestic-wire-transfer",
    "banco-azteca",
    "bbva-bancomer",
    "banorte",
    "citibanamex",
    "amazon-gift-card",
    "uber-gift-card",
    "uber-eats",
    "google-play-gift-card"
]
# --- END UPDATED LIST ---

CRYPTOS = ["BTC", "USDT"]
FIAT = "MXN"

def generate_mxn_market_report():
    """
    Generates a full CSV report for all MXN payment methods, for both
    buy and sell offers.
    Returns the (filepath, filename) of the generated report.
    """
    logger.info("Starting generation of full MXN market report...")
    
    all_offers_data = []
    
    for crypto in CRYPTOS:
        for pm_slug in MXN_PAYMENT_METHODS:
            # We scan both 'buy' (your competitors) and 'sell' (your customers' other option)
            for trade_direction in ["buy", "sell"]:
                market_key = f"{crypto}_{FIAT}_{pm_slug} ({trade_direction})"
                logger.info(f"Scanning market: {market_key}")
                
                try:
                    offers = search_public_offers(crypto, FIAT, pm_slug, trade_direction)

                    if not offers:
                        logger.warning(f"No offers found for market {market_key}.")
                        continue
                    
                    logger.info(f"Found {len(offers)} offers for {market_key}.")
                    
                    # Process and flatten the data for the CSV
                    for offer in offers:
                        flat_offer = {
                            "market_crypto": crypto,
                            "market_fiat": FIAT,
                            "market_payment_method": pm_slug,
                            "offer_type": offer.get("offer_type"),
                            "username": offer.get("offer_owner_username"),
                            "positive_feedback": offer.get("offer_owner_feedback_positive"),
                            "negative_feedback": offer.get("offer_owner_feedback_negative"),
                            "total_successful_trades": offer.get("total_successful_trades"),
                            "last_seen_string": offer.get("last_seen_string"),
                            "margin": offer.get("margin"),
                            "min_amount": offer.get("fiat_amount_range_min"),
                            "max_amount": offer.get("fiat_amount_range_max"),
                            "offer_id": offer.get("offer_id"),
                            "offer_link": offer.get("offer_link"),
                            "payment_window": offer.get("payment_window"),
                            "require_verified_id": offer.get("require_verified_id"),
                            "require_min_past_trades": offer.get("require_min_past_trades")
                        }
                        all_offers_data.append(flat_offer)
                
                except Exception as e:
                    logger.error(f"Failed to process market {market_key}: {e}")

    if not all_offers_data:
        logger.warning("No data collected for the report. Aborting.")
        return None, None

    # Define CSV headers in a logical order
    fieldnames = [
        "market_crypto", "market_fiat", "market_payment_method", "offer_type",
        "username", "margin", "min_amount", "max_amount", 
        "positive_feedback", "negative_feedback", "total_successful_trades",
        "last_seen_string", "offer_id", "offer_link", "payment_window",
        "require_verified_id", "require_min_past_trades"
    ]
    
    # Create the file in the TRADE_HISTORY directory
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"mxn_market_report_all_{date_str}.csv"
    filepath = os.path.join(TRADE_HISTORY, filename)
    
    try:
        with open(filepath, "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(all_offers_data)
        
        logger.info(f"Successfully generated market report: {filepath}")
        return filepath, filename
    except IOError as e:
        logger.error(f"Failed to write report to CSV: {e}")
        return None, None