#!/usr/bin/python3
"""
Hyperliquid Validator Monitor
============================
Features:
- Monitors validator status every minute
- Auto-unjail with 30 minute initial wait
- Retries failed unjail every 10 minutes
- Detailed unjail logging
- Rotates logs to manage space
"""

import requests
import json
import time
import subprocess
import logging
import os
import sys
import argparse
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler, SysLogHandler
from pathlib import Path
from typing import Tuple, Dict, Optional

# Constants
CHECK_INTERVAL = 60  # 1 minute
UNJAIL_WAIT_TIME = 1800  # 30 minutes
RETRY_WAIT_TIME = 600  # 10 minutes
MAX_RETRIES = 5

class ValidatorMonitor:
    def __init__(self, logger, validator_address: str, private_key: str):
        self.logger = logger
        self.validator_address = validator_address
        self.private_key = private_key
        self.last_jailed_time = None
        self.last_unjail_attempt = None
        self.retry_count = 0
        
        # Create unjail log file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.unjail_log_path = os.path.join(script_dir, 'logs', 'unjail_history.log')

    def log_unjail_attempt(self, response: dict, success: bool):
        """Log detailed information about unjail attempt"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = (
                f"\n{'='*50}\n"
                f"UNJAIL ATTEMPT LOG\n"
                f"Timestamp: {timestamp}\n"
                f"Attempt #: {self.retry_count}\n"
                f"Validator: {self.validator_address}\n"
                f"Success: {success}\n"
                f"Response: {json.dumps(response, indent=2)}\n"
                f"{'='*50}\n"
            )
            
            with open(self.unjail_log_path, 'a') as f:
                f.write(log_entry)
                
            self.logger.info(f"Unjail attempt logged to {self.unjail_log_path}")
        except Exception as e:
            self.logger.error(f"Failed to write unjail log: {e}")

    def check_validator_status(self) -> Optional[Dict]:
        """Check validator status from API"""
        try:
            response = requests.post(
                'https://api.hyperliquid-testnet.xyz/info',
                headers={'Content-Type': 'application/json'},
                json={'type': 'validatorSummaries'}
            )
            response.raise_for_status()
            validators = response.json()
            
            for validator in validators:
                if validator['validator'].lower() == self.validator_address.lower():
                    return validator
            return None
        except Exception as e:
            self.logger.error(f"Error checking validator status: {str(e)}")
            return None

    def unjail_validator(self) -> bool:
        """Execute unjail command with response logging"""
        self.retry_count += 1
        
        try:
            # Execute unjail command
            cmd = f'~/hl-node --chain Testnet --key {self.private_key} send-signed-action \'{{"type": "CSignerAction", "unjailSelf": null}}\''
            self.logger.info(f"Executing unjail attempt #{self.retry_count}")
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            response_data = {}
            
            # Process command output
            if result.stdout:
                try:
                    response_data = json.loads(result.stdout)
                    self.logger.info(f"Unjail response: {json.dumps(response_data, indent=2)}")
                except json.JSONDecodeError:
                    response_data = {"raw_output": result.stdout}
                    self.logger.info(f"Raw unjail output: {result.stdout}")
            
            if result.stderr:
                response_data["error"] = result.stderr
                self.logger.error(f"Unjail error: {result.stderr}")
            
            # Verify unjail success
            success = False
            if response_data.get('status') == 'ok':
                self.logger.info("Unjail command accepted, verifying status...")
                time.sleep(10)  # Wait for network to process
                
                validator = self.check_validator_status()
                if validator and not validator['isJailed']:
                    success = True
                    self.logger.info("✅ Validator successfully unjailed!")
                    self.retry_count = 0
                    self.last_jailed_time = None
                else:
                    self.logger.error("❌ Validator still jailed after unjail attempt")
            
            # Log attempt details
            self.log_unjail_attempt(response_data, success)
            self.last_unjail_attempt = datetime.now()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error in unjail attempt: {str(e)}")
            self.log_unjail_attempt({"error": str(e)}, False)
            self.last_unjail_attempt = datetime.now()
            return False

    def monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting validator monitoring...")
        
        while True:
            try:
                validator = self.check_validator_status()
                
                if validator:
                    status_msg = (
                        f"Validator status: "
                        f"Name={validator['name']}, "
                        f"isJailed={validator['isJailed']}, "
                        f"nRecentBlocks={validator['nRecentBlocks']}, "
                        f"isActive={validator['isActive']}"
                    )
                    self.logger.info(status_msg)
                    
                    if validator['isJailed']:
                        current_time = datetime.now()
                        
                        # First jail detection
                        if not self.last_jailed_time:
                            self.last_jailed_time = current_time
                            self.retry_count = 0
                            self.logger.warning(f"⚠️ Validator jailed at {current_time}")
                        
                        # Check if we should attempt unjail
                        time_since_jail = (current_time - self.last_jailed_time).total_seconds()
                        
                        if time_since_jail >= UNJAIL_WAIT_TIME:
                            if self.retry_count >= MAX_RETRIES:
                                self.logger.error(f"❌ Max retries ({MAX_RETRIES}) reached. Manual intervention required.")
                            else:
                                # Check if it's time for retry
                                should_retry = True
                                if self.last_unjail_attempt:
                                    time_since_attempt = (current_time - self.last_unjail_attempt).total_seconds()
                                    should_retry = time_since_attempt >= RETRY_WAIT_TIME
                                
                                if should_retry:
                                    self.logger.info(f"Attempting unjail (try #{self.retry_count + 1})")
                                    if self.unjail_validator():
                                        break  # Exit retry loop if successful
                                else:
                                    wait_time = RETRY_WAIT_TIME - (current_time - self.last_unjail_attempt).total_seconds()
                                    self.logger.info(f"⏳ Waiting {wait_time:.0f} seconds until next retry...")
                        else:
                            wait_time = UNJAIL_WAIT_TIME - time_since_jail
                            self.logger.info(f"⏳ Waiting {wait_time:.0f} seconds before first unjail attempt...")
                    else:
                        self.last_jailed_time = None
                        self.retry_count = 0
                else:
                    self.logger.error(f"❌ Cannot find validator {self.validator_address}")
            
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}")
            
            time.sleep(CHECK_INTERVAL)

def setup_logging() -> Tuple[logging.Logger, str]:
    """Setup logging configuration"""
    logger = logging.getLogger('ValidatorMonitor')
    logger.setLevel(logging.INFO)
    
    # Create log directory in script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Format for logs
    formatter = logging.Formatter('%(asctime)s - ValidatorMonitor - %(levelname)s - %(message)s')
    
    # Main log file with rotation
    main_log = os.path.join(log_dir, 'validator_monitor.log')
    file_handler = RotatingFileHandler(
        main_log,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger, log_dir

def load_env_file(logger) -> Optional[Dict]:
    """Load environment variables from .env_hyper file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, '.env_hyper')
    
    try:
        logger.info(f"Loading environment from: {file_path}")
        with open(file_path, 'r') as file:
            env_vars = {}
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"\'')
            return env_vars
    except FileNotFoundError:
        logger.error(f"Environment file not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"Error reading environment file: {str(e)}")
        return None

def main():
    # Setup logging
    logger, log_dir = setup_logging()
    logger.info("Starting Validator Monitor")
    
    # Load environment variables
    env_vars = load_env_file(logger)
    if not env_vars:
        logger.error("Failed to load environment variables. Exiting...")
        sys.exit(1)
    
    # Get required variables
    PRIVATE_KEY = env_vars.get('PRIVATE_KEY')
    VALIDATOR_ADDRESS = env_vars.get('VALIDATOR_ADDRESS')
    
    if not PRIVATE_KEY or not VALIDATOR_ADDRESS:
        logger.error("Missing required environment variables. Exiting...")
        sys.exit(1)
    
    # Create and start monitor
    monitor = ValidatorMonitor(logger, VALIDATOR_ADDRESS, PRIVATE_KEY)
    monitor.monitor_loop()

if __name__ == "__main__":
    main()