#!/usr/bin/env python3
"""
ShipStation Direct Tracking Number Extractor

This script focuses specifically on the trackingNumber field in ShipStation's
API response based on the documentation guidance.
"""

import os
import json
import requests
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_tracking_numbers():
    """Extract tracking numbers directly from ShipStation API using documented approach"""
    
    # Get ShipStation API key from environment
    api_key = os.environ.get('SHIPSTATION_API_KEY')
    
    if not api_key:
        logger.error("Missing ShipStation API key")
        return
    
    # Calculate date for filtering (last 180 days)
    cutoff_date = datetime.now() - timedelta(days=180)
    ship_date_start = cutoff_date.strftime('%Y-%m-%d')
    
    # Try both V1 and V2 endpoints to see which works
    
    # V1 API Endpoint (documented in ShipStation_V2_Tracking.md)
    v1_endpoint = "https://ssapi.shipstation.com/shipments"
    
    # Parameters focused on shipments with purchased labels
    params = {
        'shipDateStart': ship_date_start,
        'page': 1,
        'pageSize': 10  # Start with just a few for testing
    }
    
    logger.info(f"Trying V1 API endpoint: {v1_endpoint}")
    
    # V1 API uses Basic Auth with API Key as both username and password
    # This is a common approach when only API Key is available
    auth = (api_key, api_key)
    
    try:
        response = requests.get(
            v1_endpoint,
            params=params,
            auth=auth
        )
        
        if response.status_code == 200:
            logger.info("Successfully connected to V1 API endpoint")
            data = response.json()
            shipments = data.get('shipments', [])
            logger.info(f"Found {len(shipments)} shipments in response")
            
            # Save raw response for analysis
            with open('shipstation_v1_response.json', 'w') as f:
                json.dump(data, f, indent=2)
                
            tracking_numbers = []
            
            # Look specifically for trackingNumber field as mentioned in the documentation
            for shipment in shipments:
                # Check if the shipment has a tracking number
                tracking_number = shipment.get('trackingNumber')
                
                if tracking_number:
                    status = shipment.get('shipmentStatus', '')
                    logger.info(f"Found tracking number: {tracking_number} (Status: {status})")
                    tracking_numbers.append({
                        'tracking_number': tracking_number,
                        'shipment_id': shipment.get('shipmentId'),
                        'status': status,
                        'created_date': shipment.get('createDate')
                    })
                else:
                    logger.info(f"Shipment without tracking number: ID {shipment.get('shipmentId')}")
            
            if tracking_numbers:
                logger.info(f"Successfully extracted {len(tracking_numbers)} tracking numbers")
                # Print the first few for reference
                for i, tn in enumerate(tracking_numbers[:5]):
                    logger.info(f"Tracking #{i+1}: {tn['tracking_number']} (Status: {tn['status']})")
            else:
                logger.warning("No tracking numbers found in the response")
                
                # Check for alternative fields that might contain tracking info
                alternative_fields = []
                if shipments:
                    # Save a sample shipment for inspection
                    with open('sample_shipment_structure.json', 'w') as f:
                        json.dump(shipments[0], f, indent=2)
                    
                    # Log the fields available in a shipment
                    logger.info("Fields available in shipment structure:")
                    for key in shipments[0].keys():
                        logger.info(f"- {key}")
                        # Check if this might be a tracking field
                        if 'track' in key.lower():
                            alternative_fields.append(key)
                
                if alternative_fields:
                    logger.info(f"Potential alternative tracking fields: {', '.join(alternative_fields)}")
        else:
            logger.error(f"Failed to connect to V1 API: {response.status_code} - {response.text}")
            logger.info("Trying V2 API instead...")
            
            # Try V2 API as a fallback
            v2_endpoint = "https://api.shipstation.com/v2/shipments"
            headers = {
                'API-Key': api_key,
                'Content-Type': 'application/json'
            }
            
            v2_params = {
                'created_at_start': ship_date_start,
                'page': 1,
                'page_size': 10
            }
            
            v2_response = requests.get(
                v2_endpoint,
                params=v2_params,
                headers=headers
            )
            
            if v2_response.status_code == 200:
                logger.info("Successfully connected to V2 API endpoint")
                v2_data = v2_response.json()
                v2_shipments = v2_data.get('shipments', [])
                
                # Save raw response for analysis
                with open('shipstation_v2_response.json', 'w') as f:
                    json.dump(v2_data, f, indent=2)
                
                # Check for tracking numbers in V2 response
                v2_tracking_numbers = []
                
                for shipment in v2_shipments:
                    # Try various potential locations for tracking numbers
                    tracking_number = None
                    
                    if 'tracking_number' in shipment:
                        tracking_number = shipment.get('tracking_number')
                    elif 'trackingNumber' in shipment:
                        tracking_number = shipment.get('trackingNumber')
                    
                    if tracking_number:
                        logger.info(f"Found tracking number in V2 API: {tracking_number}")
                        v2_tracking_numbers.append(tracking_number)
                
                if v2_tracking_numbers:
                    logger.info(f"Successfully extracted {len(v2_tracking_numbers)} tracking numbers from V2 API")
                else:
                    logger.warning("No tracking numbers found in V2 API response either")
            else:
                logger.error(f"Failed to connect to V2 API: {v2_response.status_code} - {v2_response.text}")
    
    except Exception as e:
        logger.error(f"Error extracting tracking numbers: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")

if __name__ == "__main__":
    extract_tracking_numbers()