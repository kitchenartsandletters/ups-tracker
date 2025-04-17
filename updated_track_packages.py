#!/usr/bin/env python3
"""
UPS Package Tracking to Google Sheets

This script:
1. Reads tracking numbers from a Google Sheet
2. Validates addresses using UPS Address Validation API
3. Sets up Track Alert API subscriptions for real-time updates
4. Queries the UPS Tracking API for each tracking number
5. Gets estimated Time in Transit information
6. Updates the Google Sheet with the latest tracking information
"""

import os
import base64
import json
import logging
import uuid
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
ALERT_COLUMN = 'G'       # Column for alert subscription status

# UPS API Base URLs
UPS_OAUTH_URL = 'https://onlinetools.ups.com/security/v1/oauth/token'
UPS_TRACK_URL = 'https://onlinetools.ups.com/api/track/v1/details/'
UPS_ADDRESS_URL = 'https://onlinetools.ups.com/api/addressvalidation/v1/1'
UPS_TIME_IN_TRANSIT_URL = 'https://onlinetools.ups.com/api/timeintransit/v1'
UPS_TRACK_ALERT_URL = 'https://onlinetools.ups.com/api/track/v1/alert/create'

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
        
        # Request headers
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        # Request body
        data = {
            'grant_type': 'client_credentials',
        }
        
        # Make the request
        response = requests.post(
            UPS_OAUTH_URL,
            headers=headers,
            data=data,
            auth=(client_id, client_secret)
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            logger.info("Successfully obtained UPS OAuth token")
            return access_token
        else:
            logger.error(f"Failed to get OAuth token: {response.status_code} - {response.text}")
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
        
        # Request headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'transId': f'track_{int(time.time())}',  # Unique transaction ID
            'transactionSrc': 'tracking'
        }
        
        # Make the request
        response = requests.get(tracking_url, headers=headers)
        
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
        # Request headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'transId': f'address_{uuid.uuid4()}',
            'transactionSrc': 'addressValidation'
        }
        
        # Request body
        data = {
            "XAVRequest": {
                "AddressKeyFormat": {
                    "AddressLine": address.get("street", ""),
                    "PoliticalDivision2": address.get("city", ""),
                    "PoliticalDivision1": address.get("state", ""),
                    "PostcodePrimaryLow": address.get("postal_code", ""),
                    "CountryCode": address.get("country", "US")
                }
            }
        }
        
        # Make the request
        response = requests.post(
            UPS_ADDRESS_URL,
            headers=headers,
            json=data
        )
        
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

def get_time_in_transit(origin, destination, access_token):
    """
    Get estimated time in transit using the UPS Time in Transit API.
    
    Args:
        origin: Origin address (dict with address details)
        destination: Destination address (dict with address details)
        access_token: OAuth access token for UPS API
        
    Returns:
        dict: Time in transit information or None if an error occurs
    """
    try:
        # Request headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'transId': f'time_{uuid.uuid4()}',
            'transactionSrc': 'timeInTransit'
        }
        
        # Current date in YYYY-MM-DD format
        ship_date = datetime.now().strftime("%Y-%m-%d")
        
        # Request body
        data = {
            "originAddress": {
                "city": origin.get("city", ""),
                "stateProvince": origin.get("state", ""),
                "postalCode": origin.get("postal_code", ""),
                "countryCode": origin.get("country", "US")
            },
            "destinationAddress": {
                "city": destination.get("city", ""),
                "stateProvince": destination.get("state", ""),
                "postalCode": destination.get("postal_code", ""),
                "countryCode": destination.get("country", "US")
            },
            "shipDate": ship_date,
            "shipTime": "12:00:00",
            "weight": {
                "weight": "1",
                "unitOfMeasurement": "LBS"
            }
        }
        
        # Make the request
        response = requests.post(
            UPS_TIME_IN_TRANSIT_URL,
            headers=headers,
            json=data
        )
        
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

