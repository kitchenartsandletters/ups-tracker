#!/usr/bin/env python3
"""
Multi-Carrier Package Tracking to Google Sheets

This script:
1. Reads tracking numbers from a Google Sheet
2. Detects carrier based on tracking number format
3. Queries the appropriate carrier API for each tracking number
4. Updates the Google Sheet with the latest tracking information
"""

import os
import base64
import json
import logging
from datetime import datetime
import time

import requests
import gspread
from google.oauth2.service_account import Credentials

# Import our modules
from carrier_detector import detect_carrier, format_tracking_number
from carrier_api import create_carrier_api

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Google Sheets API scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Constants
SHEET_NAME = 'Shipped Orders Tracker'  # Updated name (was 'UPS Tracker')
TRACKING_COLUMN = 'A'    # Column for tracking numbers
CARRIER_COLUMN = 'B'     # Column for carrier info
STATUS_COLUMN = 'C'      # Column for status
UPDATE_COLUMN = 'D'      # Column for last update timestamp
LOCATION_COLUMN = 'E'    # Column for current location
ADDRESS_COLUMN = 'F'     # Column for validated address
ETA_COLUMN = 'G'         # Column for estimated delivery time

# Column index mapping (for header creation)
COLUMN_MAPPING = {
    TRACKING_COLUMN: 'Tracking Number',
    CARRIER_COLUMN: 'Carrier',
    STATUS_COLUMN: 'Status',
    UPDATE_COLUMN: 'Last Update',
    LOCATION_COLUMN: 'Current Location',
    ADDRESS_COLUMN: 'Validated Address',
    ETA_COLUMN: 'Estimated Delivery'
}

# Carrier logo URLs (for custom cell formatting)
CARRIER_LOGOS = {
    'UPS': 'https://upload.wikimedia.org/wikipedia/commons/thumb/1/1b/UPS_logo_2017.svg/1024px-UPS_logo_2017.svg.png',
    'USPS': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/USPS_Logo.png/1024px-USPS_Logo.png',
    'DHL': 'https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/DHL_Logo.svg/1024px-DHL_Logo.svg.png',
    'UNKNOWN': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/Question_mark_icon.png/1024px-Question_mark_icon.png'
}

def setup_google_sheets():
    """Authenticate with Google Sheets API using service account credentials."""
    try:
        # Check if credentials are provided as a file or as a base64-encoded string
        if os.path.exists('credentials.json'):
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        else:
            # Decode base64-encoded credentials from environment variable
            credentials_json = base64.b64decode(os.environ['GOOGLE_CREDENTIALS']).decode('utf-8')
            credentials_info = json.loads(credentials_json)
            creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        
        # Connect to Google Sheets
        client = gspread.authorize(creds)
        
        try:
            # Try to open existing sheet
            sheet = client.open(SHEET_NAME).sheet1
            logger.info(f"Successfully connected to Google Sheet: {SHEET_NAME}")
        except gspread.exceptions.SpreadsheetNotFound:
            # If sheet doesn't exist, create it
            logger.info(f"Sheet '{SHEET_NAME}' not found, creating new one")
            sheet = client.create(SHEET_NAME).sheet1
            
            # Set up header row with carrier column
            setup_sheet_headers(sheet)
            
            logger.info(f"Created new Google Sheet: {SHEET_NAME}")
        
        return sheet
    except Exception as e:
        logger.error(f"Error setting up Google Sheets: {e}")
        raise

