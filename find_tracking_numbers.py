#!/usr/bin/env python3
"""
ShipStation Tracking Number Location Finder

This script analyzes the structure of ShipStation API responses to locate
where tracking numbers are stored in your specific account's data format.
"""

import os
import json
import requests
import logging
from datetime import datetime, timedelta
import pprint

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def dump_shipment_structure(shipment, prefix=''):
    """Recursively explore and log shipment structure"""
    if isinstance(shipment, dict):
        for key, value in shipment.items():
            # If the value might contain a tracking number, log it
            if isinstance(value, str) and ('track' in key.lower() or 
                                          (len(value) > 8 and any(c.isdigit() for c in value))):
                logger.info(f"{prefix}{key}: {value} <-- POTENTIAL TRACKING NUMBER")
            elif isinstance(value, (dict, list)):
                if isinstance(value, dict):
                    logger.info(f"{prefix}{key}: {{...}}")
                    dump_shipment_structure(value, prefix + '  ')
                else:
                    logger.info(f"{prefix}{key}: [...] ({len(value)} items)")
                    if len(value) > 0:
                        dump_shipment_structure(value[0], prefix + '  ')
            else:
                # Just log the key for other values to reduce output clutter
                logger.info(f"{prefix}{key}: {type(value).__name__}")
    elif isinstance(shipment, list) and len(shipment) > 0:
        logger.info(f"{prefix}List with {len(shipment)} items:")
        # Just show the first item to avoid excessive output
        dump_shipment_structure(shipment[0], prefix + '  ')

def find_tracking_numbers():
    """Locate tracking numbers in ShipStation API response"""
    
    # Get ShipStation API key from environment
    api_key = os.environ.get('SHIPSTATION_API_KEY')
    
    if not api_key:
        logger.error("Missing ShipStation API key")
        return
    
    # ShipStation API V2 endpoint for listing shipments
    url = "https://api.shipstation.com/v2/shipments"
    
    # V2 API uses API-Key header for authentication
    headers = {
        'API-Key': api_key,
        'Content-Type': 'application/json'
    }
    
    # Parameters for the API request - focus on shipments with label_purchased status
    params = {
        'page': 1,
        'page_size': 5  # Just get a few shipments for analysis
    }
    
    logger.info("Fetching sample shipments for structure analysis")
    
    # Make the request
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            shipments = data.get('shipments', [])
            
            if not shipments:
                logger.warning("No shipments found in API response")
                return
            
            # Save the full raw response for reference
            with open('shipstation_raw_response.json', 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Found {len(shipments)} shipments for analysis")
            logger.info("Full API response saved to shipstation_raw_response.json")
            
            # Analyze the first shipment in detail
            if shipments:
                sample_shipment = shipments[0]
                
                logger.info("\n=== SHIPMENT STRUCTURE ANALYSIS ===")
                logger.info("Analyzing shipment structure to locate tracking number:")
                dump_shipment_structure(sample_shipment)
                
                # Look for any field that might contain a tracking number
                logger.info("\n=== POTENTIAL TRACKING NUMBER FIELDS ===")
                def find_potential_tracking(obj, path=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            new_path = f"{path}.{key}" if path else key
                            
                            # Check if this field might be a tracking number
                            if isinstance(value, str) and (
                                'track' in key.lower() or 
                                (len(value) > 8 and any(c.isdigit() for c in value))
                            ):
                                logger.info(f"Potential tracking number at {new_path}: {value}")
                            
                            # Recurse into nested structures
                            if isinstance(value, (dict, list)):
                                find_potential_tracking(value, new_path)
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            new_path = f"{path}[{i}]"
                            find_potential_tracking(item, new_path)
                
                find_potential_tracking(sample_shipment)
                
                # Specifically look at label_purchased shipments
                label_purchased = [s for s in shipments if s.get('shipment_status') == 'label_purchased']
                
                if label_purchased:
                    logger.info("\n=== LABEL_PURCHASED SHIPMENT ANALYSIS ===")
                    for i, shipment in enumerate(label_purchased[:2]):  # Look at up to 2 shipments
                        logger.info(f"Analyzing label_purchased shipment {i+1}:")
                        find_potential_tracking(shipment)
                
                # Save a sample shipment for reference
                with open('shipstation_sample_shipment.json', 'w') as f:
                    json.dump(sample_shipment, f, indent=2)
                
                logger.info("Sample shipment saved to shipstation_sample_shipment.json")
                
                # Check for additional metadata in raw response
                logger.info("\n=== API RESPONSE METADATA ===")
                for key, value in data.items():
                    if key != 'shipments':
                        logger.info(f"{key}: {value}")
        else:
            logger.error(f"Failed to fetch shipments: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Error analyzing shipments: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")

if __name__ == "__main__":
    find_tracking_numbers()