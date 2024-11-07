"""
    # For jailed validators only (default):
    python script.py
    # or
    python script.py --mode jailed

    # For all validators:
    python script.py --mode all
"""

import logging
from logging.handlers import RotatingFileHandler
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
import os
import argparse

# Configuration
API_URL = "https://api.hyperliquid-testnet.xyz/info"
RETRY_DELAY = 23  # seconds
MAX_RETRIES = 3

def setup_logging(mode: str):
    """Set up logging with file rotation"""
    # Create logs directory
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with date and mode
    # log_file = log_dir / f'validator_collector_{mode}_{datetime.now().strftime("%Y-%m-%d")}.log'
    log_file = log_dir / f'validator_collector_{mode}.log'

    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Set up rotating file handler (10MB per file, keep 30 files)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=30
    )
    file_handler.setFormatter(formatter)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    logger.handlers = []
    
    # Add the handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logging.info(f"Logging setup completed for mode: {mode}")
    return logging.getLogger(__name__)

@dataclass
class GoogleSheetConfig:
    """Configuration for Google Sheets connection"""
    parent_dir: Path
    spreadsheet_name: str
    sheet_name: str
    auth_file: str = 'crypto-analysis-341008-8c7e145e0d97.json'
    
    @property
    def auth_path(self) -> Path:
        return self.parent_dir / self.auth_file

def retry_on_exception(retries: int = MAX_RETRIES, delay: int = RETRY_DELAY):
    """Decorator to retry functions on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(__name__)
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == retries - 1:
                        logger.error(f"All retry attempts failed for {func.__name__}: {str(e)}")
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}")
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

class GoogleSheetHandler:
    """Handles all Google Sheets operations"""
    def __init__(self, config: GoogleSheetConfig):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.client = self._authenticate()
        
    def _authenticate(self) -> gspread.Client:
        """Authenticate with Google Sheets"""
        self.logger.info("Authenticating with Google Sheets...")
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(
                self.config.auth_path, scope
            )
            client = gspread.authorize(creds)
            self.logger.info("Successfully authenticated with Google Sheets")
            return client
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            raise
    
    def update_sheet(self, values: List[List]) -> None:
        """Update Google Sheet with new values"""
        try:
            self.logger.info(f"Updating sheet: {self.config.spreadsheet_name}/{self.config.sheet_name}")
            spread_sheet = self.client.open(self.config.spreadsheet_name)
            sheet = spread_sheet.worksheet(self.config.sheet_name)
            
            records = sheet.get_all_records()
            data_to_append = values[1:] if records else values
            
            spread_sheet.values_append(
                self.config.sheet_name,
                {'valueInputOption': 'USER_ENTERED'},
                {'values': data_to_append}
            )
            self.logger.info(f"Successfully updated {len(data_to_append)} rows")
        except Exception as e:
            self.logger.error(f"Failed to update sheet: {str(e)}")
            raise

class HyperLiquidAPI:
    """Handles all HyperLiquid API operations"""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    @retry_on_exception()
    def fetch_validator_data(self) -> List[Dict]:
        """Fetch validator data from HyperLiquid API"""
        self.logger.info("Fetching validator data from API...")
        headers = {'Content-Type': 'application/json'}
        payload = json.dumps({"type": "validatorSummaries"})
        
        response = requests.post(API_URL, headers=headers, data=payload)
        response.raise_for_status()
        
        data = response.json()
        self.logger.info(f"Successfully fetched data for {len(data)} validators")
        return data

class DataProcessor:
    """Processes and transforms validator data"""
    @staticmethod
    def add_timestamp(data: List[Dict], timestamp: str) -> List[Dict]:
        """Add timestamp to each data entry"""
        return [{**item, 'date_time_UTC': timestamp} for item in data]
    
    @staticmethod
    def filter_jailed(data: List[Dict]) -> List[Dict]:
        """Filter only jailed validators"""
        jailed = [item for item in data if item['isJailed']]
        logging.getLogger(__name__).info(f"Found {len(jailed)} jailed validators")
        return jailed
    
    @staticmethod
    def prepare_for_sheet(data: List[Dict]) -> List[List]:
        """Convert data to format suitable for Google Sheets"""
        if not data:
            return []
        headers = list(data[0].keys())
        return [headers] + [list(item.values()) for item in data]

def hyper_liquid_data_fetch(parent_dir: Path) -> None:
    """Fetch and store all validator data"""
    logger = logging.getLogger(__name__)
    config = GoogleSheetConfig(
        parent_dir=parent_dir,
        spreadsheet_name='hyperliquid_validator_data',
        sheet_name='validator_info'
    )
    
    while True:
        try:
            logger.info("Starting data fetch for all validators")
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            
            api = HyperLiquidAPI()
            data = api.fetch_validator_data()
            processed_data = DataProcessor.add_timestamp(data, timestamp)
            sheet_data = DataProcessor.prepare_for_sheet(processed_data)
            
            if sheet_data:
                sheet_handler = GoogleSheetHandler(config)
                sheet_handler.update_sheet(sheet_data)
                logger.info("All validator data successfully processed and stored")
            break
            
        except Exception as ex:
            logger.error(f"Error in data fetch: {str(ex)}")
            logger.info(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
            continue

def hyper_liquid_jailed_data_fetch(parent_dir: Path) -> None:
    """Fetch and store only jailed validator data"""
    logger = logging.getLogger(__name__)
    config = GoogleSheetConfig(
        parent_dir=parent_dir,
        spreadsheet_name='hyperliquid_validator_data',
        sheet_name='jailed_info'
    )
    
    while True:
        try:
            logger.info("Starting data fetch for jailed validators")
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            
            api = HyperLiquidAPI()
            data = api.fetch_validator_data()
            processed_data = DataProcessor.add_timestamp(data, timestamp)
            jailed_data = DataProcessor.filter_jailed(processed_data)
            
            if jailed_data:
                sheet_data = DataProcessor.prepare_for_sheet(jailed_data)
                sheet_handler = GoogleSheetHandler(config)
                sheet_handler.update_sheet(sheet_data)
                logger.info("Jailed validator data successfully processed and stored")
            else:
                logger.info("No jailed validators found")
            break
            
        except Exception as ex:
            logger.error(f"Error in jailed data fetch: {str(ex)}")
            logger.info(f"Retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
            continue

def main():
    parser = argparse.ArgumentParser(description='HyperLiquid Validator Data Collection')
    parser.add_argument('--mode', choices=['all', 'jailed'], default='jailed',
                      help='Data collection mode: all validators or only jailed ones')
    args = parser.parse_args()
    
    # Setup logging based on mode
    logger = setup_logging(args.mode)
    
    parent_dir = Path(__file__).parent
    
    try:
        if args.mode == 'all':
            logger.info("Starting collection for all validators...")
            hyper_liquid_data_fetch(parent_dir)
        else:  # jailed
            logger.info("Starting collection for jailed validators only...")
            hyper_liquid_jailed_data_fetch(parent_dir)
    except Exception as e:
        logger.critical(f"Critical error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    main()