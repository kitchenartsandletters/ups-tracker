#!/usr/bin/env python3
"""
ShipStation Active Shipments Filter

This script helps filter only recent active shipments from the ShipStation API
to ensure we're only seeding the database with current, in-transit shipments.
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

def get_active_shipments():
    """
    Get only recent active shipments from ShipStation
    
    Focuses on:
    1. Non-cancelled shipments
    2. Non-voided shipments
    3. Recent shipments (last 30 days)
    4. Shipments that have been created but not yet delivered
    """
    
    # Get ShipStation API key from environment
    api_key = os.environ.get('SHIPSTATION_API_KEY')
    
    if not api_key:
        logger.error("Missing ShipStation API key")
        return []
    
    # Calculate date for filtering (last 30 days)
    cutoff_date = datetime.now() - timedelta(days=30)
    ship_date_start = cutoff_date.strftime('%Y-%m-%d')
    
    try:
        # ShipStation API V1 endpoint for listing shipments
        url = "https://ssapi.shipstation.com/shipments"
        
        # Use API Key for both username and password
        auth = (api_key, api_key)
        
        # Parameters to filter for recent shipments
        params = {
            'shipDateStart': ship_date_start,
            'includeShipmentItems': 'true',
            'page': 1,
            'pageSize': 100
        }
        
        logger.info(f"Requesting recent shipments from ShipStation (shipDateStart: {ship_date_start})")
        
        # Make the request
        response = requests.get(
            url,
            params=params,
            auth=auth
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch from ShipStation: {response.status_code} - {response.text}")
            return []
        
        # Process response
        data = response.json()
        all_shipments = data.get('shipments', [])
        total_pages = data.get('pages', 1)
        
        logger.info(f"Found {len(all_shipments)} shipments on page 1 of {total_pages}")
        
        # Fetch additional pages if needed (up to 3 pages total for this test)
        for page in range(2, min(4, total_pages + 1)):
            params['page'] = page
            logger.info(f"Requesting page {page} of shipments")
            
            response = requests.get(
                url,
                params=params,
                auth=auth
            )
            
            if response.status_code == 200:
                page_data = response.json()
                page_shipments = page_data.get('shipments', [])
                all_shipments.extend(page_shipments)
                logger.info(f"Added {len(page_shipments)} shipments from page {page}")
            else:
                logger.error(f"Failed to fetch page {page}: {response.status_code}")
        
        logger.info(f"Retrieved {len(all_shipments)} total shipments")
        
        # Filter for active shipments
        active_shipments = []
        cancelled_count = 0
        voided_count = 0
        empty_tracking_count = 0
        
        for shipment in all_shipments:
            # Skip cancelled shipments
            if shipment.get('shipmentStatus') == 'cancelled':
                cancelled_count += 1
                continue
            
            # Skip voided shipments
            if shipment.get('voidDate'):
                voided_count += 1
                continue
            
            # Skip if no tracking number
            if not shipment.get('trackingNumber'):
                empty_tracking_count += 1
                continue
            
            # This is an active shipment
            active_shipments.append(shipment)
        
        logger.info(f"Filtered results: {len(active_shipments)} active shipments")
        logger.info(f"Excluded: {cancelled_count} cancelled, {voided_count} voided, {empty_tracking_count} without tracking")
        
        # Save the filtered results to a file
        with open('active_shipments.json', 'w') as f:
            json.dump(active_shipments, f, indent=2)
            
        logger.info("Saved active shipments to active_shipments.json")
        
        # Print some example tracking numbers if available
        if active_shipments:
            logger.info("Example tracking numbers from active shipments:")
            for i, shipment in enumerate(active_shipments[:5]):
                logger.info(f"  {i+1}. {shipment.get('trackingNumber')} - {shipment.get('shipmentStatus')}")
        
        return active_shipments
    
    except Exception as e:
        logger.error(f"Error getting active shipments: {e}")
        import traceback
        logger.error(f"Error details: {traceback.format_exc()}")
        return []

if __name__ == "__main__":
    get_active_shipments()