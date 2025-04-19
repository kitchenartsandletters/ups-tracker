#!/usr/bin/env python3
"""
Carrier API Module

This module provides a standardized interface for tracking packages
across multiple carriers (UPS, USPS, DHL).
"""

import os
import logging
import requests
import json
import time
import re
from abc import ABC, abstractmethod
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class CarrierAPI(ABC):
    """Abstract base class for carrier APIs."""
    
    @abstractmethod
    def get_tracking_info(self, tracking_number):
        """
        Retrieve tracking information for a package.
        
        Args:
            tracking_number (str): The tracking number to track
            
        Returns:
            dict: Standardized tracking information
        """
        pass
    
    @abstractmethod
    def validate_address(self, address):
        """
        Validate a delivery address.
        
        Args:
            address (dict): Address information to validate
            
        Returns:
            dict: Validation response
        """
        pass
    
    @abstractmethod
    def get_estimated_delivery(self, origin, destination):
        """
        Get estimated delivery time.
        
        Args:
            origin (dict): Origin address
            destination (dict): Destination address
            
        Returns:
            dict: Delivery time estimate information
        """
        pass
    
    def format_api_date(self, date_str):
        """
        Format date strings to be human-readable.
        
        Args:
            date_str (str): Date string in carrier format
            
        Returns:
            str: Human-readable date string
        """
        # Default implementation returns as-is
        return date_str
    
    def format_api_time(self, time_str):
        """
        Format time strings to be human-readable.
        
        Args:
            time_str (str): Time string in carrier format
            
        Returns:
            str: Human-readable time string
        """
        # Default implementation returns as-is
        return time_str
    
    def standardize_response(self, tracking_data, status=None, last_update=None, 
                             location=None, address=None, delivery_estimate=None,
                             carrier_name=None):
        """
        Standardize API response format across carriers.
        
        Args:
            tracking_data (dict): Raw tracking data
            status (str): Package status
            last_update (str): Last update timestamp
            location (str): Current location
            address (dict): Address information
            delivery_estimate (str): Estimated delivery time
            carrier_name (str): Name of the carrier
            
        Returns:
            dict: Standardized tracking information
        """
        return {
            'tracking_data': tracking_data,
            'status': status,
            'last_update': last_update,
            'location': location,
            'address': address,
            'delivery_estimate': delivery_estimate,
            'carrier': carrier_name or self.get_carrier_name()
        }
    
    def get_carrier_name(self):
        """Get the name of the carrier."""
        return self.__class__.__name__.replace('Api', '')