def setup_sheet_headers(sheet):
    """Set up header row for the sheet."""
    try:
        # Create header row
        header_row = []
        for col in 'ABCDEFG':  # Add more columns if needed
            if col in COLUMN_MAPPING:
                header_row.append(COLUMN_MAPPING[col])
            else:
                header_row.append('')
        
        # Update the first row
        sheet.update('A1:G1', [header_row])
        
        # Format header row
        fmt = {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
            "horizontalAlignment": "CENTER"
        }
        sheet.format('A1:G1', {'textFormat': {'bold': True}})
        
        # Set column widths
        sheet.batch_update([{
            'updateDimensionProperties': {
                'range': {
                    'sheetId': 0,
                    'dimension': 'COLUMNS',
                    'startIndex': 0,
                    'endIndex': 7
                },
                'properties': {
                    'pixelSize': 150
                },
                'fields': 'pixelSize'
            }
        }, {
            # Make tracking number column wider
            'updateDimensionProperties': {
                'range': {
                    'sheetId': 0,
                    'dimension': 'COLUMNS',
                    'startIndex': 0,
                    'endIndex': 1
                },
                'properties': {
                    'pixelSize': 180
                },
                'fields': 'pixelSize'
            }
        }])
        
        logger.info("Successfully set up sheet headers and formatting")
    except Exception as e:
        logger.error(f"Error setting up sheet headers: {e}")
        # Continue execution even if formatting fails

def get_origin_address():
    """Get origin address from environment variables."""
    return {
        "street": os.environ.get('ORIGIN_STREET', ''),
        "city": os.environ.get('ORIGIN_CITY', ''),
        "state": os.environ.get('ORIGIN_STATE', ''),
        "postal_code": os.environ.get('ORIGIN_ZIP', ''),
        "country": "US"  # Default to US
    }

def update_sheet_row(sheet, row, data):
    """
    Update a row in the Google Sheet with tracking information.
    Uses batch updates to avoid API rate limits.
    
    Args:
        sheet: Google Sheet object
        row: Row number to update
        data: Dict containing update data
    """
    try:
        # Add current timestamp to show when the script ran
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare all updates as a batch
        updates = []
        
        # Update carrier
        if 'carrier' in data and data['carrier']:
            updates.append({
                'range': f'{CARRIER_COLUMN}{row}',
                'values': [[data['carrier']]]
            })
        
        # Update status
        if 'status' in data and data['status']:
            updates.append({
                'range': f'{STATUS_COLUMN}{row}',
                'values': [[data['status']]]
            })
        
        # Update last_update
        if 'last_update' in data and data['last_update']:
            updates.append({
                'range': f'{UPDATE_COLUMN}{row}',
                'values': [[f"{data['last_update']} (updated {current_time})"]]
            })
        
        # Update location
        if 'location' in data and data['location']:
            updates.append({
                'range': f'{LOCATION_COLUMN}{row}',
                'values': [[data['location']]]
            })
            
        # Update validated_address
        if 'validated_address' in data and data['validated_address']:
            updates.append({
                'range': f'{ADDRESS_COLUMN}{row}',
                'values': [[data['validated_address']]]
            })
            
        # Update estimated_delivery
        if 'estimated_delivery' in data and data['estimated_delivery']:
            # Remove prefix if present
            delivery = data['estimated_delivery']
            if delivery.startswith("Estimated delivery: "):
                delivery = delivery[len("Estimated delivery: "):]
                
            updates.append({
                'range': f'{ETA_COLUMN}{row}',
                'values': [[delivery]]
            })
        
        # If we have updates, apply them as a batch
        if updates:
            sheet.batch_update(updates)
            logger.info(f"Updated row {row} with latest tracking information")
        
    except Exception as e:
        logger.error(f"Error updating sheet row {row}: {e}")
        import traceback
        logger.error(f"Update error details: {traceback.format_exc()}")

