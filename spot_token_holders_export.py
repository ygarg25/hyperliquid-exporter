import requests
from datetime import timezone,datetime
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path

# Define the parent directory for your script
parent_dir = Path(__file__).parent

# Configuration
INFO_API_URL = "https://api.hyperliquid.xyz/info"
HOLDERS_API_URL_TEMPLATE = "https://api.hypurrscan.io/holders/{}"
GOOGLE_SHEET_NAME = "hyperliquid_validator_data"  # Replace with your Google Sheet name
GOOGLE_SHEET_TAB = "hyper_spot_token_holder_data"  # Replace with the tab name in your Google Sheet
AUTH_FILE = parent_dir / "crypto-analysis-341008-b75fdac731c9.json"  # Corrected path concatenation

def fetch_token_names():
    """Fetch token names from the first API."""
    try:
        response = requests.post(
            INFO_API_URL, 
            json={"type": "spotMeta"},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return [token["name"] for token in data.get("tokens", [])]
    except Exception as e:
        print(f"Error fetching token names: {e}")
        raise

def fetch_holders_data(token_name):
    """Fetch holder information for a specific token."""
    url = HOLDERS_API_URL_TEMPLATE.format(token_name)
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()
        return {
            "token": data["token"],
            "last_update": data["lastUpdate"],
            "holders_count": data["holdersCount"],
        }
    except Exception as e:
        print(f"Error fetching holders for {token_name}: {e}")
        raise

def convert_timestamp_to_utc(timestamp):
    """Convert Unix timestamp to human-readable UTC datetime using timezone-aware objects."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def append_to_google_sheet(data):
    """Append data to Google Sheets."""
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(AUTH_FILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open(GOOGLE_SHEET_NAME).worksheet(GOOGLE_SHEET_TAB)
        
        # Append data to the sheet
        sheet.append_rows(data, value_input_option="USER_ENTERED")
        print("Successfully updated Google Sheet.")
    except Exception as e:
        print(f"Error updating Google Sheet: {e}")
        raise

def main():
    try:
        # Fetch token names
        token_names = fetch_token_names()
        print(f"Fetched {len(token_names)} tokens.")
        
        # Collect data for each token
        rows = [["Timestamp (UTC)", "Token Name", "Holders Count", "Date-Time (UTC)"]]
        for ind,token_name in enumerate(token_names):
            print(f"{ind+1}/{len(token_names)}  Processing token: {token_name}")
            try:
                holders_data = fetch_holders_data(token_name)
                utc_time = convert_timestamp_to_utc(holders_data["last_update"])
                rows.append([
                    holders_data["last_update"], 
                    holders_data["token"], 
                    holders_data["holders_count"], 
                    utc_time
                ])
            except Exception as e:
                print(f"Skipping token {token_name} due to error: {e}")
            
            # Wait for 2 seconds before making the next API call
            # time.sleep(2)
        
        # Upload to Google Sheets
        if len(rows) > 1:  # Ensure there's data to append
            print(f"Appending {len(rows) - 1} rows to Google Sheet...")
            append_to_google_sheet(rows)
        else:
            print("No data to append to Google Sheets.")
    
    except Exception as e:
        print(f"Critical error in main execution: {e}")

if __name__ == "__main__":
    main()
