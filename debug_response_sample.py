#!/usr/bin/env python3
"""
ShipStation API Response Debug Utility

This script helps debug ShipStation API responses by making a simple API call
and printing the full structure of the response to understand how to extract
tracking numbers.
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

def debug_shipstation_api():
    """Make a test call to ShipStation API and examine the response structure"""
    
    # Get ShipStation API key from environment
    api_key = os.environ.get('SHIPSTATION_API_KEY')
    
    if not api_key:
        logger.error("Missing ShipStation API key")
        return
    
    # Try V2 API first
    try:
        # ShipStation API V2 endpoint for listing shipments
        url = "https://api.shipstation.com/v2/shipments"
        
        # V2 API uses API-Key header for authentication
        headers = {
            'API-Key': api_key,
            'Content-Type': 'application/json'
        }
        
        # Get only first page with a few shipments
        params = {
            'page': 1,
            'page_size': 5
        }
        
        logger.info("Making test request to ShipStation V2 API")
        
        # Make the request
        response = requests.get(
            url,
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            logger.info("Successfully connected to ShipStation V2 API")
            data = response.json()
            
            # Save full response to file for examination
            with open('shipstation_v2_response.json', 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info("Saved response to shipstation_v2_response.json")
            
            # Extract and print key structure paths
            shipments = data.get('shipments', [])
            logger.info(f"Found {len(shipments)} shipments in response")
            
            if shipments:
                logger.info("Examining first shipment structure")
                first_shipment = shipments[0]
                
                # Print top-level keys
                logger.info(f"Top-level keys: {sorted(first_shipment.keys())}")
                
                # Check for specific keys of interest
                if 'tracking_number' in first_shipment:
                    logger.info(f"Found 'tracking_number': {first_shipment['tracking_number']}")
                elif 'trackingNumber' in first_shipment:
                    logger.info(f"Found 'trackingNumber': {first_shipment['trackingNumber']}")
                
                # Check for labels array
                if 'labels' in first_shipment:
                    labels = first_shipment.get('labels', [])
                    logger.info(f"Found {len(labels)} labels in first shipment")
                    
                    if labels:
                        label_keys = sorted(labels[0].keys())
                        logger.info(f"Label keys: {label_keys}")
                        
                        if 'tracking_number' in labels[0]:
                            logger.info(f"Found tracking number in label: {labels[0]['tracking_number']}")
                        elif 'trackingNumber' in labels[0]:
                            logger.info(f"Found trackingNumber in label: {labels[0]['trackingNumber']}")
        else:
            logger.error(f"Failed to connect to ShipStation V2 API: {response.status_code} - {response.text}")
            
            # Try V1 API as fallback
            logger.info("Trying V1 API as fallback")
            debug_shipstation_v1_api(api_key)
    
    except Exception as e:
        logger.error(f"Error connecting to ShipStation V2 API: {e}")
        logger.info("Trying V1 API as fallback")
        debug_shipstation_v1_api(api_key)

def debug_shipstation_v1_api(api_key):
    """Make a test call to ShipStation V1 API and examine the response structure"""
    try:
        # ShipStation API V1 endpoint for listing shipments
        url = "https://ssapi.shipstation.com/shipments"
        
        # V1 API uses Basic Auth with API Key as both username and password
        auth = (api_key, api_key)
        
        # Get only first page with a few shipments
        params = {
            'page': 1,
            'pageSize': 5
        }
        
        logger.info("Making test request to ShipStation V1 API")
        
        # Make the request
        response = requests.get(
            url,
            params=params,
            auth=auth
        )
        
        if response.status_code == 200:
            logger.info("Successfully connected to ShipStation V1 API")
            data = response.json()
            
            # Save full response to file for examination
            with open('shipstation_v1_response.json', 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info("Saved response to shipstation_v1_response.json")
            
            # Extract and print key structure paths
            shipments = data.get('shipments', [])
            logger.info(f"Found {len(shipments)} shipments in response")
            
            if shipments:
                logger.info("Examining first shipment structure")
                first_shipment = shipments[0]
                
                # Print top-level keys
                logger.info(f"Top-level keys: {sorted(first_shipment.keys())}")
                
                # Check for specific keys
                if 'trackingNumber' in first_shipment:
                    logger.info(f"Found 'trackingNumber': {first_shipment['trackingNumber']}")
        else:
            logger.error(f"Failed to connect to ShipStation V1 API: {response.status_code} - {response.text}")
            
    except Exception as e:
        logger.error(f"Error connecting to ShipStation V1 API: {e}")

if __name__ == "__main__":
    debug_shipstation_api()