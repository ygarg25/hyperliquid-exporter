"""
    # For jailed validators only (default):
    python script.py
    # or
    python script.py --mode jailed

    # For all validators:
    python script.py --mode all
"""

import logging
from datetime import datetime
import time
from pathlib import Path
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from pytz import timezone, UTC
from typing import List, Dict, Optional
import json
from dataclasses import dataclass
from functools import wraps
import argparse

# Configuration
API_URL = "https://api.hyperliquid-testnet.xyz/info"
RETRY_DELAY = 23  # seconds
MAX_RETRIES = 3

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class GoogleSheetConfig:
    """Configuration for Google Sheets connection"""
    parent_dir: Path
    spreadsheet_name: str
    sheet_name: str
    auth_file: str = 'crypto-analysis-341008-8c7e145e0d97.json'
    
    @property
    def auth_path(self) -> Path:
        return self.parent_dir  / self.auth_file

def retry_on_exception(retries: int = MAX_RETRIES, delay: int = RETRY_DELAY):
    """Decorator to retry functions on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

class GoogleSheetHandler:
    """Handles all Google Sheets operations"""
    def __init__(self, config: GoogleSheetConfig):
        self.config = config
        self.client = self._authenticate()
        
    def _authenticate(self) -> gspread.Client:
        """Authenticate with Google Sheets"""
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            self.config.auth_path, scope
        )
        return gspread.authorize(creds)
    
    def update_sheet(self, values: List[List]) -> None:
        """Update Google Sheet with new values"""
        try:
            spread_sheet = self.client.open(self.config.spreadsheet_name)
            sheet = spread_sheet.worksheet(self.config.sheet_name)
            
            # Append only new data (skip header if data exists)
            records = sheet.get_all_records()
            data_to_append = values[1:] if records else values
            
            spread_sheet.values_append(
                self.config.sheet_name,
                {'valueInputOption': 'USER_ENTERED'},
                {'values': data_to_append}
            )
            logger.info(f"Successfully updated {len(data_to_append)} rows in {self.config.sheet_name}")
        except Exception as e:
            logger.error(f"Error updating Google Sheet: {str(e)}")
            raise

class HyperLiquidAPI:
    """Handles all HyperLiquid API operations"""
    @staticmethod
    @retry_on_exception()
    def fetch_validator_data() -> List[Dict]:
        """Fetch validator data from HyperLiquid API"""
        headers = {'Content-Type': 'application/json'}
        payload = json.dumps({"type": "validatorSummaries"})
        
        response = requests.post(API_URL, headers=headers, data=payload)
        response.raise_for_status()
        
        return response.json()

class DataProcessor:
    """Processes and transforms validator data"""
    @staticmethod
    def add_timestamp(data: List[Dict], timestamp: str) -> List[Dict]:
        """Add timestamp to each data entry"""
        return [{**item, 'date_time_UTC': timestamp} for item in data]
    
    @staticmethod
    def filter_jailed(data: List[Dict]) -> List[Dict]:
        """Filter only jailed validators"""
        return [item for item in data if item['isJailed']]
    
    @staticmethod
    def prepare_for_sheet(data: List[Dict]) -> List[List]:
        """Convert data to format suitable for Google Sheets"""
        if not data:
            return []
        headers = list(data[0].keys())
        return [headers] + [list(item.values()) for item in data]

def hyper_liquid_data_fetch(parent_dir: Path) -> None:
    """Fetch and store all validator data"""
    config = GoogleSheetConfig(
        parent_dir=parent_dir,
        spreadsheet_name='hyperliquid_validator_data',
        sheet_name='validator_info'
    )
    
    while True:
        try:
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            
            # Fetch and process data
            api = HyperLiquidAPI()
            data = api.fetch_validator_data()
            processed_data = DataProcessor.add_timestamp(data, timestamp)
            sheet_data = DataProcessor.prepare_for_sheet(processed_data)
            
            # Update sheet
            if sheet_data:
                sheet_handler = GoogleSheetHandler(config)
                sheet_handler.update_sheet(sheet_data)
                logger.info(f"Successfully processed {len(processed_data)} validators")
            break
            
        except Exception as ex:
            logger.error(f"Error in hyper_liquid_data_fetch: {str(ex)}")
            logger.info(f"Sleep for {RETRY_DELAY} secs.....")
            time.sleep(RETRY_DELAY)
            logger.info("Awake...")
            continue

def hyper_liquid_jailed_data_fetch(parent_dir: Path) -> None:
    """Fetch and store only jailed validator data"""
    config = GoogleSheetConfig(
        parent_dir=parent_dir,
        spreadsheet_name='hyperliquid_validator_data',
        sheet_name='jailed_info'
    )
    
    while True:
        try:
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            
            # Fetch and process data
            api = HyperLiquidAPI()
            data = api.fetch_validator_data()
            processed_data = DataProcessor.add_timestamp(data, timestamp)
            jailed_data = DataProcessor.filter_jailed(processed_data)
            
            # Only proceed if there are jailed validators
            if jailed_data:
                sheet_data = DataProcessor.prepare_for_sheet(jailed_data)
                sheet_handler = GoogleSheetHandler(config)
                sheet_handler.update_sheet(sheet_data)
                logger.info(f"Successfully processed {len(jailed_data)} jailed validators")
            else:
                logger.info("No jailed validators found")
            break
            
        except Exception as ex:
            logger.error(f"Error in hyper_liquid_jailed_data_fetch: {str(ex)}")
            logger.info(f"Sleep for {RETRY_DELAY} secs.....")
            time.sleep(RETRY_DELAY)
            logger.info("Awake...")
            continue

def main():
    parser = argparse.ArgumentParser(description='HyperLiquid Validator Data Collection')
    parser.add_argument('--mode', choices=['all', 'jailed'], default='jailed',
                      help='Data collection mode: all validators or only jailed ones')
    args = parser.parse_args()
    
    parent_dir = Path(__file__).parent
    
    if args.mode == 'all':
        logger.info("Collecting data for all validators...")
        hyper_liquid_data_fetch(parent_dir)
    else:  # jailed
        logger.info("Collecting data for jailed validators only...")
        hyper_liquid_jailed_data_fetch(parent_dir)

if __name__ == "__main__":
    main()