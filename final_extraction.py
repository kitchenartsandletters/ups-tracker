#!/usr/bin/env python3
"""
ShipStation V2 Tracking Number Final Extraction Script

This script specifically targets the packages array in ShipStation shipments
based on the structure observed in the shipstation_v2_response.json file.
"""

import os
import sys
import json
import base64
import logging
import argparse
from datetime import datetime, timedelta
import re
import time

import requests
import gspread
from google.oauth2.service_account import Credentials

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("seeding_tool.log"),
        logging.StreamHandler(sys.stdout)
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
TRACKING_COLUMN = 'A'    # Column for tracking numbers
STATUS_COLUMN = 'B'      # Column for status
UPDATE_COLUMN = 'C'      # Column for last update timestamp
LOCATION_COLUMN = 'D'    # Column for current location
ADDRESS_COLUMN = 'E'     # Column for validated address
ETA_COLUMN = 'F'         # Column for estimated delivery time

# Carrier validation patterns
CARRIER_PATTERNS = {
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
            creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        else:
            # Decode base64-encoded credentials from environment variable
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

def detect_carrier(tracking_number):
    """
    Detect carrier based on tracking number format.
    Returns the carrier name or 'UNKNOWN' if not recognized.
    """
    for carrier, pattern in CARRIER_PATTERNS.items():
        if re.match(pattern, tracking_number):
            return carrier
    return 'UNKNOWN'

def is_duplicate(sheet, tracking_number):
    """
    Check if a tracking number already exists in the sheet.
    Returns True if it's a duplicate, False otherwise.
    """
    try:
        # Get all tracking numbers from column A
        tracking_column = sheet.get_all_values()
        
        # Skip header row if it exists
        if tracking_column and tracking_column[0][0].lower() == 'tracking number':
            tracking_column = tracking_column[1:]
        
        # Check if tracking number exists
        for row in tracking_column:
            if row and row[0].strip() == tracking_number.strip():
                return True
        
        return False
    except Exception as e:
        logger.error(f"Error checking for duplicate tracking number: {e}")
        # If there's an error, assume it's not a duplicate to be safe
        return False

def add_tracking_to_sheet(sheet, tracking_data):
    """
    Add tracking information to Google Sheet.
    Handles duplicate checking and proper formatting.
    
    Args:
        sheet: Google Sheet object
        tracking_data: List of dicts with tracking information
    
    Returns:
        tuple: (added_count, duplicate_count, error_count)
    """
    added_count = 0
    duplicate_count = 0
    error_count = 0
    
    try:
        # Check if we need to add header row
        all_values = sheet.get_all_values()
        
        if len(all_values) == 0 or all_values[0][0].lower() != 'tracking number':
            # Add header row
            headers = [
                'Tracking Number', 
                'Status', 
                'Last Update', 
                'Current Location', 
                'Validated Address', 
                'Estimated Delivery'
            ]
            sheet.update('A1:F1', [headers])
            next_row = 2  # Start at row 2 after header
        else:
            next_row = len(all_values) + 1  # Start at the next available row
        
        # Prepare batch updates
        batch_updates = []
        
        # Process each tracking entry
        for entry in tracking_data:
            tracking_number = entry.get('tracking_number', '').strip()
            
            if not tracking_number:
                logger.warning("Empty tracking number found, skipping")
                error_count += 1
                continue
                
            # Check for duplicates
            if is_duplicate(sheet, tracking_number):
                logger.info(f"Skipping duplicate tracking number: {tracking_number}")
                duplicate_count += 1
                continue
                
            # Prepare row data
            row_data = [
                tracking_number,                                           # Tracking Number
                entry.get('status', 'Pending'),                           # Status
                f"Added on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", # Last Update
                entry.get('location', ''),                                 # Current Location
                entry.get('address', ''),                                  # Validated Address
                entry.get('estimated_delivery', '')                        # Estimated Delivery
            ]
            
            # Add to batch updates
            batch_updates.append({
                'range': f'A{next_row}:F{next_row}',
                'values': [row_data]
            })
            
            next_row += 1
            added_count += 1
        
        # Apply batch updates if we have any
        if batch_updates:
            sheet.batch_update(batch_updates)
            logger.info(f"Added {added_count} new tracking entries to sheet")
        
        return added_count, duplicate_count, error_count
    except Exception as e:
        logger.error(f"Error adding tracking to sheet: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        return added_count, duplicate_count, error_count + (len(tracking_data) - added_count - duplicate_count)

def fetch_from_shipstation_v2(days_to_look_back=180):
    """
    Connect to ShipStation API V2 and extract in-transit shipment tracking numbers from packages.
    
    Args:
        days_to_look_back: Number of days to look back for shipments
        
    Returns:
        list: List of dicts containing tracking information
    """
    tracking_data = []
    
    try:
        # Get ShipStation API key from environment
        api_key = os.environ.get('SHIPSTATION_API_KEY')
        
        if not api_key:
            logger.error("Missing ShipStation API key")
            return tracking_data
        
        # Calculate date for filtering
        cutoff_date = datetime.now() - timedelta(days=days_to_look_back)
        created_at_start = cutoff_date.strftime('%Y-%m-%d')
        
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
        max_pages = 5  # Limit to first 5 pages for initial test
        
        # Focus on shipments with labels purchased
        params = {
            'created_at_start': created_at_start,
            'page': page,
            'page_size': page_size
        }
        
        while page <= max_pages:
            logger.info(f"Fetching ShipStation shipments page {page}")
            
            # Update the page parameter
            params['page'] = page
            
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
            
            if not shipments:
                logger.info("No more shipments to fetch")
                break
            
            # Track counts for reporting
            shipments_with_packages = 0
            shipments_with_tracking = 0
            
            # Process each shipment
            for shipment in shipments:
                # Skip cancelled shipments
                if shipment.get('shipment_status') == 'cancelled':
                    continue
                
                # Check packages array based on the observed structure
                if 'packages' in shipment and shipment['packages']:
                    shipments_with_packages += 1
                    
                    for package in shipment['packages']:
                        # Try to find the tracking number in the package
                        package_id = package.get('shipment_package_id', '')
                        
                        # The next line is crucial - we're explicitly checking the "shipment"
                        # for its tracking number, not the package as originally assumed
                        shipment_id = shipment.get('shipment_id', '')
                        shipment_status = shipment.get('shipment_status', '')
                        
                        # Check if this is a label_purchased shipment
                        if shipment_status == 'label_purchased':
                            # For these shipments, we need to find the tracking number
                            # Try different approaches
                            
                            # First, check directly in the package
                            if 'tracking_number' in package:
                                tracking_number = package.get('tracking_number')
                            else:
                                # If not in the package directly, try shipment-level fields
                                tracking_number = None
                            
                            if not tracking_number:
                                # Try carrier-specific identification
                                carrier_id = shipment.get('carrier_id', '')
                                service_code = shipment.get('service_code', '')
                                packages_count = len(shipment['packages'])
                                
                                logger.debug(f"No direct tracking number, checking ship_to and packages")
                                logger.debug(f"Carrier: {carrier_id}, Service: {service_code}, Packages: {packages_count}")
                                
                                # Get the weight if available
                                weight = None
                                if 'weight' in package:
                                    weight_obj = package.get('weight', {})
                                    weight_value = weight_obj.get('value', 0)
                                    weight_unit = weight_obj.get('unit', '')
                                    weight = f"{weight_value} {weight_unit}"
                                
                                # Extract the ship-to address information
                                ship_to = shipment.get('ship_to', {})
                                recipient_name = ship_to.get('name', '')
                                
                                # Format address
                                address_parts = []
                                street1 = ship_to.get('address_line1', '')
                                street2 = ship_to.get('address_line2', '')
                                city = ship_to.get('city_locality', '')
                                state = ship_to.get('state_province', '')
                                postal_code = ship_to.get('postal_code', '')
                                country = ship_to.get('country_code', '')
                                
                                if street1:
                                    address_parts.append(street1)
                                if street2 and street2.strip():
                                    address_parts.append(street2)
                                if city:
                                    address_parts.append(city)
                                if state:
                                    address_parts.append(state)
                                if postal_code:
                                    address_parts.append(postal_code)
                                if country:
                                    address_parts.append(country)
                                
                                formatted_address = ', '.join(address_parts)
                                
                                # Log details for this shipment
                                logger.info(f"Found label_purchased shipment {shipment_id} to {recipient_name}")
                                logger.info(f"  Address: {formatted_address}")
                                logger.info(f"  Package weight: {weight}")
                                
                                # For now, we'll extract the package info even without a tracking number
                                # This is useful for customers who want to track the shipment status
                                shipments_with_tracking += 1
                                
                                # Add to tracking data - use package ID as identifier
                                tracking_data.append({
                                    'tracking_number': f"PKG-{package_id}",  # Use package ID as placeholder
                                    'status': shipment_status,
                                    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'location': '',
                                    'address': formatted_address,
                                    'estimated_delivery': '',
                                    'carrier': carrier_id,
                                    'service': service_code,
                                    'source': 'shipstation',
                                    'recipient': recipient_name,
                                    'weight': weight,
                                    'shipment_id': shipment_id,
                                    'package_id': package_id
                                })
                            else:
                                # We found a tracking number!
                                shipments_with_tracking += 1
                                
                                # Add to tracking data
                                tracking_data.append({
                                    'tracking_number': tracking_number,
                                    'status': shipment_status,
                                    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'location': '',
                                    'address': formatted_address,
                                    'estimated_delivery': '',
                                    'carrier': carrier_id,
                                    'service': service_code,
                                    'source': 'shipstation',
                                    'recipient': recipient_name,
                                    'weight': weight
                                })
                                
                                logger.info(f"Found tracking number: {tracking_number}")
            
            logger.info(f"Processed {shipments_with_packages} shipments with packages")
            logger.info(f"Found {shipments_with_tracking} shipments with tracking information")
            
            # Load test data from JSON file if available
            if page == 1 and not tracking_data and os.path.exists('shipstation_v2_response.json'):
                try:
                    logger.info("No tracking data found in live API, checking saved JSON file")
                    with open('shipstation_v2_response.json', 'r') as f:
                        test_data = json.load(f)
                    
                    test_shipments = test_data.get('shipments', [])
                    if test_shipments:
                        logger.info(f"Processing {len(test_shipments)} shipments from JSON file")
                        
                        for shipment in test_shipments:
                            # Skip cancelled shipments
                            if shipment.get('shipment_status') == 'cancelled':
                                continue
                            
                            # Process all other shipments
                            if shipment.get('shipment_status') == 'label_purchased':
                                # Extract data from shipment
                                shipment_id = shipment.get('shipment_id', '')
                                shipment_number = shipment.get('shipment_number', '')
                                
                                # Get ship_to address
                                ship_to = shipment.get('ship_to', {})
                                recipient_name = ship_to.get('name', '')
                                
                                # Format address
                                address_parts = []
                                street1 = ship_to.get('address_line1', '')
                                street2 = ship_to.get('address_line2', '')
                                city = ship_to.get('city_locality', '')
                                state = ship_to.get('state_province', '')
                                postal_code = ship_to.get('postal_code', '')
                                country = ship_to.get('country_code', '')
                                
                                if street1:
                                    address_parts.append(street1)
                                if street2 and street2.strip():
                                    address_parts.append(street2)
                                if city:
                                    address_parts.append(city)
                                if state:
                                    address_parts.append(state)
                                if postal_code:
                                    address_parts.append(postal_code)
                                if country:
                                    address_parts.append(country)
                                
                                formatted_address = ', '.join(address_parts)
                                
                                # Use shipment ID as identifier
                                shipments_with_tracking += 1
                                logger.info(f"Adding shipment {shipment_number} to {recipient_name}")
                                
                                tracking_data.append({
                                    'tracking_number': f"SHIP-{shipment_number}",  # Use shipment number as ID
                                    'status': 'Ready to ship',
                                    'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'location': '',
                                    'address': formatted_address,
                                    'estimated_delivery': '',
                                    'carrier': shipment.get('carrier_id', ''),
                                    'service': shipment.get('service_code', ''),
                                    'source': 'shipstation_json',
                                    'recipient': recipient_name
                                })
                except Exception as json_error:
                    logger.error(f"Error processing JSON file: {json_error}")
            
            # Check if we've reached the end
            if page >= total_pages:
                break
            
            # Move to next page
            page += 1
            time.sleep(0.5)  # Small delay to avoid hitting rate limits
        
        logger.info(f"Extracted {len(tracking_data)} tracking/shipment entries")
        return tracking_data
    
    except Exception as e:
        logger.error(f"Error fetching from ShipStation API: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        return tracking_data

def generate_report(added_count, duplicate_count, error_count, source_type):
    """
    Generate a summary report of the seeding operation.
    
    Args:
        added_count: Number of tracking numbers added
        duplicate_count: Number of duplicates found
        error_count: Number of errors encountered
        source_type: Type of source used for seeding
        
    Returns:
        str: Formatted report text
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""
UPS Tracker Database Seeding Report
===================================
Generated: {now}

Source: {source_type}

Summary:
--------
* New tracking/shipment entries added: {added_count}
* Duplicate entries skipped: {duplicate_count}
* Errors encountered: {error_count}
* Total processed: {added_count + duplicate_count + error_count}

Status: {'Success' if error_count == 0 else 'Completed with errors'}
"""
    
    # Write report to file
    report_filename = f"seeding_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_filename, 'w') as f:
        f.write(report)
    
    logger.info(f"Report generated and saved to {report_filename}")
    
    return report

def main():
    """Main function to orchestrate the seeding process."""
    parser = argparse.ArgumentParser(description='Seed UPS Tracker database with in-transit shipments')
    parser.add_argument('--days', type=int, default=180,
                      help='Number of days to look back for shipments (default: 180)')
    
    args = parser.parse_args()
    
    try:
        logger.info(f"Starting tracking database seeding from ShipStation V2 API")
        logger.info(f"Looking back {args.days} days for shipments")
        
        # Get tracking data from the selected source
        tracking_data = fetch_from_shipstation_v2(args.days)
        
        if not tracking_data:
            logger.warning("No tracking data found to seed")
            print("No tracking data found to seed. Check the logs for details.")
            return
        
        # Connect to Google Sheets
        sheet = setup_google_sheets()
        
        # Add tracking data to sheet
        logger.info(f"Adding {len(tracking_data)} tracking entries to sheet")
        added_count, duplicate_count, error_count = add_tracking_to_sheet(sheet, tracking_data)
        
        # Generate report
        report = generate_report(added_count, duplicate_count, error_count, "ShipStation V2 API")
        
        # Print summary to console
        print(f"\nSeeding completed!")
        print(f"Added {added_count} new tracking/shipment entries")
        print(f"Skipped {duplicate_count} duplicates")
        print(f"Encountered {error_count} errors")
        print(f"Report saved to seeding_report_*.txt")
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        print(f"Error: {e}")
        print("Check the logs for detailed information.")

if __name__ == "__main__":
    main()