#!/usr/bin/env python3
"""
Minimal ShipStation Tracking Number Seeder

This script only extracts actual tracking numbers from ShipStation
and adds them to column A of the UPS Tracker sheet if and only if
they are valid tracking numbers. No other columns are touched.
"""

import os
import base64
import json
import logging
import re
import time
from datetime import datetime, timedelta
 
import requests

def fetch_labels_for_shipment(shipment_id, api_key):
    """
    Fetch Label objects for a given shipment to extract tracking numbers.
    """
    url = "https://api.shipstation.com/v2/labels"
    params = {'shipment_id': shipment_id, 'page': 1, 'page_size': 100}
    headers = {'API-Key': api_key, 'Content-Type': 'application/json'}
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        logger.error(f"Failed to fetch labels for shipment {shipment_id}: {response.status_code} - {response.text}")
        return []
    data = response.json()
    return data.get('labels', [])

import gspread
from google.oauth2.service_account import Credentials

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tracking_seeder.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Google Sheets API scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Constants
SHEET_NAME = 'UPS Tracker'

# Valid tracking number patterns
TRACKING_PATTERNS = {
    'UPS': r'^1Z[0-9A-Z]{16}$|^T\d{10}$|^\d{9}$',
    'USPS': r'^9[0-9]{15,21}$|^[A-Z]{2}[0-9]{9}US$',
    'FedEx': r'^[0-9]{12,14}$|^[0-9]{20,22}$',
    'DHL': r'^[0-9]{10,11}$'
}

def setup_google_sheets():
    """Authenticate with Google Sheets API using service account credentials."""
    try:
        # Check if credentials are provided as a file or as a base64-encoded string
        if os.path.exists('credentials.json'):
            logger.info("Using credentials.json file")
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        else:
            # Decode base64-encoded credentials from environment variable
            logger.info("Using GOOGLE_CREDENTIALS environment variable")
            credentials_json = base64.b64decode(os.environ['GOOGLE_CREDENTIALS']).decode('utf-8')
            credentials_info = json.loads(credentials_json)
            creds = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        
        # Connect to Google Sheets
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        
        logger.info(f"Successfully connected to Google Sheet: {SHEET_NAME}")
        return sheet
    except Exception as e:
        logger.error(f"Error setting up Google Sheets: {e}")
        raise

def is_valid_tracking_number(tracking_number):
    """
    Check if a string is a valid tracking number.
    Returns True if it matches any known carrier pattern.
    """
    if not tracking_number or len(tracking_number) < 8:
        return False
        
    for pattern in TRACKING_PATTERNS.values():
        if re.match(pattern, tracking_number):
            return True
    
    return False

def get_existing_tracking_numbers(sheet):
    """
    Get all existing tracking numbers from the sheet.
    Returns them as a set for efficient lookup.
    """
    try:
        # Get all values from column A
        col_values = sheet.col_values(1)  # Column A = 1
        
        # Skip header row if it exists
        if col_values and col_values[0].lower() == 'tracking number':
            col_values = col_values[1:]
        
        # Convert to set for O(1) lookup
        return set(col_values)
    except Exception as e:
        logger.error(f"Error getting existing tracking numbers: {e}")
        return set()