class UPSApi(CarrierAPI):
    """UPS API implementation."""
    
    # UPS API Base URLs
    UPS_OAUTH_URL = 'https://onlinetools.ups.com/security/v1/oauth/token'
    UPS_TRACK_URL = 'https://onlinetools.ups.com/api/track/v1/details/'
    UPS_ADDRESS_URL = 'https://onlinetools.ups.com/api/addressvalidation/v1/1'
    UPS_TIME_IN_TRANSIT_URL = 'https://onlinetools.ups.com/api/timeintransit/v1'
    
    def __init__(self):
        """Initialize the UPS API client."""
        self.access_token = None
        
    def get_oauth_token(self):
        """Get OAuth token from UPS API."""
        try:
            client_id = os.environ.get('UPS_CLIENT_ID')
            client_secret = os.environ.get('UPS_CLIENT_SECRET')
            
            # Log credential information (mask most of it for security)
            if client_id:
                masked_id = client_id[:4] + '*' * (len(client_id) - 4) if len(client_id) > 4 else '****'
                logger.info(f"Using UPS Client ID: {masked_id}")
            else:
                logger.error("UPS_CLIENT_ID is empty or not set")
                
            if client_secret:
                logger.info(f"UPS Client Secret is set (length: {len(client_secret)})")
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
            
            logger.info("Sending UPS OAuth token request...")
            
            # Make the request
            response = requests.post(
                self.UPS_OAUTH_URL,
                headers=headers,
                data=data,
                auth=(client_id, client_secret)
            )
            
            logger.info(f"UPS OAuth response status code: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 'unknown')
                logger.info(f"Successfully obtained UPS OAuth token (expires in {expires_in} seconds)")
                
                # Mask token for security in logs
                if access_token:
                    masked_token = access_token[:10] + '*' * 10 + access_token[-5:] if len(access_token) > 25 else '****'
                    logger.info(f"UPS Token: {masked_token}")
                    self.access_token = access_token
                    return access_token
                else:
                    logger.error("UPS Access token not found in response")
                    return None
            else:
                logger.error(f"Failed to get UPS OAuth token: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error obtaining UPS OAuth token: {e}")
            return None
    
    def get_tracking_info(self, tracking_number):
        """Get tracking information from UPS API."""
        try:
            # Get OAuth token if not already present
            if not self.access_token:
                self.access_token = self.get_oauth_token()
                
            if not self.access_token:
                logger.error("No UPS access token available, cannot track package")
                return self.standardize_response(None, status="API Error", carrier_name="UPS")
            
            # UPS Tracking API endpoint
            tracking_url = self.UPS_TRACK_URL + tracking_number
            logger.info(f"Using UPS Tracking API URL: {tracking_url}")
            
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
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'transId': trans_id,
                'transactionSrc': 'tracking'
            }
            
            logger.info(f"Using UPS transaction ID: {trans_id}")
            logger.info(f"Sending UPS tracking request for: {tracking_number}")
            
            # Make the request with query parameters
            response = requests.get(
                tracking_url, 
                headers=headers,
                params=query_params
            )
            
            logger.info(f"UPS Tracking API response status: {response.status_code}")
            
            if response.status_code == 200:
                tracking_data = response.json()
                logger.info(f"Successfully retrieved UPS tracking info for {tracking_number}")
                
                # Parse the tracking response
                status, last_update, location, address_dict, delivery_estimate = self.parse_tracking_response(tracking_data)
                
                # Return standardized response
                return self.standardize_response(
                    tracking_data, 
                    status=status, 
                    last_update=last_update, 
                    location=location, 
                    address=address_dict, 
                    delivery_estimate=delivery_estimate,
                    carrier_name="UPS"
                )
            else:
                logger.error(f"Failed to get UPS tracking info for {tracking_number}: {response.status_code} - {response.text}")
                return self.standardize_response(
                    None, 
                    status="API Error", 
                    carrier_name="UPS"
                )
        except Exception as e:
            logger.error(f"Error getting UPS tracking info for {tracking_number}: {e}")
            return self.standardize_response(
                None, 
                status="Error", 
                carrier_name="UPS"
            )
    
    def validate_address(self, address):
        """Validate address using UPS Address Validation API."""
        try:
            # Get OAuth token if not already present
            if not self.access_token:
                self.access_token = self.get_oauth_token()
                
            if not self.access_token:
                logger.error("No UPS access token available, cannot validate address")
                return None
                
            # Log the address we're trying to validate
            logger.info(f"Attempting to validate address with UPS: {json.dumps(address)}")
            
            # Check if we have enough address information to validate
            if not any([address.get(key) for key in ["postal_code", "city", "state"]]):
                logger.warning("Not enough address information for UPS validation")
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
                'Authorization': f'Bearer {self.access_token}',
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
            
            logger.info(f"UPS Validation request data: {json.dumps(data)}")
            
            # Make the request
            response = requests.post(
                self.UPS_ADDRESS_URL,
                headers=headers,
                json=data
            )
            
            logger.info(f"UPS Address Validation API response status: {response.status_code}")
            
            if response.status_code == 200:
                validation_data = response.json()
                logger.info(f"Successfully validated address with UPS")
                return validation_data
            else:
                logger.error(f"Failed to validate address with UPS: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error validating address with UPS: {e}")
            return None
    
    def get_estimated_delivery(self, origin, destination):
        """Get estimated delivery time using UPS Time in Transit API."""
        try:
            # Get OAuth token if not already present
            if not self.access_token:
                self.access_token = self.get_oauth_token()
                
            if not self.access_token:
                logger.error("No UPS access token available, cannot get time in transit")
                return None
                
            # Log what we have
            logger.info(f"UPS Origin data: {origin}")
            logger.info(f"UPS Destination data: {destination}")
            
            # Check if we have the minimum required fields
            origin_postal = origin.get("postal_code")
            dest_postal = destination.get("postal_code")
            
            if not origin_postal:
                logger.error("Missing origin postal code for UPS time in transit calculation")
                return None
                
            if not dest_postal:
                logger.error("Missing destination postal code for UPS time in transit calculation")
                return None
                
            # Request headers
            headers = {
                'Authorization': f'Bearer {self.access_token}',
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
            
            logger.info(f"Requesting UPS time in transit estimate from {origin_postal} to {dest_postal}")
            
            # Use the correct endpoint URL based on the example
            transit_url = "https://onlinetools.ups.com/api/shipments/v1/transittimes"
            
            # Make the request
            response = requests.post(
                transit_url,
                headers=headers,
                json=data
            )
            
            logger.info(f"UPS Time in Transit API response status: {response.status_code}")
            
            if response.status_code == 200:
                time_data = response.json()
                logger.info(f"Successfully retrieved UPS time in transit information")
                return time_data
            else:
                logger.error(f"Failed to get UPS time in transit: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting UPS time in transit: {e}")
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
    
    def validate_address(self, address):
        """Validate address using USPS Address Validation API."""
        # PLACEHOLDER - will implement once API credentials are available
        logger.warning("USPS Address Validation not yet implemented")
        return None
    
    def get_estimated_delivery(self, origin, destination):
        """Get estimated delivery time using USPS APIs."""
        # PLACEHOLDER - will implement once API credentials are available
        logger.warning("USPS Estimated Delivery not yet implemented")
        return None
    
    def parse_ups_tracking_response(self, tracking_data):
        """Parse the UPS Tracking API response."""
        try:
            if not tracking_data:
                return None, None, None, None, None
                
            # Log the tracking data structure for debugging
            logger.info(f"Parsing UPS tracking data response")
            
            # Extract package information
            shipment = tracking_data.get('trackResponse', {}).get('shipment', [{}])[0]
            package = shipment.get('package', [{}])[0]
            
            # Get status
            activity = package.get('activity', [{}])[0]
            status = activity.get('status', {}).get('description', 'Unknown')
            
            # Get last update time
            date = activity.get('date', '')
            time_str = activity.get('time', '')
            
            # Format the date and time for readability
            formatted_date = self.format_api_date(date)
            formatted_time = self.format_api_time(time_str)
            
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
                    logger.info(f"Found UPS delivery date: {date}, type: {type_code}")
                    
                    if date:
                        # Format date to be human-readable
                        formatted_delivery_date = self.format_api_date(date)
                        delivery_estimate = formatted_delivery_date
                        break
            
            # 2. If not found, check deliveryTime object
            if not delivery_estimate:
                delivery_time = package.get('deliveryTime', {})
                if delivery_time:
                    date_type = delivery_time.get('type', '')
                    start_time = delivery_time.get('startTime', '')
                    end_time = delivery_time.get('endTime', '')
                    
                    logger.info(f"Found UPS delivery time: type={date_type}, start={start_time}, end={end_time}")
                    
                    if date_type and (start_time or end_time):
                        if date_type == 'EDW' and start_time and end_time:
                            # Format time for better readability
                            start_formatted = self.format_api_time(start_time)
                            end_formatted = self.format_api_time(end_time)
                            delivery_estimate = f"{start_formatted} - {end_formatted}"
                        elif date_type == 'CMT' and end_time:
                            end_formatted = self.format_api_time(end_time)
                            delivery_estimate = f"By {end_formatted}"
            
            # 3. If still not found, check package status for delivery information
            if not delivery_estimate and 'SCHEDULED DELIVERY' in status.upper():
                # Extract date from status if possible
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
                logger.info(f"Extracted UPS delivery estimate: {delivery_estimate}")
            else:
                logger.warning("No delivery estimate found in UPS tracking data")
            
            return status, last_update, location, address_dict, delivery_estimate
        except Exception as e:
            logger.error(f"Error parsing UPS tracking response: {e}")
            return None, None, None, None, None
    
    def format_api_date(self, date_str):
        """Format UPS date strings to be more human-readable."""
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
            logger.error(f"Error formatting UPS date {date_str}: {e}")
            return date_str
    
    def format_api_time(self, time_str):
        """Format UPS time strings to be more human-readable."""
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
            logger.error(f"Error formatting UPS time {time_str}: {e}")
            return time_str


class USPSApi(CarrierAPI):
    """USPS API implementation."""
    
    # USPS API Base URLs
    USPS_BASE_URL = 'https://secure.shippingapis.com/ShippingAPI.dll'
    
    def __init__(self):
        """Initialize the USPS API client."""
        self.user_id = os.environ.get('USPS_USER_ID')
        if not self.user_id:
            logger.warning("USPS_USER_ID not set, USPS tracking will be unavailable")
        else:
            logger.info(f"USPS API configured with User ID: {self.user_id[:4]}****")
    
    def get_tracking_info(self, tracking_number):
        """Get tracking information from USPS API."""
        try:
            if not self.user_id:
                logger.error("USPS_USER_ID not set, cannot track package")
                return self.standardize_response(None, status="API Not Configured", carrier_name="USPS")
            
            # For now, create mock data for development until API keys acquired
            # PLACEHOLDER - will replace with actual API call
            tracking_data = self._get_usps_mock_data(tracking_number)
            
            # Parse the tracking response 
            status, last_update, location, address_dict, delivery_estimate = self.parse_tracking_response(tracking_data)
            
            # Return standardized response
            return self.standardize_response(
                tracking_data,
                status=status,
                last_update=last_update,
                location=location,
                address=address_dict,
                delivery_estimate=delivery_estimate,
                carrier_name="USPS"
            )
            
            # Once API is configured, replace the mock data with actual API calls:
            """
            # Build XML request
            xml_request = f'''
            <TrackFieldRequest USERID="{self.user_id}">
                <TrackID ID="{tracking_number}"></TrackID>
            </TrackFieldRequest>
            '''
            
            # Parameters for the API request
            params = {
                'API': 'TrackV2',
                'XML': xml_request
            }
            
            # Make the request
            response = requests.get(self.USPS_BASE_URL, params=params)
            
            if response.status_code == 200:
                # Parse XML response
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                
                # Extract tracking data
                tracking_info = {}
                track_info = root.find('.//TrackInfo')
                
                if track_info is not None:
                    tracking_info['tracking_number'] = track_info.get('ID')
                    
                    # Get summary
                    summary = track_info.find('TrackSummary')
                    if summary is not None and summary.text:
                        tracking_info['summary'] = summary.text
                    
                    # Get status events
                    events = []
                    for track_detail in track_info.findall('TrackDetail'):
                        if track_detail.text:
                            events.append(track_detail.text)
                    
                    tracking_info['events'] = events
                    
                    # Additional fields
                    for field in ['Status', 'StatusCategory', 'StatusSummary', 'ExpectedDeliveryDate']:
                        elem = track_info.find(field)
                        if elem is not None and elem.text:
                            tracking_info[field.lower()] = elem.text
                
                # Parse the tracking response
                status, last_update, location, address_dict, delivery_estimate = self.parse_tracking_response(tracking_info)
                
                # Return standardized response
                return self.standardize_response(
                    tracking_info,
                    status=status,
                    last_update=last_update,
                    location=location,
                    address=address_dict,
                    delivery_estimate=delivery_estimate,
                    carrier_name="USPS"
                )
            else:
                logger.error(f"Failed to get USPS tracking info for {tracking_number}: {response.status_code} - {response.text}")
                return self.standardize_response(None, status="API Error", carrier_name="USPS")
            """
        except Exception as e:
            logger.error(f"Error getting USPS tracking info for {tracking_number}: {e}")
            return self.standardize_response(None, status="Error", carrier_name="USPS")
            
    def _get_usps_mock_data(self, tracking_number):
        """Create mock USPS tracking data for development."""
        import random
        from datetime import datetime, timedelta
        
        # Current date/time
        now = datetime.now()
        
        # Create a random delivery date (1-5 days from now)
        delivery_days = random.randint(1, 5)
        delivery_date = now + timedelta(days=delivery_days)
        
        # Possible statuses
        statuses = [
            "Accepted at USPS Origin Facility",
            "Departed USPS Regional Facility",
            "Arrived at USPS Regional Facility",
            "In Transit to Next Facility", 
            "Out for Delivery",
            "Delivered, In/At Mailbox"
        ]
        
        # Get a status based on delivery days
        if delivery_days <= 0:
            status = "Delivered, In/At Mailbox"
        elif delivery_days == 1:
            status = "Out for Delivery"
        else:
            status_index = min(5 - delivery_days, 3)
            status = statuses[status_index]
        
        # Format dates
        last_update = now.strftime("%B %d, %Y at %I:%M %p")
        expected_delivery = delivery_date.strftime("%B %d, %Y")
        
        # Mock locations
        cities = ["New York", "Chicago", "Los Angeles", "Houston", "Miami", "Denver", "Seattle"]
        states = ["NY", "IL", "CA", "TX", "FL", "CO", "WA"]
        
        # Choose a random location
        location_index = random.randint(0, len(cities) - 1)
        city = cities[location_index]
        state = states[location_index]
        
        # Create mock data structure
        mock_data = {
            'tracking_number': tracking_number,
            'status': status,
            'status_category': 'In Transit' if delivery_days > 0 else 'Delivered',
            'status_summary': status,
            'expected_delivery_date': expected_delivery,
            'summary': f"{status} at {last_update} in {city}, {state}",
            'events': [
                f"{status} at {last_update} in {city}, {state}"
            ],
            'city': city,
            'state': state,
            'country': 'US',
            'last_update': last_update
        }
        
 
class DHLApi(CarrierAPI):
    """DHL API implementation."""
    
    # DHL API Base URLs
    DHL_BASE_URL = 'https://api-test.dhl.com/track/shipments'  # Test endpoint - update to production
    
    def __init__(self):
        """Initialize the DHL API client."""
        self.api_key = os.environ.get('DHL_API_KEY')
        if not self.api_key:
            logger.warning("DHL_API_KEY not set, DHL tracking will be unavailable")
        else:
            masked_key = self.api_key[:4] + '*' * (len(self.api_key) - 8) + self.api_key[-4:] if len(self.api_key) > 8 else '****'
            logger.info(f"DHL API configured with API Key: {masked_key}")
    
    def get_tracking_info(self, tracking_number):
        """Get tracking information from DHL API."""
        try:
            if not self.api_key:
                logger.error("DHL_API_KEY not set, cannot track package")
                return self.standardize_response(None, status="API Not Configured", carrier_name="DHL")
            
            # For now, create mock data for development until API keys acquired
            # PLACEHOLDER - will replace with actual API call
            tracking_data = self._get_dhl_mock_data(tracking_number)
            
            # Parse the tracking response
            status, last_update, location, address_dict, delivery_estimate = self.parse_tracking_response(tracking_data)
            
            # Return standardized response
            return self.standardize_response(
                tracking_data,
                status=status,
                last_update=last_update,
                location=location,
                address=address_dict,
                delivery_estimate=delivery_estimate,
                carrier_name="DHL"
            )
            
            # Once API is configured, replace the mock data with actual API calls:
            """
            # Request headers
            headers = {
                'Accept': 'application/json',
                'DHL-API-Key': self.api_key
            }
            
            # Make the request
            url = f"{self.DHL_BASE_URL}?trackingNumber={tracking_number}"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                tracking_data = response.json()
                logger.info(f"Successfully retrieved DHL tracking info for {tracking_number}")
                
                # Parse the tracking response
                status, last_update, location, address_dict, delivery_estimate = self.parse_tracking_response(tracking_data)
                
                # Return standardized response
                return self.standardize_response(
                    tracking_data,
                    status=status,
                    last_update=last_update,
                    location=location,
                    address=address_dict,
                    delivery_estimate=delivery_estimate,
                    carrier_name="DHL"
                )
            else:
                logger.error(f"Failed to get DHL tracking info for {tracking_number}: {response.status_code} - {response.text}")
                return self.standardize_response(None, status="API Error", carrier_name="DHL")
            """
        except Exception as e:
            logger.error(f"Error getting DHL tracking info for {tracking_number}: {e}")
            return self.standardize_response(None, status="Error", carrier_name="DHL")
    
    def _get_dhl_mock_data(self, tracking_number):
        """Create mock DHL tracking data for development."""
        import random
        from datetime import datetime, timedelta
        
        # Current date/time
        now = datetime.now()
        
        # Create a random delivery date (1-5 days from now)
        delivery_days = random.randint(1, 5)
        delivery_date = now + timedelta(days=delivery_days)
        
        # Possible statuses based on DHL tracking status
        statuses = [
            "Shipment picked up",
            "Processed at DHL Location",
            "Departed Facility",
            "In Transit", 
            "Arrived at Delivery Facility",
            "With Delivery Courier",
            "Delivered"
        ]
        
        # Get a status based on delivery days
        if delivery_days <= 0:
            status = "Delivered"
        elif delivery_days == 1:
            status = "With Delivery Courier"
        else:
            status_index = min(6 - delivery_days, 5)
            status = statuses[status_index]
        
        # Format dates
        last_update = now.strftime("%Y-%m-%dT%H:%M:%S")
        expected_delivery = delivery_date.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Mock locations
        cities = ["Berlin", "Frankfurt", "London", "Paris", "Madrid", "Rome", "Amsterdam"]
        countries = ["Germany", "Germany", "United Kingdom", "France", "Spain", "Italy", "Netherlands"]
        country_codes = ["DE", "DE", "GB", "FR", "ES", "IT", "NL"]
        
        # Choose a random location
        location_index = random.randint(0, len(cities) - 1)
        city = cities[location_index]
        country = countries[location_index]
        country_code = country_codes[location_index]
        
        # Create mock data structure similar to DHL API response
        mock_data = {
            'shipments': [{
                'id': tracking_number,
                'service': 'express',
                'origin': {
                    'address': {
                        'city': 'Leipzig',
                        'country': 'Germany',
                        'countryCode': 'DE'
                    }
                },
                'destination': {
                    'address': {
                        'city': city,
                        'country': country,
                        'countryCode': country_code
                    }
                },
                'status': {
                    'timestamp': last_update,
                    'statusCode': 'delivered' if status == 'Delivered' else 'transit',
                    'status': status,
                    'description': status
                },
                'estimatedDeliveryTimeframe': {
                    'estimatedFrom': expected_delivery,
                    'estimatedThrough': expected_delivery
                },
                'events': [
                    {
                        'timestamp': last_update,
                        'statusCode': 'delivered' if status == 'Delivered' else 'transit',
                        'status': status,
                        'description': status,
                        'location': {
                            'city': city,
                            'country': country,
                            'countryCode': country_code
                        }
                    }
                ]
            }]
        }
        
        logger.info(f"Generated mock DHL data for {tracking_number}: {status}")
        return mock_data
    
    def parse_tracking_response(self, tracking_data):
        """Parse the DHL tracking response."""
        try:
            if not tracking_data or 'shipments' not in tracking_data or not tracking_data['shipments']:
                return None, None, None, None, None
            
            # Extract shipment info
            shipment = tracking_data['shipments'][0]
            
            # Extract status
            status_info = shipment.get('status', {})
            status = status_info.get('description', 'Unknown')
            
            # Extract timestamp
            timestamp = status_info.get('timestamp', '')
            last_update = self.format_api_date(timestamp)
            
            # Extract location from most recent event
            events = shipment.get('events', [])
            location = 'Unknown'
            city = ''
            country = ''
            country_code = ''
            
            if events:
                latest_event = events[0]  # Most recent event
                location_info = latest_event.get('location', {})
                city = location_info.get('city', '')
                country = location_info.get('country', '')
                country_code = location_info.get('countryCode', '')
                
                location_parts = [part for part in [city, country] if part]
                location = ', '.join(location_parts) if location_parts else 'Unknown'
            
            # Create address dict for validation
            address_dict = {
                "city": city,
                "country": country,
                "country_code": country_code
            }
            
            # Extract delivery estimate
            delivery_estimate = None
            est_timeframe = shipment.get('estimatedDeliveryTimeframe', {})
            
            if est_timeframe:
                est_date = est_timeframe.get('estimatedThrough', '')
                if est_date:
                    delivery_estimate = self.format_api_date(est_date)
            
            return status, last_update, location, address_dict, delivery_estimate
        except Exception as e:
            logger.error(f"Error parsing DHL tracking response: {e}")
            return None, None, None, None, None
    
    def format_api_date(self, date_str):
        """Format DHL date strings (ISO 8601) to be more human-readable."""
        try:
            if not date_str:
                return 'Unknown'
                
            # DHL uses ISO 8601 format (YYYY-MM-DDTHH:MM:SS)
            from datetime import datetime
            
            # Parse ISO format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            
            # Format as human readable
            return dt.strftime("%B %d, %Y at %I:%M %p")
        except Exception as e:
            logger.error(f"Error formatting DHL date {date_str}: {e}")
            return date_str
    
    def validate_address(self, address):
        """Validate address using DHL address validation."""
        # PLACEHOLDER - will implement once API credentials are available
        logger.warning("DHL Address Validation not yet implemented")
        return None
    
    def get_estimated_delivery(self, origin, destination):
        """Get estimated delivery time using DHL APIs."""
        # PLACEHOLDER - will implement once API credentials are available
        logger.warning("DHL Estimated Delivery not yet implemented")
        return None


# Factory to create the appropriate carrier API instance
def create_carrier_api(carrier_name=None, tracking_number=None):
    """
    Factory function to create the appropriate carrier API instance.
    
    Args:
        carrier_name (str, optional): Name of the carrier ('UPS', 'USPS', 'DHL')
        tracking_number (str, optional): If carrier_name not provided, will try to detect from tracking number
        
    Returns:
        CarrierAPI: An instance of the appropriate carrier API class
    """
    # Import here to avoid circular import
    from carrier_detector import detect_carrier
    
    # If carrier not specified but tracking number provided, try to detect
    if not carrier_name and tracking_number:
        carrier_name = detect_carrier(tracking_number)
    
    # Default to UPS if still unknown
    if not carrier_name or carrier_name == 'UNKNOWN':
        logger.warning(f"Unknown carrier for tracking number: {tracking_number}, defaulting to UPS")
        carrier_name = 'UPS'
    
    # Create the appropriate API instance
    carrier_apis = {
        'UPS': UPSApi,
        'USPS': USPSApi,
        'DHL': DHLApi
    }
    
    api_class = carrier_apis.get(carrier_name)
    if not api_class:
        logger.error(f"No API implementation found for carrier: {carrier_name}")
        return None
    
    return api_class()