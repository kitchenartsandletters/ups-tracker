# UPS Tracker Database Seeding Tool

This tool automatically identifies and adds all active, undelivered shipments to your UPS Tracker database. It provides seamless integration with ShipStation to ensure no packages are missed in your tracking system.

## Features

- **ShipStation Integration**: Connect directly to your ShipStation account to retrieve all active shipments
- **CSV Import**: Support for importing tracking data from CSV files with flexible column mapping
- **Custom API Support**: Connect to other shipping platforms via custom API endpoints
- **Duplicate Prevention**: Automatically detects and skips existing tracking numbers
- **Carrier Detection**: Identifies shipping carriers (UPS, USPS, FedEx, DHL) based on tracking number patterns
- **Date Filtering**: Import only shipments from a specific date range
- **Detailed Reporting**: Generates comprehensive logs and summary reports

## Prerequisites

Before running the tool, ensure you have:

1. Python 3.6 or higher installed
2. The required Python packages (listed in `requirements.txt`)
3. Access to your ShipStation account with API credentials
4. Access to your Google Sheets UPS Tracker (same as the main tracking script)

## Installation

1. Download the seeding tool script and place it in your UPS Tracker project directory
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

### ShipStation API Setup

1. Log in to your ShipStation account
2. Go to **Account Settings** → **Account** → **API Settings**
3. Generate an API Key
4. Store this credential securely as an environment variable:

```bash
export SHIPSTATION_API_KEY="your_api_key"
```

Note: The script is compatible with both ShipStation API V2 (newer) and V1 (older). It will automatically attempt to use V2 first, then fall back to V1 if needed.

### Google Sheets Configuration

The tool uses the same Google Sheets credentials as the main tracking script. Ensure your `GOOGLE_CREDENTIALS` environment variable is properly set:

```bash
export GOOGLE_CREDENTIALS="your_google_credentials_json"
```

## Usage

### Seeding from ShipStation (Recommended)

To import all active shipments from ShipStation:

```bash
python seed_tracking_database.py --source shipstation --days 30
```

The `--days` parameter specifies how far back to look for shipments (default: 30 days).

### Importing from CSV

If you have tracking data in a CSV file:

```bash
python seed_tracking_database.py --source csv --csv-file shipments.csv --days 30
```

The tool automatically attempts to detect the appropriate columns in your CSV.

### Using a Custom API

To connect to a custom shipping API:

```bash
python seed_tracking_database.py --source api --api-url https://your-api.com/shipments --days 30
```

You may need to set the `CUSTOM_API_KEY` environment variable if your API requires authentication.

## Adding to GitHub Actions

You can automate the seeding process by adding it to your GitHub Actions workflow. Here's a sample workflow configuration:

```yaml
name: Seed Tracking Database

on:
  schedule:
    - cron: '0 0 * * 0'  # Run weekly on Sunday at midnight
  workflow_dispatch:     # Allow manual trigger

jobs:
  seed:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          
      - name: Seed tracking database
        env:
          SHIPSTATION_API_KEY: ${{ secrets.SHIPSTATION_API_KEY }}
          SHIPSTATION_API_SECRET: ${{ secrets.SHIPSTATION_API_SECRET }}
          GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}
        run: |
          python seed_tracking_database.py --source shipstation --days 30
```

Make sure to add your `SHIPSTATION_API_KEY` and `SHIPSTATION_API_SECRET` to your GitHub repository secrets.

## Troubleshooting

### Common Issues

1. **API Authentication Errors**: Verify your ShipStation API credentials are correct and properly exported as environment variables.

2. **Google Sheets Connection Issues**: Ensure your Google service account has access to the UPS Tracker sheet.

3. **No Shipments Found**: Check that you have active shipments within the date range specified by the `--days` parameter.

### Detailed Logging

The tool creates a detailed log file named `seeding_tool.log` in the current directory. If you encounter issues, check this file for more information:

```bash
tail -f seeding_tool.log
```

A summary report is also generated after each run with statistics on added shipments, duplicates, and errors.

## Contributing

Feel free to enhance this tool with additional features or improvements. Some ideas:

- Add support for more shipping carriers
- Implement more sophisticated duplicate detection
- Add a web interface for manual operation

Please follow the existing code style and include appropriate tests and documentation for any new features.

## License

This tool is subject to the same license as the main UPS Tracker project.