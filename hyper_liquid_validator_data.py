"""
    # For jailed validators only (default):
    python hyper_liquid_validator_data.py
    # or
    python hyper_liquid_validator_data.py --mode jailed

    # For all validators:
    python hyper_liquid_validator_data.py --mode all
"""

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
import time
from pathlib import Path
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from pytz import timezone, UTC
from typing import List, Dict, Optional, Deque
import json
from dataclasses import dataclass
from functools import wraps
import os
import argparse
from collections import deque

# Configuration
API_URL = "https://api.hyperliquid-testnet.xyz/info"
RETRY_DELAY = 23  # seconds
MAX_RETRIES = 3
MAX_CALLS_PER_MINUTE = 30  # Adjust based on API limits
INITIAL_BACKOFF = 1  # seconds
MAX_BACKOFF = 300  # seconds (5 minutes)
DEFAULT_RETRY_AFTER = 60  # seconds
MAX_ATTEMPTS = 3

class APIRateLimiter:
    def __init__(self, max_calls_per_minute: int = MAX_CALLS_PER_MINUTE):
        self.calls: Deque[datetime] = deque()
        self.max_calls = max_calls_per_minute
        self.window = timedelta(minutes=1)
        self.logger = logging.getLogger(__name__)

    def wait_if_needed(self):
        now = datetime.now()
        # Remove old calls
        while self.calls and (now - self.calls[0]) > self.window:
            self.calls.popleft()
        
        # Check if we need to wait
        if len(self.calls) >= self.max_calls:
            wait_time = (self.calls[0] + self.window - now).total_seconds()
            if wait_time > 0:
                self.logger.warning(f"Rate limit approaching, waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
        
        self.calls.append(now)
        self.logger.debug(f"Current API calls in window: {len(self.calls)}")

def setup_logging(mode: str):
    """Set up logging with file rotation"""
    # Create logs directory
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with mode
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
    auth_file: str = 'crypto-analysis-341008-b75fdac731c9.json'
    
    @property
    def auth_path(self) -> Path:
        return self.parent_dir / self.auth_file

def retry_on_exception(retries: int = MAX_RETRIES, delay: int = RETRY_DELAY):
    """Decorator to retry functions on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(__name__)
            last_exception = None
            
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == retries - 1:
                        logger.error(f"All retry attempts failed for {func.__name__}: {str(e)}")
                        raise last_exception
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
        self.rate_limiter = APIRateLimiter()
        self.backoff_time = INITIAL_BACKOFF

    def _handle_rate_limit(self, response: requests.Response) -> int:
        """Handle rate limit response and return wait time"""
        retry_after = int(response.headers.get('Retry-After', DEFAULT_RETRY_AFTER))
        self.logger.warning(f"Rate limit hit (429). Retry after: {retry_after} seconds")
        return retry_after

    def _exponential_backoff(self) -> None:
        """Implement exponential backoff"""
        wait_time = min(self.backoff_time, MAX_BACKOFF)
        self.logger.info(f"Backing off for {wait_time} seconds")
        time.sleep(wait_time)
        self.backoff_time *= 2

    def fetch_validator_data(self) -> Optional[List[Dict]]:
        """Fetch validator data with improved error handling and rate limiting"""
        attempt = 0

        while attempt < MAX_RETRIES:
            try:
                self.rate_limiter.wait_if_needed()
                
                self.logger.info(f"Fetching validator data (attempt {attempt + 1}/{MAX_RETRIES})")
                headers = {'Content-Type': 'application/json'}
                payload = json.dumps({"type": "validatorSummaries"})
                
                response = requests.post(API_URL, headers=headers, data=payload)
                
                if response.status_code == 200:
                    self.backoff_time = INITIAL_BACKOFF  # Reset backoff on success
                    data = response.json()
                    self.logger.info(f"Successfully fetched data for {len(data)} validators")
                    return data
                
                elif response.status_code == 429:
                    wait_time = self._handle_rate_limit(response)
                    time.sleep(wait_time)
                
                else:
                    response.raise_for_status()
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
                self._exponential_backoff()
            
            except Exception as e:
                self.logger.error(f"Unexpected error (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
                self._exponential_backoff()
            
            attempt += 1

        self.logger.error("Max retries reached, giving up")
        return None

class DataProcessor:
    """Processes and transforms validator data"""
    @staticmethod
    def flatten_stats(stats_data: List) -> dict:
        """Convert stats array to flattened dictionary with specific uptime metrics"""
        flattened = {}
        for period, data in stats_data:
            flattened[f"{period}_uptime"] = float(data.get("uptimeFraction", "0"))
        return flattened

    @staticmethod
    def process_validator(validator: Dict, timestamp: str) -> Dict:
        """Process a single validator entry with specific order of fields"""
        # Extract base fields we want to keep
        base_data = {
            "validator": validator.get("validator"),
            "signer": validator.get("signer"),
            "name": validator.get("name"),
            "description": validator.get("description"),
            "nRecentBlocks": validator.get("nRecentBlocks"),
            "stake": validator.get("stake"),
            "isJailed": validator.get("isJailed"),
            "unjailableAfter": validator.get("unjailableAfter"),
            "isActive": validator.get("isActive"),
            "date_time_UTC": timestamp
        }
        
        # Process stats
        stats = validator.get('stats', [])
        stats_dict = DataProcessor.flatten_stats(stats)
        
        # Combine in desired order
        return {
            **base_data,
            "day_uptime": stats_dict.get("day_uptime", 0),
            "week_uptime": stats_dict.get("week_uptime", 0),
            "month_uptime": stats_dict.get("month_uptime", 0)
        }

    @staticmethod
    def add_timestamp(data: List[Dict], timestamp: str) -> List[Dict]:
        """Add timestamp to each data entry"""
        return [DataProcessor.process_validator(item, timestamp) for item in data]
    
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
        return [headers] + [[item[key] for key in headers] for item in data]
def hyper_liquid_data_fetch(parent_dir: Path) -> None:
    """Fetch and store all validator data"""
    logger = logging.getLogger(__name__)
    config = GoogleSheetConfig(
        parent_dir=parent_dir,
        spreadsheet_name='hyperliquid_validator_data',
        sheet_name='validator_info'
    )
    
    attempt = 0
    while attempt < MAX_ATTEMPTS:
        try:
            logger.info("Starting data fetch for all validators")
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            
            api = HyperLiquidAPI()
            data = api.fetch_validator_data()
            
            if data is None:
                logger.error("Failed to fetch data, will retry")
                attempt += 1
                time.sleep(RETRY_DELAY)
                continue
                
            processed_data = DataProcessor.add_timestamp(data, timestamp)
            sheet_data = DataProcessor.prepare_for_sheet(processed_data)
            
            if sheet_data:
                sheet_handler = GoogleSheetHandler(config)
                sheet_handler.update_sheet(sheet_data)
                logger.info("All validator data successfully processed and stored")
            break
            
        except Exception as ex:
            attempt += 1
            logger.error(f"Error in data fetch (attempt {attempt}/{MAX_ATTEMPTS}): {str(ex)}")
            if attempt < MAX_ATTEMPTS:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max attempts reached, giving up")
                raise

def hyper_liquid_jailed_data_fetch(parent_dir: Path) -> None:
    """Fetch and store only jailed validator data"""
    logger = logging.getLogger(__name__)
    config = GoogleSheetConfig(
        parent_dir=parent_dir,
        spreadsheet_name='hyperliquid_validator_data',
        sheet_name='jailed_info'
    )
    
    attempt = 0
    while attempt < MAX_ATTEMPTS:
        try:
            logger.info("Starting data fetch for jailed validators")
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            
            api = HyperLiquidAPI()
            data = api.fetch_validator_data()
            
            if data is None:
                logger.error("Failed to fetch data, will retry")
                attempt += 1
                time.sleep(RETRY_DELAY)
                continue
                
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
            attempt += 1
            logger.error(f"Error in jailed data fetch (attempt {attempt}/{MAX_ATTEMPTS}): {str(ex)}")
            if attempt < MAX_ATTEMPTS:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max attempts reached, giving up")
                raise

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