#!/usr/bin/env python3
"""
UPS Package Tracking to Google Sheets

This script:
1. Reads tracking numbers from a Google Sheet
2. Validates addresses using UPS Address Validation API
3. Queries the UPS Tracking API for each tracking number
4. Gets estimated delivery time using Time in Transit API
5. Updates the Google Sheet with the latest tracking information
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
SHEET_NAME = 'UPS Tracker'
TRACKING_COLUMN = 'A'    # Column for tracking numbers
STATUS_COLUMN = 'B'      # Column for status
UPDATE_COLUMN = 'C'      # Column for last update timestamp
LOCATION_COLUMN = 'D'    # Column for current location
ADDRESS_COLUMN = 'E'     # Column for validated address
ETA_COLUMN = 'F'         # Column for estimated delivery time

# UPS API Base URLs
UPS_OAUTH_URL = 'https://onlinetools.ups.com/security/v1/oauth/token'
UPS_TRACK_URL = 'https://onlinetools.ups.com/api/track/v1/details/'
UPS_ADDRESS_URL = 'https://onlinetools.ups.com/api/addressvalidation/v1/1'
UPS_TIME_IN_TRANSIT_URL = 'https://onlinetools.ups.com/api/timeintransit/v1'

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

def get_ups_oauth_token():
    """Get OAuth token from UPS API."""
    try:
        client_id = os.environ['UPS_CLIENT_ID']
        client_secret = os.environ['UPS_CLIENT_SECRET']
        
        # Log credential information (mask most of it for security)
        if client_id:
            masked_id = client_id[:4] + '*' * (len(client_id) - 4) if len(client_id) > 4 else '****'
            logger.info(f"Using Client ID: {masked_id}")
        else:
            logger.error("UPS_CLIENT_ID is empty or not set")
            
        if client_secret:
            logger.info(f"Client Secret is set (length: {len(client_secret)})")
        else:
            logger.error("UPS_CLIENT_SECRET is empty or not set")
        
        # Request headers
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        # Request body
        data = {
            'grant_type': 'client_credentials',
        }
        
        logger.info("Sending OAuth token request...")
        
        # Make the request
        response = requests.post(
            UPS_OAUTH_URL,
            headers=headers,
            data=data,
            auth=(client_id, client_secret)
        )
        
        logger.info(f"OAuth response status code: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 'unknown')
            logger.info(f"Successfully obtained UPS OAuth token (expires in {expires_in} seconds)")
            
            # Mask token for security in logs
            if access_token:
                masked_token = access_token[:10] + '*' * 10 + access_token[-5:] if len(access_token) > 25 else '****'
                logger.info(f"Token: {masked_token}")
                return access_token
            else:
                logger.error("Access token not found in response")
                return None
        else:
            logger.error(f"Failed to get OAuth token: {response.status_code} - {response.text}")
            return None
    except KeyError as e:
        logger.error(f"Environment variable not set: {e}")
        return None
    except Exception as e:
        logger.error(f"Error obtaining UPS OAuth token: {e}")
        return None

def get_tracking_info(tracking_number, access_token):
    """
    Query the UPS Tracking API for a specific tracking number.
    
    Args:
        tracking_number: The UPS tracking number
        access_token: OAuth access token for UPS API
        
    Returns:
        dict: Tracking information or None if an error occurs
    """
    try:
        # UPS Tracking API endpoint
        tracking_url = UPS_TRACK_URL + tracking_number
        logger.info(f"Using Tracking API URL: {tracking_url}")
        
        # Request headers
        trans_id = f'track_{int(time.time())}'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'transId': trans_id,
            'transactionSrc': 'tracking'
        }
        
        logger.info(f"Using transaction ID: {trans_id}")
        logger.info(f"Sending tracking request for: {tracking_number}")
        
        # Make the request
        response = requests.get(tracking_url, headers=headers)
        
        logger.info(f"Tracking API response status: {response.status_code}")
        
        if response.status_code == 200:
            tracking_data = response.json()
            logger.info(f"Successfully retrieved tracking info for {tracking_number}")
            return tracking_data
        else:
            logger.error(f"Failed to get tracking info for {tracking_number}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error getting tracking info for {tracking_number}: {e}")
        return None

def validate_address(address, access_token):
    """
    Validate an address using the UPS Address Validation API.
    
    Args:
        address: Address to validate (dict with street, city, state, postal_code)
        access_token: OAuth access token for UPS API
        
    Returns:
        dict: Validated address information or None if an error occurs
    """
    try:
        # Enhanced address information with default values to avoid missing fields
        enhanced_address = {
            "AddressLine": address.get("street", ""),
            "PoliticalDivision2": address.get("city", ""),
            "PoliticalDivision1": address.get("state", ""),
            "PostcodePrimaryLow": address.get("postal_code", ""),
            "CountryCode": address.get("country", "US")
        }
        
        # Only proceed if we have at least some address information
        if not any(enhanced_address.values()):
            logger.warning("No address information available for validation")
            return None
            
        # Request headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'transId': f'address_{int(time.time())}',
            'transactionSrc': 'addressValidation'
        }
        
        # Request body - enhanced with more fields to meet API requirements
        data = {
            "XAVRequest": {
                "AddressKeyFormat": enhanced_address,
                "RegionalRequestIndicator": "",
                "MaximumCandidateListSize": "10"
            }
        }
        
        logger.info(f"Validating address: {json.dumps(enhanced_address)}")
        
        # Make the request
        response = requests.post(
            UPS_ADDRESS_URL,
            headers=headers,
            json=data
        )
        
        logger.info(f"Address Validation API response status: {response.status_code}")
        
        if response.status_code == 200:
            validation_data = response.json()
            logger.info(f"Successfully validated address")
            return validation_data
        else:
            logger.error(f"Failed to validate address: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error validating address: {e}")
        return None

# Improved Time in Transit function
def get_time_in_transit(origin, destination, access_token):
    """
    Get estimated time in transit using the UPS Time in Transit API.
    Enhanced with better logging and validation.
    
    Args:
        origin: Origin address (dict with address details)
        destination: Destination address (dict with address details)
        access_token: OAuth access token for UPS API
        
    Returns:
        dict: Time in transit information or None if an error occurs
    """
    try:
        # Log what we have
        logger.info(f"Origin data: {origin}")
        logger.info(f"Destination data: {destination}")
        
        # Check if we have the minimum required fields
        origin_postal = origin.get("postal_code")
        dest_postal = destination.get("postal_code")
        
        if not origin_postal:
            logger.error("Missing origin postal code for time in transit calculation")
            return None
            
        if not dest_postal:
            logger.error("Missing destination postal code for time in transit calculation")
            return None
            
        # Request headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'transId': f'time_{int(time.time())}',
            'transactionSrc': 'timeInTransit'
        }
        
        # Current date in YYYY-MM-DD format
        ship_date = datetime.now().strftime("%Y-%m-%d")
        
        # Enhanced request body with more details
        data = {
            "originAddress": {
                "addressLine": origin.get("street", ""),
                "city": origin.get("city", ""),
                "stateProvince": origin.get("state", ""),
                "postalCode": origin_postal,
                "countryCode": origin.get("country", "US")
            },
            "destinationAddress": {
                "addressLine": destination.get("street", ""),
                "city": destination.get("city", ""),
                "stateProvince": destination.get("state", ""),
                "postalCode": dest_postal,
                "countryCode": destination.get("country", "US")
            },
            "shipDate": ship_date,
            "shipTime": "12:00:00",
            "weight": {
                "weight": "1",
                "unitOfMeasurement": "LBS"
            },
            "totalPackagesInShipment": "1"
        }
        
        logger.info(f"Requesting time in transit estimate from {origin_postal} to {dest_postal}")
        logger.info(f"Request data: {json.dumps(data)}")
        
        # Make the request
        response = requests.post(
            UPS_TIME_IN_TRANSIT_URL,
            headers=headers,
            json=data
        )
        
        logger.info(f"Time in Transit API response status: {response.status_code}")
        logger.info(f"Time in Transit API response body: {response.text}")
        
        if response.status_code == 200:
            time_data = response.json()
            logger.info(f"Successfully retrieved time in transit information")
            return time_data
        else:
            logger.error(f"Failed to get time in transit: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error getting time in transit: {e}")
        return None

def parse_tracking_response(tracking_data):
    """
    Parse the UPS Tracking API response to extract relevant information.
    
    Args:
        tracking_data: The API response from UPS
        
    Returns:
        tuple: (status, last_update, location, address) or (None, None, None, None) if parsing fails
    """
    try:
        if not tracking_data:
            return None, None, None, None
            
        # Extract package information
        package = tracking_data.get('trackResponse', {}).get('shipment', [{}])[0].get('package', [{}])[0]
        
        # Get status
        activity = package.get('activity', [{}])[0]
        status = activity.get('status', {}).get('description', 'Unknown')
        
        # Get last update time
        date = activity.get('date', '')
        time_str = activity.get('time', '')
        last_update = f"{date} {time_str}" if date and time_str else 'Unknown'
        
        # Get location
        location_info = activity.get('location', {})
        address = location_info.get('address', {})
        
        city = address.get('city', '')
        state = address.get('stateProvince', '')
        country = address.get('country', '')
        postal_code = address.get('postalCode', '')
        
        location_parts = [part for part in [city, state, country] if part]
        location = ', '.join(location_parts) if location_parts else 'Unknown'
        
        # Try to get street address from shipment information if available
        try:
            shipment = tracking_data.get('trackResponse', {}).get('shipment', [{}])[0]
            ship_to = shipment.get('shipTo', {})
            street = ship_to.get('address', {}).get('addressLine', '')
            
            # If not available in shipTo, try other locations
            if not street and shipment.get('package'):
                delivery_detail = shipment.get('package', [{}])[0].get('deliveryDetail', {})
                street = delivery_detail.get('addressLine', '')
        except:
            street = ""
        
        # Create address dict for validation with enhanced information
        address_dict = {
            "street": street,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country
        }
        
        return status, last_update, location, address_dict
    except Exception as e:
        logger.error(f"Error parsing tracking response: {e}")
        return None, None, None, None

def parse_validated_address(validation_data):
    """
    Parse the UPS Address Validation API response.
    
    Args:
        validation_data: The API response from UPS
        
    Returns:
        str: Formatted address or None if parsing fails
    """
    try:
        if not validation_data:
            return None
            
        # Extract address information
        valid_indicator = validation_data.get('XAVResponse', {}).get('ValidAddressIndicator')
        
        if valid_indicator:
            # Use the validated address
            validated = validation_data.get('XAVResponse', {}).get('AddressKeyFormat', {})
            address_lines = validated.get('AddressLine', [])
            city = validated.get('PoliticalDivision2', '')
            state = validated.get('PoliticalDivision1', '')
            postal = validated.get('PostcodePrimaryLow', '')
            country = validated.get('CountryCode', '')
        else:
            # Try to get candidate addresses if exact match not found
            candidates = validation_data.get('XAVResponse', {}).get('Candidate', [])
            if not candidates:
                return "Address could not be validated"
                
            # Use the first candidate
            candidate = candidates[0]
            address_lines = candidate.get('AddressKeyFormat', {}).get('AddressLine', [])
            city = candidate.get('AddressKeyFormat', {}).get('PoliticalDivision2', '')
            state = candidate.get('AddressKeyFormat', {}).get('PoliticalDivision1', '')
            postal = candidate.get('AddressKeyFormat', {}).get('PostcodePrimaryLow', '')
            country = candidate.get('AddressKeyFormat', {}).get('CountryCode', '')
        
        # Format the address
        formatted_address = ""
        if address_lines:
            if isinstance(address_lines, list):
                formatted_address += ", ".join(address_lines)
            else:
                formatted_address += address_lines
            
        location_parts = [part for part in [city, state, postal, country] if part]
        if location_parts:
            if formatted_address:
                formatted_address += ", "
            formatted_address += ", ".join(location_parts)
            
        return formatted_address or "Address could not be validated"
    except Exception as e:
        logger.error(f"Error parsing validated address: {e}")
        return "Error validating address"

def parse_time_in_transit(time_data):
    """
    Parse the UPS Time in Transit API response.
    
    Args:
        time_data: The API response from UPS
        
    Returns:
        str: Estimated delivery time or None if parsing fails
    """
    try:
        if not time_data:
            return None
            
        # Extract service information
        services = time_data.get('timeInTransitResponse', {}).get('services', [])
        
        if not services:
            return "No estimated delivery time available"
            
        # Find the UPS Ground or lowest cost service
        best_service = None
        for service in services:
            service_name = service.get('serviceName', '')
            if 'GROUND' in service_name.upper():
                best_service = service
                break
                
        # If no Ground service, use the first one
        if not best_service and services:
            best_service = services[0]
            
        if best_service:
            delivery_date = best_service.get('deliveryDate', '')
            delivery_time = best_service.get('deliveryTime', '')
            service_name = best_service.get('serviceName', '')
            
            if delivery_date and delivery_time:
                return f"{service_name}: {delivery_date} by {delivery_time}"
            elif delivery_date:
                return f"{service_name}: {delivery_date}"
                
        return "No estimated delivery time available"
    except Exception as e:
        logger.error(f"Error parsing time in transit: {e}")
        return "Error getting estimated delivery time"

# Function to fix Google Sheets update method
def update_sheet_row(sheet, row, data):
    """
    Update a row in the Google Sheet with tracking information.
    Uses the current recommended gspread method to avoid deprecation warnings.
    
    Args:
        sheet: Google Sheet object
        row: Row number to update
        data: Dict containing update data
    """
    try:
        # Add current timestamp to show when the script ran
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare all updates as a batch instead of individual calls
        # This also avoids the deprecation warnings
        updates = []
        
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
                'values': [[f"{data['last_update']} (checked: {current_time})"]]
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
            updates.append({
                'range': f'{ETA_COLUMN}{row}',
                'values': [[data['estimated_delivery']]]
            })
        
        # If we have updates, apply them as a batch
        if updates:
            sheet.batch_update(updates)
            logger.info(f"Updated row {row} with latest tracking information")
        
    except Exception as e:
        logger.error(f"Error updating sheet row {row}: {e}")

def main():
    """Main function to orchestrate the tracking process."""
    try:
        logger.info("Starting UPS package tracking script")
        
        # Set up Google Sheets connection
        sheet = setup_google_sheets()
        
        # Get sheet values
        all_values = sheet.get_all_values()
        
        # Check if we need to add header row
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
            start_row = 2
        else:
            start_row = 2  # Skip header row
        
        # Get UPS OAuth token
        access_token = get_ups_oauth_token()
        if not access_token:
            logger.error("Failed to obtain UPS OAuth token. Exiting.")
            return
            
        # Get origin address from environment variables
        origin_address = {
            "street": os.environ.get('ORIGIN_STREET', ''),
            "city": os.environ.get('ORIGIN_CITY', ''),
            "state": os.environ.get('ORIGIN_STATE', ''),
            "postal_code": os.environ.get('ORIGIN_ZIP', ''),
            "country": "US"
        }
        
        # Log the origin address details
        if any(origin_address.values()):
            logger.info(f"Origin address details:")
            logger.info(f"  Street: {origin_address.get('street', 'Not set')}")
            logger.info(f"  City: {origin_address.get('city', 'Not set')}")
            logger.info(f"  State: {origin_address.get('state', 'Not set')}")
            logger.info(f"  Postal code: {origin_address.get('postal_code', 'Not set')}")
        else:
            logger.warning("No origin address provided for time-in-transit calculations")
        
        # Process each tracking number
        for i, row in enumerate(all_values[start_row-1:], start=start_row):
            # Skip empty rows
            if not row or not row[0]:
                continue
                
            tracking_number = row[0].strip()
            logger.info(f"Processing tracking number: {tracking_number}")
            
            # Get tracking information
            tracking_info = get_tracking_info(tracking_number, access_token)
            
            # Parse tracking response
            status, last_update, location, address_dict = parse_tracking_response(tracking_info)
            
            # Update data dictionary
            update_data = {
                'status': status,
                'last_update': last_update,
                'location': location
            }
            
            # Validate address if we have one
            if address_dict and any(address_dict.values()):
                validation_data = validate_address(address_dict, access_token)
                validated_address = parse_validated_address(validation_data)
                if validated_address:
                    update_data['validated_address'] = validated_address
                
                # If we have origin address with postal code, estimate transit time
                if origin_address.get('postal_code') and address_dict.get('postal_code'):
                    time_data = get_time_in_transit(origin_address, address_dict, access_token)
                    if time_data:
                        estimated_delivery = parse_time_in_transit(time_data)
                        if estimated_delivery:
                            update_data['estimated_delivery'] = estimated_delivery
                    else:
                        logger.warning(f"Unable to get time in transit estimate for {tracking_number}")
            
            # Update sheet
            if update_data:
                update_sheet_row(sheet, i, update_data)
            else:
                logger.warning(f"No valid tracking information found for {tracking_number}")
                
            # Add a small delay to avoid API rate limits
            time.sleep(1)
            
        logger.info("Tracking script completed successfully")
    except Exception as e:
        logger.error(f"Error in main function: {e}")

if __name__ == "__main__":
    main()