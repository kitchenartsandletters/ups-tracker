#!/usr/bin/env python3
"""
ShipStation API Deep Dive Debug

This script analyzes ShipStation API data to understand why no tracking numbers 
are being found and provides detailed information about the available shipments.
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

def analyze_shipstation_shipments():
    """Do a deep dive analysis of ShipStation shipments"""
    
    # Get ShipStation API key from environment
    api_key = os.environ.get('SHIPSTATION_API_KEY')
    
    if not api_key:
        logger.error("Missing ShipStation API key")
        return
    
    # Calculate different date ranges to try
    now = datetime.now()
    date_ranges = [
        ("Last 30 days", (now - timedelta(days=30)).strftime('%Y-%m-%d')),
        ("Last 90 days", (now - timedelta(days=90)).strftime('%Y-%m-%d')),
        ("Last 180 days", (now - timedelta(days=180)).strftime('%Y-%m-%d')),
        ("Last 365 days", (now - timedelta(days=365)).strftime('%Y-%m-%d')),
        ("All time", "2010-01-01")  # Long ago date to get all shipments
    ]
    
    # V2 API uses API-Key header for authentication
    headers = {
        'API-Key': api_key,
        'Content-Type': 'application/json'
    }
    
    # Try different date ranges
    all_shipments = []
    results_by_range = {}
    
    for range_name, start_date in date_ranges:
        logger.info(f"\n=== Checking {range_name} (since {start_date}) ===")
        
        # ShipStation API V2 endpoint for listing shipments
        url = "https://api.shipstation.com/v2/shipments"
        
        # Parameters for the API request
        params = {
            'created_at_start': start_date,
            'page': 1,
            'page_size': 100
        }
        
        # Make the request
        try:
            logger.info(f"Requesting shipments since {start_date}")
            response = requests.get(
                url,
                params=params,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                shipments = data.get('shipments', [])
                total_pages = data.get('pages', 1)
                total_count = data.get('total', 0)
                
                logger.info(f"Found {total_count} total shipments across {total_pages} pages")
                
                # Categorize shipments by status
                status_counts = {}
                has_tracking_count = 0
                active_with_tracking = 0
                
                for shipment in shipments:
                    # Count by status
                    status = shipment.get('shipment_status', '')
                    if status not in status_counts:
                        status_counts[status] = 0
                    status_counts[status] += 1
                    
                    # Check for tracking numbers
                    has_tracking = False
                    
                    # Look in all possible locations
                    if 'tracking_number' in shipment and shipment['tracking_number']:
                        has_tracking = True
                    elif 'trackingNumber' in shipment and shipment['trackingNumber']:
                        has_tracking = True
                    elif 'packages' in shipment and shipment['packages']:
                        for package in shipment['packages']:
                            if (package.get('tracking_number') or package.get('trackingNumber')):
                                has_tracking = True
                                break
                    
                    if has_tracking:
                        has_tracking_count += 1
                        
                        # Check if it's an active shipment
                        is_active = True
                        if status == 'cancelled':
                            is_active = False
                        elif shipment.get('void_date') or shipment.get('voidDate'):
                            is_active = False
                            
                        if is_active:
                            active_with_tracking += 1
                            # For the first few active shipments, show details
                            if len(all_shipments) < 5:
                                all_shipments.append(shipment)
                
                # Save results for this date range
                results_by_range[range_name] = {
                    'total_shipments': total_count,
                    'shipments_with_tracking': has_tracking_count,
                    'active_with_tracking': active_with_tracking,
                    'status_distribution': status_counts
                }
                
                # Print summary for this date range
                logger.info(f"Summary for {range_name}:")
                logger.info(f"- Total shipments: {total_count}")
                logger.info(f"- Shipments with tracking numbers: {has_tracking_count}")
                logger.info(f"- Active shipments with tracking: {active_with_tracking}")
                
                if status_counts:
                    logger.info("- Status distribution:")
                    for status, count in status_counts.items():
                        logger.info(f"  * {status}: {count} shipments")
            else:
                logger.error(f"Failed to fetch shipments: {response.status_code} - {response.text}")
        
        except Exception as e:
            logger.error(f"Error analyzing shipments for {range_name}: {e}")
    
    # Overall summary
    logger.info("\n=== OVERALL SUMMARY ===")
    for range_name, results in results_by_range.items():
        logger.info(f"\n{range_name}:")
        logger.info(f"- Total shipments: {results['total_shipments']}")
        logger.info(f"- With tracking numbers: {results['shipments_with_tracking']}")
        logger.info(f"- Active with tracking: {results['active_with_tracking']}")
    
    # Examine sample shipments to understand structure
    if all_shipments:
        logger.info("\n=== SAMPLE SHIPMENT STRUCTURE ===")
        sample_shipment = all_shipments[0]
        
        # Save sample to file
        with open('sample_shipment.json', 'w') as f:
            json.dump(sample_shipment, f, indent=2)
        
        logger.info(f"Saved sample shipment to sample_shipment.json")
        
        # Look for tracking number location
        if 'tracking_number' in sample_shipment:
            logger.info(f"Tracking number found at tracking_number: {sample_shipment['tracking_number']}")
        elif 'trackingNumber' in sample_shipment:
            logger.info(f"Tracking number found at trackingNumber: {sample_shipment['trackingNumber']}")
        
        # Look for packages
        if 'packages' in sample_shipment and sample_shipment['packages']:
            logger.info(f"Found {len(sample_shipment['packages'])} packages in shipment")
            # Check first package
            package = sample_shipment['packages'][0]
            if 'tracking_number' in package:
                logger.info(f"Tracking number in package: {package['tracking_number']}")
            elif 'trackingNumber' in package:
                logger.info(f"Tracking number in package: {package['trackingNumber']}")
    else:
        logger.warning("No sample shipments available to analyze structure")
    
    # Suggestions based on findings
    logger.info("\n=== SUGGESTIONS ===")
    
    any_active_shipments = False
    for results in results_by_range.values():
        if results['active_with_tracking'] > 0:
            any_active_shipments = True
            break
    
    if any_active_shipments:
        logger.info("1. Try increasing the days_to_look_back parameter to include older shipments")
        logger.info("2. Check if the tracking numbers already exist in your UPS Tracker sheet")
    else:
        logger.info("1. There don't appear to be any active shipments with tracking numbers")
        logger.info("2. Consider creating test shipments in ShipStation to verify the integration")
        logger.info("3. Check if your ShipStation account is properly configured to store tracking information")

if __name__ == "__main__":
    analyze_shipstation_shipments()