# UPS Package Tracking to Google Sheets

## Objective
Automate the tracking of UPS packages and log their statuses in a Google Sheet every 6 hours using the UPS Tracking API. The project will be built with:

- **UPS Tracking API** for real-time package status.
- **Google Sheets** as the primary data store.
- **GitHub Actions** for scheduled execution (cron job).
- **Google Sheets API** to interact with the sheet.
- **GitHub Secrets** for securely storing UPS API credentials.

---

## Architecture Overview

1. **Tracking Numbers**: Stored in a dedicated Google Sheet (Column A).
2. **Script**: Node.js or Python script queries UPS Tracking API and updates statuses.
3. **Google Sheets API**: Reads and writes to the sheet.
4. **GitHub Actions**: Runs the script on a 6-hour schedule.
5. **Secrets Management**: UPS credentials and Google service account stored in GitHub Secrets.

---

## Setup Steps

### 1. Get UPS Developer API Access
- Sign up at [UPS Developer Portal](https://developer.ups.com/).
- Create a new app.
- Note your **Client ID**, **Client Secret**, and any other required keys.
- Choose the **Tracking API** from the API catalog.
- Follow their [OAuth 2.0 setup guide](https://developer.ups.com/oauth-migration-guide).

### 2. Create and Share Google Sheet
- Create a sheet titled `UPS Tracker` with columns:
  - Column A: `Tracking Number`
  - Column B: `Status`
  - Column C: `Last Update`
  - Column D: `Current Location`
- Share it with the service account email (created in the next step).

### 3. Enable Google Sheets API
- Go to [Google Cloud Console](https://console.cloud.google.com/).
- Create a project > Enable **Google Sheets API** and **Google Drive API**.
- Create a **service account**, download the JSON credentials file.

### 4. Script Development
Use **Python** or **Node.js** to:
- Authenticate with Google Sheets using service account JSON.
- Authenticate with UPS using OAuth 2.0.
- Read tracking numbers from the sheet.
- Query UPS Tracking API.
- Parse response and update the Google Sheet.

#### Python Packages
```bash
pip install gspread google-auth requests
```

#### Node.js Packages
```bash
npm install googleapis axios dotenv
```

---

## Example Workflow

1. GitHub repository contains:
   - `/src/track_packages.py` or `/src/trackPackages.js`
   - `/credentials/service_account.json` (ignored in Git)
   - `.github/workflows/scheduler.yml`

2. GitHub Actions Workflow Example:
```yaml
name: Track UPS Packages

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  track:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run script
        env:
          UPS_CLIENT_ID: ${{ secrets.UPS_CLIENT_ID }}
          UPS_CLIENT_SECRET: ${{ secrets.UPS_CLIENT_SECRET }}
          UPS_USERNAME: ${{ secrets.UPS_USERNAME }}
          UPS_PASSWORD: ${{ secrets.UPS_PASSWORD }}
          GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}
          GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}  # Base64-encoded JSON
        run: |
          echo "$GOOGLE_CREDENTIALS" | base64 -d > credentials.json
          python src/track_packages.py
```

---

## Script Responsibilities

- Authenticate to UPS and get OAuth token.
- Read all tracking numbers from column A.
- For each number, call the Tracking API.
- Parse `status`, `date/time`, and `location`.
- Write updates into columns B, C, D.
- Optionally log changes to a local log or Google Sheet tab.

---

## Security
- **Google credentials** stored in GitHub Secrets as a base64-encoded string.
- **UPS credentials** stored in Secrets for use in GitHub Actions.

---

## Future Enhancements
- Email or Slack notifications for status changes.
- Archive delivered packages.
- Support other carriers via modular API calls.
- Web dashboard or Slack command integration.

---

## Next Steps
- [ ] Sign up for UPS Developer access.
- [ ] Create and share Google Sheet.
- [ ] Build and test the script locally.
- [ ] Set up GitHub repository and push code.
- [ ] Add secrets to GitHub.
- [ ] Set up GitHub Actions cron job.
- [ ] Monitor and iterate.

