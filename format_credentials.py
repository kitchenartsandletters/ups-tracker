#!/usr/bin/env python3
"""
Format Google service account credentials for GitHub Secrets.
This script:
1. Takes a service account JSON file
2. Properly formats it for GitHub Secrets
3. Tests that it can be decoded back properly

Usage: python format_credentials.py your-service-account.json
"""

import sys
import json
import base64

def format_for_github(file_path):
    """Read a JSON file and format it for GitHub Secrets."""
    try:
        # Read the file
        with open(file_path, 'r') as f:
            json_content = f.read()
        
        # Parse as JSON to verify it's valid
        json_data = json.loads(json_content)
        
        # Two options to format for GitHub:
        
        # Option 1: Use the JSON as-is (recommended)
        print("\n=== OPTION 1: Direct JSON (RECOMMENDED) ===")
        print("Copy this exactly as-is for your GOOGLE_CREDENTIALS secret:")
        print("---BEGIN CREDENTIALS---")
        print(json_content)
        print("---END CREDENTIALS---")
        
        # Option 2: Base64 encode
        base64_encoded = base64.b64encode(json_content.encode('utf-8')).decode('utf-8')
        print("\n=== OPTION 2: Base64 Encoded ===")
        print("Copy this exactly as-is for your GOOGLE_CREDENTIALS secret:")
        print("---BEGIN CREDENTIALS---")
        print(base64_encoded)
        print("---END CREDENTIALS---")
        
        # Test decoding back
        print("\nVerification tests:")
        try:
            # Test option 1 (direct JSON)
            decoded_json = json.loads(json_content)
            print("✓ Direct JSON format can be parsed successfully")
        except Exception as e:
            print(f"✗ Error parsing direct JSON: {e}")
        
        try:
            # Test option 2 (base64)
            decoded_content = base64.b64decode(base64_encoded).decode('utf-8')
            decoded_json = json.loads(decoded_content)
            print("✓ Base64 format can be decoded and parsed successfully")
        except Exception as e:
            print(f"✗ Error decoding base64: {e}")
            
        print("\nINSTRUCTIONS:")
        print("1. Use OPTION 1 (Direct JSON) in your GitHub Secret 'GOOGLE_CREDENTIALS'")
        print("2. If that doesn't work, try OPTION 2 (Base64 Encoded)")
        print("3. Update your GitHub workflow to use the approach directly without base64 decoding:")
        print("   echo \"$GOOGLE_CREDENTIALS\" > credentials.json")
        
    except Exception as e:
        print(f"Error processing file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python format_credentials.py your-service-account.json")
        sys.exit(1)
        
    format_for_github(sys.argv[1])