#!/usr/bin/env python3
"""
Simple test script to check and debug Google credentials.
"""

import os
import json
import sys
import base64
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

def try_load_json_file(file_path):
    """Try to load a file as JSON and diagnose issues."""
    logger.info(f"Attempting to load file: {file_path}")
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File {file_path} does not exist")
            return None
        
        # Check file size
        file_size = os.path.getsize(file_path)
        logger.info(f"File size: {file_size} bytes")
        
        if file_size == 0:
            logger.error(f"File {file_path} is empty")
            return None
            
        # Try to read as JSON
        with open(file_path, 'r') as f:
            file_content = f.read()
            
        # Check first few characters to diagnose format
        first_chars = file_content[:20].replace('\n', '\\n')
        logger.info(f"First characters: {first_chars}...")
        
        # Try to parse as JSON
        try:
            json_data = json.loads(file_content)
            logger.info("Successfully parsed as JSON")
            
            # Check for required fields
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            missing_fields = [field for field in required_fields if field not in json_data]
            
            if missing_fields:
                logger.warning(f"Missing required fields: {', '.join(missing_fields)}")
            else:
                logger.info("All required fields present")
                logger.info(f"Service account email: {json_data.get('client_email')}")
                
            return json_data
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            
            # Check if it looks like base64
            if all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in file_content.strip()):
                logger.info("Content looks like base64, attempting to decode")
                try:
                    decoded = base64.b64decode(file_content).decode('utf-8')
                    try:
                        json_data = json.loads(decoded)
                        logger.info("Successfully decoded from base64 to JSON")
                        return json_data
                    except json.JSONDecodeError as e2:
                        logger.error(f"Failed to parse decoded content as JSON: {e2}")
                except Exception as e3:
                    logger.error(f"Failed to decode as base64: {e3}")
            
            # If it contains quotes and newlines, it might be a string that needs unescaping
            if '\\n' in file_content and (file_content.startswith('"') or file_content.startswith("'")):
                logger.info("Content looks like a string literal, attempting to unescape")
                try:
                    # Try to parse as a Python string literal
                    unescaped = eval(file_content)
                    try:
                        json_data = json.loads(unescaped)
                        logger.info("Successfully unescaped string to JSON")
                        return json_data
                    except json.JSONDecodeError as e4:
                        logger.error(f"Failed to parse unescaped content as JSON: {e4}")
                except Exception as e5:
                    logger.error(f"Failed to unescape string: {e5}")
                    
            return None
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return None

def main():
    """Main function to test credential loading."""
    # First try credentials.json
    if os.path.exists('credentials.json'):
        logger.info("Found credentials.json")
        json_data = try_load_json_file('credentials.json')
        if json_data:
            logger.info("Successfully loaded credentials.json")
            try:
                # Try to import Google auth packages if available
                from google.oauth2.service_account import Credentials
                import gspread
                
                # Define the scopes
                SCOPES = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                
                # Create credentials object
                creds = Credentials.from_service_account_info(json_data, scopes=SCOPES)
                logger.info("Successfully created credentials object")
                
                # Try to authorize
                client = gspread.authorize(creds)
                logger.info("Successfully authorized with gspread")
                
                # Try to list spreadsheets
                spreadsheets = client.list_spreadsheet_files()
                logger.info(f"Found {len(spreadsheets)} spreadsheets")
                if spreadsheets:
                    logger.info(f"First spreadsheet: {spreadsheets[0]['name']}")
            except ImportError:
                logger.warning("Google auth packages not installed, skipping auth test")
            except Exception as e:
                logger.error(f"Error during auth test: {e}")
        else:
            logger.error("Failed to load credentials.json as JSON")
            
    # Check environment variable
    if 'GOOGLE_CREDENTIALS' in os.environ:
        logger.info("Found GOOGLE_CREDENTIALS environment variable")
        env_value = os.environ['GOOGLE_CREDENTIALS']
        logger.info(f"Length of GOOGLE_CREDENTIALS: {len(env_value)}")
        
        # Write to temp file for inspection
        with open('env_credentials.json', 'w') as f:
            f.write(env_value)
            
        json_data = try_load_json_file('env_credentials.json')
        if json_data:
            logger.info("Successfully loaded GOOGLE_CREDENTIALS as JSON")
        else:
            logger.error("Failed to load GOOGLE_CREDENTIALS as JSON")
    else:
        logger.warning("GOOGLE_CREDENTIALS environment variable not found")
        
    logger.info("Test completed")

if __name__ == "__main__":
    main()