def process_tracking_number(tracking_number, row_index, sheet):
    """
    Process a single tracking number by detecting carrier and getting tracking info.
    
    Args:
        tracking_number (str): The tracking number to process
        row_index (int): The row index in the spreadsheet
        sheet (object): Google Sheet object
    """
    try:
        # Skip empty tracking numbers
        if not tracking_number or tracking_number.strip() == '':
            logger.warning(f"Empty tracking number at row {row_index}, skipping")
            return
        
        # Clean tracking number
        tracking_number = tracking_number.strip()
        logger.info(f"Processing tracking number: {tracking_number} (row {row_index})")
        
        # Detect carrier based on tracking number format
        carrier = detect_carrier(tracking_number)
        logger.info(f"Detected carrier for {tracking_number}: {carrier}")
        
        # Create the appropriate carrier API
        carrier_api = create_carrier_api(carrier)
        if not carrier_api:
            logger.error(f"Failed to create carrier API for {carrier}, skipping")
            
            # Update sheet with just the carrier info
            update_data = {'carrier': carrier or 'UNKNOWN'}
            update_sheet_row(sheet, row_index, update_data)
            return
        
        # Get tracking information
        track_result = carrier_api.get_tracking_info(tracking_number)
        
        if not track_result:
            logger.error(f"Failed to get tracking info for {tracking_number}, skipping")
            
            # Update sheet with just the carrier info
            update_data = {'carrier': carrier, 'status': 'API Error'}
            update_sheet_row(sheet, row_index, update_data)
            return
        
        # Extract data from standardized response
        status = track_result.get('status')
        last_update = track_result.get('last_update')
        location = track_result.get('location')
        address_dict = track_result.get('address')
        delivery_estimate = track_result.get('delivery_estimate')
        carrier_name = track_result.get('carrier')
        
        # Prepare update data
        update_data = {
            'carrier': carrier_name,
            'status': status,
            'last_update': last_update,
            'location': location
        }
        
        # Add delivery estimate if available
        if delivery_estimate:
            update_data['estimated_delivery'] = delivery_estimate
        
        # Validate address if we have address data
        validated_address = None
        
        if address_dict and any(address_dict.values()):
            # Try to validate address using carrier's API
            validation_data = carrier_api.validate_address(address_dict)
            
            if validation_data:
                # Different carriers may return different validation formats
                # For now, just indicate that address was validated
                validated_address = f"Address validated by {carrier_name}"
            else:
                # If validation fails, just use what we have
                validated_address = "Address validation failed"
            
            update_data['validated_address'] = validated_address
            
            # Only try time in transit if we don't already have a delivery estimate
            if not delivery_estimate:
                origin_address = get_origin_address()
                
                # Check if we have minimum data for transit calculation
                if origin_address.get('postal_code') and address_dict.get('postal_code'):
                    logger.info(f"No delivery estimate from tracking data, trying {carrier_name} time in transit API")
                    time_data = carrier_api.get_estimated_delivery(origin_address, address_dict)
                    
                    if time_data:
                        # Each carrier may have different ways to extract the estimate
                        # For now, just use a placeholder value
                        estimated_delivery = f"Estimated by {carrier_name}"
                        update_data['estimated_delivery'] = estimated_delivery
        
        # Update sheet with all collected data
        update_sheet_row(sheet, row_index, update_data)
        
        # Small delay to avoid API rate limits
        time.sleep(1)
        
    except Exception as e:
        logger.error(f"Error processing tracking number {tracking_number}: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")

def main():
    """Main function to orchestrate the tracking process."""
    try:
        logger.info("Starting multi-carrier package tracking script")
        
        # Set up Google Sheets connection
        sheet = setup_google_sheets()
        
        # Get sheet values
        all_values = sheet.get_all_values()
        
        # Check if sheet is empty or needs header
        if len(all_values) == 0 or all_values[0][0].lower() != 'tracking number':
            # Set up headers
            setup_sheet_headers(sheet)
            
            # Re-fetch values after setting up headers
            all_values = sheet.get_all_values()
            
            # If still empty, nothing to process
            if len(all_values) <= 1:  # Only header row
                logger.info("No tracking numbers found in sheet, exiting")
                return
        
        # Start processing from row 2 (skip header)
        start_row = 2
        
        # Process each tracking number
        for i, row in enumerate(all_values[start_row-1:], start=start_row):
            # Skip empty rows
            if not row or not row[0]:
                continue
                
            tracking_number = row[0].strip()
            process_tracking_number(tracking_number, i, sheet)
        
        logger.info("Multi-carrier tracking script completed successfully")
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        import traceback
        logger.error(f"Main function error details: {traceback.format_exc()}")

if __name__ == "__main__":
    main()