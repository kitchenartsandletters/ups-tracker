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
    Enhanced to include query parameters from the example.
    
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
        
        # Query parameters based on the example
        query_params = {
            "locale": "en_US",
            "returnSignature": "false",
            "returnMilestones": "false",
            "returnPOD": "false"
        }
        
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
        
        # Make the request with query parameters
        response = requests.get(
            tracking_url, 
            headers=headers,
            params=query_params
        )
        
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
    Simplified with better error handling.
    
    Args:
        address: Address to validate (dict with street, city, state, postal_code)
        access_token: OAuth access token for UPS API
        
    Returns:
        dict: Validated address information or None if an error occurs
    """
    try:
        # Log the address we're trying to validate
        logger.info(f"Attempting to validate address: {json.dumps(address)}")
        
        # Check if we have enough address information to validate
        if not any([address.get(key) for key in ["postal_code", "city", "state"]]):
            logger.warning("Not enough address information to validate")
            return None
            
        # Enhanced address information with default values
        enhanced_address = {
            "AddressLine": address.get("street", ""),
            "PoliticalDivision2": address.get("city", ""),
            "PoliticalDivision1": address.get("state", ""),
            "PostcodePrimaryLow": address.get("postal_code", ""),
            "CountryCode": address.get("country", "US")
        }
        
        # Request headers
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'transId': f'address_{int(time.time())}',
            'transactionSrc': 'addressValidation'
        }
        
        # Request body
        data = {
            "XAVRequest": {
                "AddressKeyFormat": enhanced_address,
                "RegionalRequestIndicator": "",
                "MaximumCandidateListSize": "10"
            }
        }
        
        logger.info(f"Validation request data: {json.dumps(data)}")
        
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
        import traceback
        logger.error(f"Validation error details: {traceback.format_exc()}")
        return None

# Improved Time in Transit function
def get_time_in_transit(origin, destination, access_token):
    """
    Get estimated time in transit using the UPS Time in Transit API.
    Updated to match the exact format shown in the UPS example.
    
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
            'transactionSrc': 'tracking'
        }
        
        # Current date in YYYY-MM-DD format
        ship_date = datetime.now().strftime("%Y-%m-%d")
        
        # Format the request exactly as in the example
        data = {
            "originCountryCode": origin.get("country", "US"),
            "originStateProvince": origin.get("state", ""),
            "originCityName": origin.get("city", ""),
            "originTownName": "",
            "originPostalCode": origin_postal,
            "destinationCountryCode": destination.get("country", "US"),
            "destinationStateProvince": destination.get("state", ""),
            "destinationCityName": destination.get("city", ""),
            "destinationTownName": "",
            "destinationPostalCode": dest_postal,
            "weight": "1.0",
            "weightUnitOfMeasure": "LBS",
            "shipmentContentsValue": "1.0",
            "shipmentContentsCurrencyCode": "USD",
            "billType": "03",
            "shipDate": ship_date,
            "shipTime": "",
            "residentialIndicator": "",
            "numberOfPackages": "1"
        }
        
        logger.info(f"Requesting time in transit estimate from {origin_postal} to {dest_postal}")
        logger.info(f"Request data: {json.dumps(data)}")
        
        # Use the correct endpoint URL based on the example
        transit_url = "https://onlinetools.ups.com/api/shipments/v1/transittimes"
        
        # Make the request
        response = requests.post(
            transit_url,
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
        import traceback
        logger.error(f"Detailed exception: {traceback.format_exc()}")
        return None

def parse_tracking_response(tracking_data):
    """
    Parse the UPS Tracking API response to extract relevant information.
    Enhanced to specifically extract delivery date information with human-friendly formatting.
    
    Args:
        tracking_data: The API response from UPS
        
    Returns:
        tuple: (status, last_update, location, address, delivery_estimate) or (None, None, None, None, None) if parsing fails
    """
    try:
        if not tracking_data:
            return None, None, None, None, None
            
        # Log the tracking data structure for debugging
        logger.info(f"Parsing tracking data response")
        
        # Extract package information
        shipment = tracking_data.get('trackResponse', {}).get('shipment', [{}])[0]
        package = shipment.get('package', [{}])[0]
        
        # Get status
        activity = package.get('activity', [{}])[0]
        status = activity.get('status', {}).get('description', 'Unknown')
        
        # Get last update time - with better formatting
        date = activity.get('date', '')
        time_str = activity.get('time', '')
        
        # Format the date and time for readability
        formatted_date = format_ups_date(date)
        formatted_time = format_ups_time(time_str)
        
        if formatted_date and formatted_time:
            last_update = f"{formatted_date} at {formatted_time}"
        elif formatted_date:
            last_update = formatted_date
        else:
            last_update = 'Unknown'
        
        # Get location
        location_info = activity.get('location', {})
        address = location_info.get('address', {})
        
        city = address.get('city', '')
        state = address.get('stateProvince', '')
        country = address.get('country', '')
        postal_code = address.get('postalCode', '')
        
        location_parts = [part for part in [city, state, country] if part]
        location = ', '.join(location_parts) if location_parts else 'Unknown'
        
        # Extract street address if available
        street = ""
        ship_to = shipment.get('shipTo', {})
        if ship_to:
            ship_to_address = ship_to.get('address', {})
            if ship_to_address:
                street_lines = ship_to_address.get('addressLine', [])
                if isinstance(street_lines, list) and street_lines:
                    street = street_lines[0]
                elif isinstance(street_lines, str):
                    street = street_lines
        
        # Create address dict for validation
        address_dict = {
            "street": street,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country
        }
        
        # Extract delivery date information - primary focus
        delivery_estimate = None
        
        # Check multiple places for delivery date information
        
        # 1. Check the deliveryDate object if present
        delivery_dates = package.get('deliveryDate', [])
        if delivery_dates:
            for delivery_date_obj in delivery_dates:
                date = delivery_date_obj.get('date', '')
                type_code = delivery_date_obj.get('type', '')
                
                # Log what we found
                logger.info(f"Found delivery date: {date}, type: {type_code}")
                
                if date:
                    # Format date to be human-readable
                    formatted_delivery_date = format_ups_date(date)
                    delivery_estimate = formatted_delivery_date
                    break
        
        # 2. If not found, check deliveryTime object
        if not delivery_estimate:
            delivery_time = package.get('deliveryTime', {})
            if delivery_time:
                date_type = delivery_time.get('type', '')
                start_time = delivery_time.get('startTime', '')
                end_time = delivery_time.get('endTime', '')
                
                logger.info(f"Found delivery time: type={date_type}, start={start_time}, end={end_time}")
                
                if date_type and (start_time or end_time):
                    if date_type == 'EDW' and start_time and end_time:
                        # Format time for better readability
                        start_formatted = format_ups_time(start_time)
                        end_formatted = format_ups_time(end_time)
                        delivery_estimate = f"{start_formatted} - {end_formatted}"
                    elif date_type == 'CMT' and end_time:
                        end_formatted = format_ups_time(end_time)
                        delivery_estimate = f"By {end_formatted}"
        
        # 3. If still not found, check package status for delivery information
        if not delivery_estimate and 'SCHEDULED DELIVERY' in status.upper():
            # Extract date from status if possible
            import re
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', status)
            if date_match:
                delivery_date = date_match.group(1)
                # Try to convert MM/DD/YY format to more readable
                try:
                    parts = delivery_date.split('/')
                    if len(parts) == 3:
                        month_num = int(parts[0])
                        day = int(parts[1])
                        year = parts[2]
                        if len(year) == 2:
                            year = "20" + year  # Assume 21st century
                        
                        month_names = ["January", "February", "March", "April", "May", "June", 
                                      "July", "August", "September", "October", "November", "December"]
                        month_name = month_names[month_num - 1] if 1 <= month_num <= 12 else ""
                        
                        if month_name:
                            delivery_estimate = f"{month_name} {day}, {year}"
                        else:
                            delivery_estimate = delivery_date
                    else:
                        delivery_estimate = delivery_date
                except:
                    delivery_estimate = delivery_date
        
        # If we found a delivery estimate, log it
        if delivery_estimate:
            logger.info(f"Extracted delivery estimate: {delivery_estimate}")
        else:
            logger.warning("No delivery estimate found in tracking data")
        
        return status, last_update, location, address_dict, delivery_estimate
    except Exception as e:
        logger.error(f"Error parsing tracking response: {e}")
        import traceback
        logger.error(f"Parse error details: {traceback.format_exc()}")
        return None, None, None, None, None

def parse_validated_address(validation_data):
    """
    Parse the UPS Address Validation API response.
    Super-simplified with robust error handling.
    
    Args:
        validation_data: The API response from UPS
        
    Returns:
        str: Formatted address or None if parsing fails
    """
    try:
        # First check if we have valid data
        if not validation_data or not isinstance(validation_data, dict):
            logger.warning(f"Invalid validation data type: {type(validation_data)}")
            return None
            
        # Just return a simple status message instead of trying to parse the complex structure
        logger.info("Address validation response received")
        
        # Check for XAVResponse key
        if 'XAVResponse' in validation_data:
            # Success!
            return "Address validated by UPS"
        elif 'response' in validation_data and 'errors' in validation_data.get('response', {}):
            # Error response
            return "Address validation error"
        else:
            # Unknown format
            return "Address validation completed"
            
    except Exception as e:
        logger.error(f"Error parsing validated address: {e}")
        import traceback
        logger.error(f"Parser error details: {traceback.format_exc()}")
        return "Error during address validation"

def parse_time_in_transit(time_data):
    """
    Parse the UPS Time in Transit API response.
    Updated to match the expected format.
    
    Args:
        time_data: The API response from UPS
        
    Returns:
        str: Estimated delivery time or None if parsing fails
    """
    try:
        if not time_data:
            return None
            
        logger.info(f"Parsing time in transit data: {json.dumps(time_data)}")
            
        # First check for error responses
        if 'response' in time_data and 'errors' in time_data.get('response', {}):
            errors = time_data['response']['errors']
            logger.error(f"Error in time in transit response: {errors}")
            return "Error getting delivery estimate"
            
        # Check for the services list based on the sample provided
        services = time_data.get('services', [])
        
        if not services:
            logger.warning("No services found in time in transit response")
            return "No estimated delivery time available"
            
        # Log what services were returned
        logger.info(f"Found {len(services)} service options")
        for i, service in enumerate(services):
            logger.info(f"Service {i+1}: {service.get('serviceLevelDescription', 'Unknown')} - {service.get('estimatedArrival', {}).get('date', 'Unknown')}")
            
        # Find the UPS Ground or lowest cost service
        best_service = None
        for service in services:
            service_desc = service.get('serviceLevelDescription', '')
            if 'GROUND' in service_desc.upper():
                best_service = service
                break
                
        # If no Ground service, use the first one
        if not best_service and services:
            best_service = services[0]
            
        if best_service:
            service_desc = best_service.get('serviceLevelDescription', 'Unknown Service')
            estimated_arrival = best_service.get('estimatedArrival', {})
            delivery_date = estimated_arrival.get('date', '')
            delivery_time = estimated_arrival.get('time', '')
            
            if delivery_date and delivery_time:
                return f"{service_desc}: {delivery_date} by {delivery_time}"
            elif delivery_date:
                return f"{service_desc}: {delivery_date}"
                
        return "No estimated delivery time available"
    except Exception as e:
        logger.error(f"Error parsing time in transit: {e}")
        import traceback
        logger.error(f"Detailed exception: {traceback.format_exc()}")
        return "Error getting estimated delivery time"

def format_ups_date(date_str):
    """
    Format UPS date strings to be more human-readable.
    Converts formats like "20250418" to "April 18, 2025"
    
    Args:
        date_str: UPS format date string
        
    Returns:
        str: Human-readable date
    """
    try:
        if not date_str or len(date_str) < 8:
            return date_str
            
        # Check if it's in the format YYYYMMDD
        if len(date_str) >= 8 and date_str.isdigit():
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            
            # Convert month number to name
            month_names = ["January", "February", "March", "April", "May", "June", 
                           "July", "August", "September", "October", "November", "December"]
            try:
                month_num = int(month)
                if 1 <= month_num <= 12:
                    month_name = month_names[month_num - 1]
                    return f"{month_name} {int(day)}, {year}"
            except:
                pass
                
        # For other formats, return as is
        return date_str
    except Exception as e:
        logger.error(f"Error formatting date {date_str}: {e}")
        return date_str

def format_ups_time(time_str):
    """
    Format UPS time strings to be more human-readable.
    Converts formats like "095158" to "9:51 AM"
    
    Args:
        time_str: UPS format time string (HHMMSS in 24h format)
        
    Returns:
        str: Human-readable time
    """
    try:
        if not time_str or len(time_str) < 6:
            return time_str
            
        # Check if it's in the format HHMMSS
        if len(time_str) >= 6 and time_str.isdigit():
            hour = int(time_str[:2])
            minute = time_str[2:4]
            
            # Convert to 12-hour format with AM/PM
            am_pm = "AM" if hour < 12 else "PM"
            hour_12 = hour if hour <= 12 else hour - 12
            hour_12 = 12 if hour_12 == 0 else hour_12  # Convert 0 to 12 for 12 AM
            
            return f"{hour_12}:{minute} {am_pm}"
                
        # For other formats, return as is
        return time_str
    except Exception as e:
        logger.error(f"Error formatting time {time_str}: {e}")
        return time_str

# Function to fix Google Sheets update method
def update_sheet_row(sheet, row, data):
    """
    Update a row in the Google Sheet with tracking information.
    Uses the current recommended gspread method to avoid deprecation warnings.
    Also formats the "Last Update" date for better readability.
    
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
        
        # Update last_update - format "checked" time more clearly
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
            
        # Update estimated_delivery - remove prefix as requested
        if 'estimated_delivery' in data and data['estimated_delivery']:
            # Remove "Estimated delivery: " prefix if present
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
        
        # Log origin address details
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
            
            # Parse tracking response - now includes delivery_estimate
            status, last_update, location, address_dict, delivery_estimate = parse_tracking_response(tracking_info)
            
            # Update data dictionary
            update_data = {
                'status': status,
                'last_update': last_update,
                'location': location
            }
            
            # Add delivery estimate from tracking data if available
            if delivery_estimate:
                update_data['estimated_delivery'] = delivery_estimate
                logger.info(f"Using delivery estimate from tracking data: {delivery_estimate}")
            
            # Validate address if we have one
            if address_dict and any(address_dict.values()):
                validation_data = validate_address(address_dict, access_token)
                validated_address = parse_validated_address(validation_data)
                if validated_address:
                    update_data['validated_address'] = validated_address
                
                # Only try time in transit if we don't already have a delivery estimate
                if not delivery_estimate and origin_address.get('postal_code') and address_dict.get('postal_code'):
                    logger.info("No delivery estimate from tracking data, trying Time in Transit API")
                    time_data = get_time_in_transit(origin_address, address_dict, access_token)
                    if time_data:
                        estimated_delivery = parse_time_in_transit(time_data)
                        if estimated_delivery:
                            update_data['estimated_delivery'] = estimated_delivery
                            logger.info(f"Using delivery estimate from Time in Transit API: {estimated_delivery}")
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
        import traceback
        logger.error(f"Main function error details: {traceback.format_exc()}")

if __name__ == "__main__":
    main()