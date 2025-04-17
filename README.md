# UPS Package Tracking to Google Sheets

This project automates tracking UPS packages and logs their statuses to a Google Sheet on a regular schedule using GitHub Actions.

## Features

- **Package Tracking**: Retrieve real-time package status and location using UPS Tracking API
- **Address Validation**: Validate delivery addresses with UPS Address Validation API
- **Delivery Estimates**: Get estimated delivery times using UPS Time in Transit API
- **Real-time Alerts**: Subscribe to push notifications with UPS Track Alert API
- **Automated Updates**: Scheduled tracking updates every 6 hours via GitHub Actions

## Setup Instructions

### Prerequisites

1. UPS Developer Account with the following APIs enabled:
   - Tracking API
   - Address Validation API
   - Time in Transit API
   - Track Alert API

2. Google Cloud account with:
   - Google Sheets API enabled
   - Google Drive API enabled
   - Service Account with credentials

3. GitHub account

### Installation

1. Clone this repository
```bash
git clone https://github.com/kitchenartsandletters.com/ups-tracker.git
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
   - Column G: Alert Status

4. Share the Google Sheet with your service account email address

5. Set up GitHub Secrets in your repository:
   - `UPS_CLIENT_ID`: Your UPS API Client ID
   - `UPS_CLIENT_SECRET`: Your UPS API Client Secret
   - `GOOGLE_SHEET_ID`: The ID of your Google Sheet
   - `GOOGLE_CREDENTIALS`: Base64-encoded Google service account JSON credentials
   - `NOTIFICATION_EMAIL`: Email for receiving tracking alerts
   - `ORIGIN_CITY`, `ORIGIN_STATE`, `ORIGIN_ZIP`: Optional origin address for time-in-transit estimates

### Usage

#### Manual Run

You can run the script manually:

```bash
python updated_track_packages.py
```

#### Automated Run

The GitHub Action workflow will run automatically every 6 hours. You can also trigger it manually via the GitHub Actions tab.

## File Structure

- `updated_track_packages.py`: Main script that handles tracking and API communication
- `requirements.txt`: Python dependencies
- `.github/workflows/github_workflow.yml`: GitHub Actions workflow definition

## Contributing

Contributions are welcome! Feel free to submit a pull request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.