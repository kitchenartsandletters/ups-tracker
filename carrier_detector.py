#!/usr/bin/env python3
"""
Carrier Detection Module

This module contains functions to detect which carrier a tracking number belongs to
based on its format and pattern.
"""

import re
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Define carrier tracking number patterns
CARRIER_PATTERNS = {
    'UPS': [
        r'^1Z[0-9A-Z]{16}$',  # UPS standard format (1Z + 16 chars)
        r'^T\d{10}$',          # UPS Mail Innovations
        r'^\d{9}$',            # UPS alternative format (9 digits)
        r'^\d{12}$',           # UPS Freight
        r'^(H|V|R|U)\d{9}$'    # UPS alternative format with prefix
    ],
    'USPS': [
        r'^9[0-9]{15,21}$',    # USPS Intelligent Mail (20-22 digits starting with 9)
        r'^[A-Z]{2}[0-9]{9}US$',  # USPS International (2 letters + 9 digits + US)
        r'^E[A-Z]{1}[0-9]{9}US$',  # USPS International Special Services
        r'^[0-9]{20}$',        # USPS Intelligent Mail package barcode
        r'^([A-Z]{2})?[0-9]{13}$'  # USPS tracking for certain packages
    ],
    'DHL': [
        r'^[0-9]{10,11}$',     # DHL Express (10-11 digits)
        r'^JD[0-9]{18}$',      # DHL eCommerce with JD prefix
        r'^[0-9]{4} ?[0-9]{4} ?[0-9]{2}$'  # DHL Express (format: #### #### ##)
    ]
}

def detect_carrier(tracking_number):
    """
    Detect which carrier a tracking number belongs to.
    
    Args:
        tracking_number (str): The tracking number to analyze
        
    Returns:
        str: Carrier name ('UPS', 'USPS', 'DHL') or 'UNKNOWN' if not detected
    """
    if not tracking_number:
        return 'UNKNOWN'
    
    # Clean the tracking number - remove spaces and convert to uppercase
    tracking_number = tracking_number.strip().upper().replace(' ', '')
    
    logger.debug(f"Detecting carrier for tracking number: {tracking_number}")
    
    # Check against each carrier's patterns
    for carrier, patterns in CARRIER_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, tracking_number):
                logger.info(f"Detected carrier for {tracking_number}: {carrier}")
                return carrier
    
    logger.warning(f"Could not detect carrier for tracking number: {tracking_number}")
    return 'UNKNOWN'

def format_tracking_number(tracking_number, carrier=None):
    """
    Format tracking number for display and API calls.
    Some carriers need specific formatting.
    
    Args:
        tracking_number (str): The tracking number to format
        carrier (str, optional): The carrier name if known
        
    Returns:
        str: Properly formatted tracking number
    """
    if not tracking_number:
        return tracking_number
    
    # Strip spaces and convert to uppercase
    tracking_number = tracking_number.strip().upper().replace(' ', '')
    
    # Detect carrier if not provided
    if not carrier:
        carrier = detect_carrier(tracking_number)
    
    # Apply carrier-specific formatting
    if carrier == 'DHL' and len(tracking_number) == 10:
        # Format DHL as #### #### ##
        if re.match(r'^[0-9]{10}$', tracking_number):
            return f"{tracking_number[:4]} {tracking_number[4:8]} {tracking_number[8:]}"
    
    # Return as is for other carriers
    return tracking_number

def validate_tracking_number(tracking_number):
    """
    Validate if a tracking number appears to be in a valid format.
    
    Args:
        tracking_number (str): The tracking number to validate
        
    Returns:
        bool: True if the tracking number matches any known pattern
    """
    if not tracking_number:
        return False
    
    # Clean the tracking number
    tracking_number = tracking_number.strip().upper().replace(' ', '')
    
    # Check if it matches any carrier pattern
    carrier = detect_carrier(tracking_number)
    return carrier != 'UNKNOWN'

# Test the module when run directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test tracking numbers
    test_numbers = [
        '1Z999AA1X123456789',  # UPS
        '9400123456789123456789',  # USPS
        '1234567890',  # DHL
        'INVALID123',  # Invalid format
        'RA123456789',  # UPS with prefix
        'AA123456789US',  # USPS International
        'JD123456789012345678'  # DHL eCommerce
    ]
    
    for num in test_numbers:
        carrier = detect_carrier(num)
        formatted = format_tracking_number(num, carrier)
        valid = validate_tracking_number(num)
        print(f"Number: {num} -> Carrier: {carrier}, Valid: {valid}, Formatted: {formatted}")