#!/usr/bin/env python3
"""
ShipStation API Authentication Test

This script tests different authentication methods for ShipStation API
to determine which one works with your account.
"""

import os
import requests
import logging
import base64

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_shipstation_auth():
    """Test multiple authentication methods with ShipStation API"""
    
    # Get ShipStation API key from environment
    api_key = os.environ.get('SHIPSTATION_API_KEY')
    
    if not api_key:
        logger.error("Missing SHIPSTATION_API_KEY environment variable")
        return
    
    logger.info(f"Using API key: {api_key[:4]}...{api_key[-4:]} (length: {len(api_key)})")
    
    # Test 1: V2 API with API Key in header
    logger.info("TEST 1: V2 API with API-Key header")
    try:
        url = "https://api.shipstation.com/v2/carriers"
        headers = {
            'API-Key': api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers)
        
        logger.info(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            logger.info("SUCCESS: V2 API with API-Key header works")
            logger.info(f"Response preview: {str(response.text)[:100]}...")
        else:
            logger.error(f"FAILED: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error in Test 1: {e}")
    
    # Test 2: V1 API with Basic Auth (API key as both username and password)
    logger.info("\nTEST 2: V1 API with Basic Auth (API key as both username and password)")
    try:
        url = "https://ssapi.shipstation.com/carriers"
        auth = (api_key, api_key)  # Using API key as both username and password
        
        response = requests.get(url, auth=auth)
        
        logger.info(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            logger.info("SUCCESS: V1 API with Basic Auth (API key as both) works")
            logger.info(f"Response preview: {str(response.text)[:100]}...")
        else:
            logger.error(f"FAILED: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error in Test 2: {e}")
    
    # Test 3: V1 API with Basic Auth (API key as username, empty password)
    logger.info("\nTEST 3: V1 API with Basic Auth (API key as username, empty password)")
    try:
        url = "https://ssapi.shipstation.com/carriers"
        auth = (api_key, "")  # Using API key as username, empty password
        
        response = requests.get(url, auth=auth)
        
        logger.info(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            logger.info("SUCCESS: V1 API with Basic Auth (API key as username, empty password) works")
            logger.info(f"Response preview: {str(response.text)[:100]}...")
        else:
            logger.error(f"FAILED: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error in Test 3: {e}")
    
    # Test 4: V1 API with Authorization header (manually constructed Basic Auth)
    logger.info("\nTEST 4: V1 API with Authorization header (manually constructed Basic Auth)")
    try:
        url = "https://ssapi.shipstation.com/carriers"
        
        # Construct Basic Auth header manually
        auth_string = f"{api_key}:{api_key}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers)
        
        logger.info(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            logger.info("SUCCESS: V1 API with Authorization header works")
            logger.info(f"Response preview: {str(response.text)[:100]}...")
        else:
            logger.error(f"FAILED: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error in Test 4: {e}")
    
    # Test 5: V1 API with alternative endpoint
    logger.info("\nTEST 5: V1 API alternative endpoint")
    try:
        url = "https://ssapi.shipstation.com/accounts"
        auth = (api_key, api_key)
        
        response = requests.get(url, auth=auth)
        
        logger.info(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            logger.info("SUCCESS: V1 API alternative endpoint works")
            logger.info(f"Response preview: {str(response.text)[:100]}...")
        else:
            logger.error(f"FAILED: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error in Test 5: {e}")
    
    # Summary
    logger.info("\n=== AUTHENTICATION TEST SUMMARY ===")
    logger.info("Please check the logs above to see which authentication methods succeeded.")
    logger.info("Use the successful method in your database seeding script.")

if __name__ == "__main__":
    test_shipstation_auth()