#!/usr/bin/env python3
"""
ShipStation Package-Level Tracking Checker

This script specifically checks for package-level tracking numbers in multi-package
shipments based on the documentation in ShipStation_V2_Tracking.md.
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

def check_package_tracking():
    """Check for package-level tracking numbers in shipment rates"""
    
    # Get ShipStation API key from environment
    api_key = os.environ.get('SHIPSTATION_API_KEY')
    
    if not api_key:
        logger.error("Missing ShipStation API key")
        return
    
    # First get some shipment IDs to check
    try:
        logger.info("First fetching some shipment IDs to test...")
        
        # V1 API endpoint for listing shipments
        shipments_url = "https://ssapi.shipstation.com/shipments"
        
        # Parameters to focus on shipments with status 'label_purchased'
        params = {
            'shipmentStatus': 'label_purchased',
            'page': 1,
            'pageSize': 5
        }
        
        # V1 API uses Basic Auth with API Key as both username and password
        auth = (api_key, api_key)
        
        response = requests.get(
            shipments_url,
            params=params,
            auth=auth
        )
        
        if response.status_code == 200:
            data = response.json()
            shipments = data.get('shipments', [])
            
            if not shipments:
                logger.warning("No shipments found with label_purchased status")
                return
            
            logger.info(f"Found {len(shipments)} shipments to check")
            
            # Now check each shipment for package-level tracking
            for shipment in shipments:
                shipment_id = shipment.get('shipmentId')
                if not shipment_id:
                    continue
                
                logger.info(f"Checking rates for shipment ID: {shipment_id}")
                
                # Use the rates endpoint to check for package-level tracking
                # as mentioned in the documentation
                rates_url = f"https://ssapi.shipstation.com/shipments/{shipment_id}/rates"
                
                rates_response = requests.get(
                    rates_url,
                    auth=auth
                )
                
                if rates_response.status_code == 200:
                    rates_data = rates_response.json()
                    
                    # Save the rates response for analysis
                    with open(f'shipment_{shipment_id}_rates.json', 'w') as f:
                        json.dump(rates_data, f, indent=2)
                    
                    logger.info(f"Saved rates data for shipment {shipment_id}")
                    
                    # Check for package-level tracking
                    if 'packages' in rates_data:
                        packages = rates_data.get('packages', [])
                        logger.info(f"Found {len(packages)} packages in rates response")
                        
                        for i, package in enumerate(packages):
                            tracking_number = package.get('tracking_number')
                            if tracking_number:
                                logger.info(f"Found package-level tracking number: {tracking_number} (Package {i+1})")
                            else:
                                logger.info(f"No tracking number in package {i+1}")
                    else:
                        logger.info("No packages array found in rates response")
                        
                        # Check alternative locations where tracking might exist
                        if 'trackingNumber' in rates_data:
                            logger.info(f"Found tracking number at root level: {rates_data['trackingNumber']}")
                        elif 'tracking_number' in rates_data:
                            logger.info(f"Found tracking number at root level: {rates_data['tracking_number']}")
                else:
                    logger.error(f"Failed to get rates: {rates_response.status_code} - {rates_response.text}")
        else:
            logger.error(f"Failed to get shipments: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Error checking package tracking: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")

if __name__ == "__main__":
    check_package_tracking()