def fetch_shipstation_tracking_numbers(days_to_look_back=180):
    """
    Connect to ShipStation API and extract ONLY valid tracking numbers.
    
    Args:
        days_to_look_back: Number of days to look back for shipments
        
    Returns:
        list: List of valid tracking numbers (strings)
    """
    valid_tracking_numbers = []
    
    try:
        # Get ShipStation API key from environment
        api_key = os.environ.get('SHIPSTATION_API_KEY')
        
        if not api_key:
            logger.error("Missing ShipStation API key")
            return valid_tracking_numbers
        
        # Calculate date for filtering
        # Only include shipments from the last 120 days
        cutoff_date = datetime.now() - timedelta(days=120)
        
        # ShipStation API V2 endpoint for listing shipments
        url = "https://api.shipstation.com/v2/shipments"
        
        # V2 API uses API-Key header for authentication
        headers = {
            'API-Key': api_key,
            'Content-Type': 'application/json'
        }
        
        # ShipStation API uses pagination
        page = 1
        page_size = 100
        more_pages = True
        max_pages = 20  # Limit to processing only 20 pages
        
        while more_pages:
            # Build parameters using V2 API snake_case naming
            now_iso = datetime.now().isoformat()
            cutoff_iso = cutoff_date.isoformat()
            params = {
                'created_at_start': cutoff_iso,
                'created_at_end': now_iso,
                'sort_by': 'created_at',
                'sort_dir': 'desc',
                'page': page,
                'page_size': page_size
            }
            
            logger.info(f"Fetching ShipStation shipments page {page}")
            
            # Make the request
            response = requests.get(
                url,
                params=params,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch from ShipStation API: {response.status_code} - {response.text}")
                break
            
            # Process response
            data = response.json()
            shipments = data.get('shipments', [])
            total_pages = data.get('pages', 1)
            
            logger.info(f"Fetched {len(shipments)} shipments from page {page} of {total_pages}")
            # Stop early if we've reached the maximum page limit
            if page >= max_pages:
                logger.info(f"Reached max page limit ({max_pages}), stopping fetch early")
                break

            if not shipments:
                logger.info("No more shipments to fetch")
                break
            
            # Extract tracking numbers
            for shipment in shipments:
                checked_numbers = set()  # To avoid duplicates
                tracking = shipment.get('trackingNumber') or shipment.get('tracking_number')
                if tracking and tracking not in checked_numbers:
                    for carrier in ('UPS', 'USPS', 'DHL'):
                        pattern = TRACKING_PATTERNS.get(carrier)
                        if pattern and re.fullmatch(pattern, tracking):
                            valid_tracking_numbers.append(tracking)
                            logger.info(f"Found valid {carrier} tracking number: {tracking}")
                            break
                    else:
                        logger.debug(f"Filtered out non-target or invalid tracking number: {tracking}")
                    checked_numbers.add(tracking)
                
                # Determine the shipment ID using camelCase or snake_case
                shipment_id_value = shipment.get('shipmentId') or shipment.get('shipment_id')
                if not shipment_id_value:
                    logger.debug(f"No shipment ID found for shipment: {shipment}")
                    continue

                # 2. Fetch label-level tracking numbers for this shipment
                labels = fetch_labels_for_shipment(shipment_id_value, api_key)
                for label in labels:
                    track = label.get('tracking_number') or label.get('trackingNumber')
                    if not track or track in checked_numbers:
                        continue
                    for carrier in ('UPS', 'USPS', 'DHL'):
                        pattern = TRACKING_PATTERNS.get(carrier)
                        if pattern and re.fullmatch(pattern, track):
                            valid_tracking_numbers.append(track)
                            logger.info(f"Found valid {carrier} tracking number on label: {track}")
                            break
                    else:
                        logger.debug(f"Filtered out non-target or invalid tracking number on label: {track}")
                    checked_numbers.add(track)
            
            # Check if we've reached the end
            if page >= total_pages:
                break
            
            # Move to next page
            page += 1
            time.sleep(1)  # Delay to avoid rate limits
        
        logger.info(f"Extracted {len(valid_tracking_numbers)} valid tracking numbers")
        return valid_tracking_numbers
    
    except Exception as e:
        logger.error(f"Error fetching from ShipStation API: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        return valid_tracking_numbers

def add_tracking_numbers_to_sheet(sheet, tracking_numbers):
    """
    Add new tracking numbers to the sheet.
    Only adds to column A and only if not already present.
    
    Args:
        sheet: Google Sheet object
        tracking_numbers: List of tracking numbers to add
        
    Returns:
        int: Number of tracking numbers added
    """
    try:
        # Get existing tracking numbers
        existing_numbers = get_existing_tracking_numbers(sheet)
        logger.info(f"Found {len(existing_numbers)} existing tracking numbers in sheet")
        
        # Filter out duplicates
        new_tracking_numbers = [tn for tn in tracking_numbers if tn not in existing_numbers]
        logger.info(f"Found {len(new_tracking_numbers)} new tracking numbers to add")

        # Determine the next available row (accounting for header)
        next_row = len(existing_numbers) + 2  # +1 for header, +1 to start at next row
        if not existing_numbers:
            # If sheet is empty, ensure header exists and adjust next_row
            values = sheet.get_values()
            if not values or values[0][0].lower() != 'tracking number':
                sheet.update('A1', [['Tracking Number']])
                logger.info("Added header row")
            next_row = 2
        
        # Ensure the sheet has enough rows to accommodate new entries
        current_rows = sheet.row_count
        required_rows = next_row + len(new_tracking_numbers) - 1
        if required_rows > current_rows:
            try:
                extra = required_rows - current_rows
                sheet.add_rows(extra)
                logger.info(f"Added {extra} extra rows to sheet (now {required_rows} rows total)")
            except Exception as e:
                logger.error(f"Failed to expand sheet rows: {e}")
        
        if not new_tracking_numbers:
            logger.info("No new tracking numbers to add")
            return 0
        
        # Batch updates for efficiency
        cell_list = []
        for i, tracking in enumerate(new_tracking_numbers):
            cell_list.append({'range': f'A{next_row + i}', 'values': [[tracking]]})
        
        # Apply updates if we have any
        if cell_list:
            # Split into smaller batches to avoid rate limits (max 20 per batch)
            batch_size = 20
            for i in range(0, len(cell_list), batch_size):
                batch = cell_list[i:i+batch_size]
                sheet.batch_update(batch)
                logger.info(f"Updated batch of {len(batch)} tracking numbers")
                time.sleep(1)  # Delay to avoid rate limits
            
            logger.info(f"Added {len(new_tracking_numbers)} new tracking numbers to sheet")
        
        return len(new_tracking_numbers)
    
    except Exception as e:
        logger.error(f"Error adding tracking numbers to sheet: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        return 0

def main():
    """Main function to orchestrate the seeding process."""
    try:
        logger.info("Starting minimal tracking number seeder")
        
        # Fetch tracking numbers from ShipStation
        tracking_numbers = fetch_shipstation_tracking_numbers()
        
        if not tracking_numbers:
            logger.warning("No valid tracking numbers found")
            print("No valid tracking numbers found. Check the logs for details.")
            return
        
        # Connect to Google Sheets
        sheet = setup_google_sheets()
        
        # Add tracking numbers to sheet
        added_count = add_tracking_numbers_to_sheet(sheet, tracking_numbers)
        
        # Print summary to console
        print(f"\nSeeding completed!")
        print(f"Added {added_count} new tracking numbers to column A")
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        print(f"Error: {e}")
        print("Check the logs for detailed information.")

if __name__ == "__main__":
    main()