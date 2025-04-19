# UPS Package Tracking to Google Sheets
## UPDATED: April 19, 2025

This project automates tracking UPS, USPS, and DHL packages and logs their statuses to a Google Sheet on a regular schedule using GitHub Actions.

## Features

- **Package Tracking**: Retrieve real-time package status and location using UPS, USPS, and DHL APIs
- **Address Validation**: Validate delivery addresses with UPS Address Validation API
- **Delivery Estimates**: Get estimated delivery times directly from tracking data
- **Human-Friendly Dates**: All dates and times are formatted for easy reading
- **Automated Updates**: Scheduled tracking updates every 6 hours via GitHub Actions

## Setup Instructions

### Prerequisites

1. UPS Developer Account with the following APIs enabled:
   - Tracking API
   - Address Validation API 
   - Time in Transit API (optional, provides fallback delivery estimates)

2. Google Cloud account with:
   - Google Sheets API enabled
   - Google Drive API enabled
   - Service Account with credentials

3. GitHub account

### Installation

1. Clone this repository
```bash
git clone https://github.com/yourusername/ups-tracker.git
cd ups-tracker
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Create a Google Sheet called "UPS Tracker" with these columns:
   - Column A: Tracking Number
   - Column B: Status
   - Column C: Last Update
   - Column D: Current Location
   - Column E: Validated Address
   - Column F: Estimated Delivery

4. Share the Google Sheet with your service account email address

5. Set up GitHub Secrets in your repository:
   - `UPS_CLIENT_ID`: Your UPS API Client ID
   - `UPS_CLIENT_SECRET`: Your UPS API Client Secret
   - `GOOGLE_CREDENTIALS`: Your Google service account JSON credentials
   - `ORIGIN_STREET`: Street address for origin (for Time in Transit estimates)
   - `ORIGIN_CITY`: City for origin address
   - `ORIGIN_STATE`: State for origin address (two-letter code)
   - `ORIGIN_ZIP`: ZIP code for origin address

### Usage

#### Manual Run

You can run the script manually:

```bash
python updated_track_packages.py
```

#### Automated Run

The GitHub Action workflow will run automatically every 6 hours. You can also trigger it manually via the GitHub Actions tab.

## Key Learnings

1. **UPS API Configuration**: 
   - Each UPS API must be explicitly activated in the UPS Developer Portal
   - You need distinct permission for each API you want to use
   - OAuth token acquisition works independently from API permissions

2. **API Response Handling**:
   - UPS date formats need conversion to be human-readable
   - Response formats may vary between different tracking numbers
   - Fallback options improve reliability when specific data is missing

3. **Google Sheets Integration**:
   - Use batch updates instead of individual updates for better performance
   - The latest gspread library recommends specific parameter patterns

4. **Address Validation**:
   - Not all tracking responses include complete address information
   - Validate incomplete addresses when necessary, but handle validation failures gracefully

5. **Estimated Delivery Times**:
   - Primary source: Package tracking data (most accurate)
   - Fallback: Time in Transit API (when tracking doesn't include delivery date)

## File Structure

- `updated_track_packages.py`: Main script that handles tracking and API communication
- `requirements.txt`: Python dependencies
- `.github/workflows/github_workflow.yml`: GitHub Actions workflow definition
- `format_credentials.py`: Helper script for formatting Google credentials
- `test_credentials.py`: Test script to verify credentials are working

## ShipStation Integration

The UPS Tracker tool now supports automatically seeding UPS tracking numbers from ShipStation via the ShipStation API V2.

### Setup

1. Generate a ShipStation API key:
   - Log in to ShipStation and navigate to **Settings → Account → API Settings**.
   - Click **Generate API Key** to create your credentials.

2. Add your API key to GitHub Secrets:
   - **Name**: SHIPSTATION_API_KEY  
   - **Value**: <your ShipStation API key>

### Usage

Run the seeding tool to populate your tracking database with UPS shipments seeded from ShipStation:

```bash
python minimal_tracking_seeder.py
```

### API Notes

- **Date Window**: The tool filters shipments created in the past **120 days** using ISO 8601 timestamps (`created_at_start` and `created_at_end` query parameters).
- **Sorting**: Results are sorted by `created_at` in **descending** order (`sort_by=created_at`, `sort_dir=desc`) so that the newest shipments are processed first.
- **Pagination**: The script limits to **20 pages** (`page` and `page_size`) to prevent long backfills.
- **Parameter Naming**: Uses **snake_case** for all API parameters:
  - `created_at_start`, `created_at_end` (not `createDateStart`/`createDateEnd`)
  - `page_size` (not `pageSize`)
  - `sort_by`, `sort_dir` (not `sortBy`/`sortDir`)
- **Label Endpoint**: Fetches package-level tracking via `GET /v2/labels?shipment_id={shipment_id}&page=1&page_size=100`.
- **Carrier Filtering**: Strictly matches UPS numbers with `re.fullmatch(r'^1Z[0-9A-Z]{16}$|^T\d{10}$|^\d{9}$')`.
- **Authentication**: Include your API key in the headers:
  ```python
  headers = {
      'API-Key': SHIPSTATION_API_KEY,
      'Content-Type': 'application/json'
  }
  ```
- **Duplicate Prevention**: Existing tracking numbers in column A are skipped, ensuring no duplicates.

## Improvement Roadmap

See the Issues tab for planned improvements:

1. Optimize cron job frequency for better data timeliness
2. Add support for multiple Google Sheets
3. Enable direct integration with e-commerce platforms (Shopify, ShipStation, etc.)
4. Expand multi-carrier support for international shipments (USPS, DHL)
5. Add email notifications for delivery exceptions
6. Create a database seeding tool for adding all in-transit shipments 

## Contributing

Contributions are welcome! Feel free to submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details