def subscribe_to_tracking_alerts(tracking_number, email, access_token):
    """
    Subscribe to tracking alerts using the UPS Track Alert API.
    
    Args:
        tracking_number: The UPS tracking number
        email: Email address to receive notifications
        access_token: OAuth access token for UPS API
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Request headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'transId': f'alert_{uuid.uuid4()}',
            'transactionSrc': 'trackAlert'
        }
        
        # Request body
        data = {
            "TrackAlertRequest": {
                "Request": {
                    "RequestOption": "1",
                    "TransactionReference": {
                        "CustomerContext": f"Alert for {tracking_number}"
                    }
                },
                "AlertConfiguration": {
                    "Event": {
                        "Delivered": "01",
                        "Exception": "01",
                        "OutForDelivery": "01"
                    },
                    "EMailNotification": {
                        "EMailAddress": email,
                        "UndeliverableEMailAddress": email,
                        "FromEMailAddress": email,
                        "Subject": f"UPS Alert: Package {tracking_number} status update",
                        "Memo": "This is an automated alert from UPS Tracker"
                    },
                    "Locale": {
                        "Language": "ENG",
                        "Dialect": "US"
                    }
                },
                "InquiryNumber": tracking_number
            }
        }
        
        # Make the request
        response = requests.post(
            UPS_TRACK_ALERT_URL,
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            logger.info(f"Successfully subscribed to alerts for {tracking_number}")
            return True
        else:
            logger.error(f"Failed to subscribe to alerts: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error subscribing to alerts: {e}")
        return False

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
        
        # Create address dict for validation
        address_dict = {
            "street": "",  # Not always available in the tracking response
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
        address_key_format = validation_data.get('XAVResponse', {}).get('ValidAddressIndicator', {})
        
        if not address_key_format:
            # Try to get candidate addresses if exact match not found
            candidate = validation_data.get('XAVResponse', {}).get('Candidate', [{}])[0]
            if not candidate:
                return "Address could not be validated"
                
            # Use the first candidate
            address_lines = candidate.get('AddressKeyFormat', {}).get('AddressLine', [])
            city = candidate.get('AddressKeyFormat', {}).get('PoliticalDivision2', '')
            state = candidate.get('AddressKeyFormat', {}).get('PoliticalDivision1', '')
            postal = candidate.get('AddressKeyFormat', {}).get('PostcodePrimaryLow', '')
            country = candidate.get('AddressKeyFormat', {}).get('CountryCode', '')
        else:
            # Use the validated address
            validated = validation_data.get('XAVResponse', {}).get('AddressKeyFormat', {})
            address_lines = validated.get('AddressLine', [])
            city = validated.get('PoliticalDivision2', '')
            state = validated.get('PoliticalDivision1', '')
            postal = validated.get('PostcodePrimaryLow', '')
            country = validated.get('CountryCode', '')
        
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
            if 'GROUND' in service_name:
                best_service = service
                break
                
        # If no Ground service, use the first one
        if not best_service and services:
            best_service = services[0]
            
        if best_service:
            delivery_date = best_service.get('deliveryDate', '')
            delivery_time = best_service.get('deliveryTime', '')
            
            if delivery_date and delivery_time:
                return f"{delivery_date} by {delivery_time}"
            elif delivery_date:
                return delivery_date
                
        return "No estimated delivery time available"
    except Exception as e:
        logger.error(f"Error parsing time in transit: {e}")
        return "Error getting estimated delivery time"

def update_sheet_row(sheet, row, data):
    """
    Update a row in the Google Sheet with tracking information.
    
    Args:
        sheet: Google Sheet object
        row: Row number to update
        data: Dict containing update data
    """
    try:
        # Add current timestamp to show when the script ran
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update status
        if 'status' in data and data['status']:
            sheet.update(f'{STATUS_COLUMN}{row}', data['status'])
        
        # Update last_update
        if 'last_update' in data and data['last_update']:
            sheet.update(f'{UPDATE_COLUMN}{row}', f"{data['last_update']} (checked: {current_time})")
        
        # Update location
        if 'location' in data and data['location']:
            sheet.update(f'{LOCATION_COLUMN}{row}', data['location'])
            
        # Update validated_address
        if 'validated_address' in data and data['validated_address']:
            sheet.update(f'{ADDRESS_COLUMN}{row}', data['validated_address'])
            
        # Update estimated_delivery
        if 'estimated_delivery' in data and data['estimated_delivery']:
            sheet.update(f'{ETA_COLUMN}{row}', data['estimated_delivery'])
            
        # Update alert_status
        if 'alert_status' in data and data['alert_status'] is not None:
            status = "Subscribed" if data['alert_status'] else "Failed to subscribe"
            sheet.update(f'{ALERT_COLUMN}{row}', status)
            
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
                'Estimated Delivery', 
                'Alert Status'
            ]
            sheet.update('A1:G1', [headers])
            start_row = 2
        else:
            start_row = 2  # Skip header row
        
        # Get UPS OAuth token
        access_token = get_ups_oauth_token()
        if not access_token:
            logger.error("Failed to obtain UPS OAuth token. Exiting.")
            return
        
        # Get notification email from environment variable
        notification_email = os.environ.get('NOTIFICATION_EMAIL', '')
        
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
                update_data['validated_address'] = validated_address
                
                # If we have origin address (could be from a config or env var)
                origin_address = {
                    "city": os.environ.get('ORIGIN_CITY', ''),
                    "state": os.environ.get('ORIGIN_STATE', ''),
                    "postal_code": os.environ.get('ORIGIN_ZIP', ''),
                    "country": "US"
                }
                
                if any(origin_address.values()) and any(address_dict.values()):
                    time_data = get_time_in_transit(origin_address, address_dict, access_token)
                    estimated_delivery = parse_time_in_transit(time_data)
                    update_data['estimated_delivery'] = estimated_delivery
            
            # Subscribe to tracking alerts if email is provided
            if notification_email:
                alert_status = subscribe_to_tracking_alerts(tracking_number, notification_email, access_token)
                update_data['alert_status'] = alert_status
                
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