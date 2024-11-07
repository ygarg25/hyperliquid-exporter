#!/usr/bin/python3
"""
Hyperliquid Validator Monitor
============================

This script monitors a Hyperliquid validator's status and automatically handles unjailing.

Features:
---------
1. Status Monitoring:
   - Checks validator status every minute
   - Monitors for jailing status, block count, and activity
   - Logs full validator details

2. Auto-Unjailing:
   - Detects when validator is jailed
   - Waits exactly 30 minutes from jail time
   - Executes unjail command automatically

3. Logging System:
   - Maintains logs in same directory as script
   - Two log files:
     * validator_monitor.log: Main activity log
     * validator_detailed.log: Detailed debug information
   - Log rotation to manage disk space
   - Integration with systemd journal

4. Testing Capabilities:
   - Test function to verify configuration
   - Validates environment setup
   - Checks API connectivity
   - Verifies hl-node command functionality

Setup Instructions:
------------------
1. Environment File (.env_hyper in script directory):
   VALIDATOR_ADDRESS=your_validator_address
   PRIVATE_KEY=your_private_key

2. Directory Structure:
   /your/script/directory/
   ├── validator_monitor.py      - This script
   ├── .env_hyper               - Environment file
   └── logs/                    - Log directory
       ├── validator_monitor.log
       └── validator_detailed.log

3. Running:
   - As script: python3 validator_monitor.py
   - Test mode: python3 validator_monitor.py --test
   - Service: sudo systemctl start validator-monitor
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
CHECK_INTERVAL = 300  # 5 minute
UNJAIL_WAIT_TIME = 1800  # 30 minutes
API_ENDPOINT = 'https://api.hyperliquid-testnet.xyz/info'

class ValidatorMonitor:
    def __init__(self, logger, validator_address: str, private_key: str):
        self.logger = logger
        self.validator_address = validator_address
        self.private_key = private_key
        self.last_jailed_time = None

    def check_validator_status(self) -> Optional[Dict]:
        """Check validator status from API"""
        headers = {'Content-Type': 'application/json'}
        data = {'type': 'validatorSummaries'}
        
        try:
            response = requests.post(API_ENDPOINT, headers=headers, json=data)
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
        """Execute unjail command"""
        try:
            cmd = f'~/hl-node --chain Testnet --key {self.private_key} send-signed-action \'{{"type": "CSignerAction", "unjailSelf": null}}\''
            
            self.logger.info(f"Executing unjail command...")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.stdout:
                self.logger.info(f"Unjail command output: {result.stdout}")
            if result.stderr:
                self.logger.error(f"Unjail command error: {result.stderr}")
            
            success = result.returncode == 0
            if success:
                self.last_jailed_time = None  # Reset jail time after successful unjail
            return success
        except Exception as e:
            self.logger.error(f"Error executing unjail command: {str(e)}")
            return False

    def monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Starting monitoring loop...")
        
        while True:
            try:
                self.logger.debug(f"Checking validator status for {self.validator_address}")
                validator = self.check_validator_status()
                
                if validator:
                    status_msg = (
                        f"Validator status: "
                        f"Name={validator['name']}, "
                        f"isJailed={validator['isJailed']}, "
                        f"nRecentBlocks={validator['nRecentBlocks']}, "
                        f"isActive={validator['isActive']}, "
                        f"stake={validator['stake']}"
                    )
                    self.logger.info(status_msg)
                    self.logger.debug(f"Full validator info: {json.dumps(validator, indent=2)}")
                    
                    if validator['isJailed']:
                        current_time = datetime.now()
                        
                        # Record jail time if first detection
                        if not self.last_jailed_time:
                            self.last_jailed_time = current_time
                            self.logger.warning(f"⚠️ Validator jailed at {current_time}")
                        
                        # Check if 30 minutes have passed since jailing
                        time_since_jail = (current_time - self.last_jailed_time).total_seconds()
                        if time_since_jail >= UNJAIL_WAIT_TIME:
                            self.logger.info("🔄 30 minutes passed, attempting to unjail...")
                            if self.unjail_validator():
                                self.logger.info("✅ Unjail command executed successfully")
                            else:
                                self.logger.error("❌ Failed to execute unjail command")
                        else:
                            wait_remaining = UNJAIL_WAIT_TIME - time_since_jail
                            self.logger.info(f"⏳ Waiting {wait_remaining:.0f} seconds before unjailing...")
                    else:
                        self.last_jailed_time = None
                else:
                    self.logger.error(f"❌ Validator {self.validator_address} not found in response")
                    
            except Exception as e:
                self.logger.error(f"❌ Error in monitoring loop: {str(e)}")
            
            time.sleep(CHECK_INTERVAL)

    def test_configuration(self) -> bool:
        """Test configuration and connectivity"""
        try:
            print("\n=== Testing Validator Monitor Configuration ===\n")
            
            # 1. Test Environment
            print("1. Testing Environment Setup...")
            print(f"   Script Directory: {os.path.dirname(os.path.abspath(__file__))}")
            print(f"   Validator Address: {self.validator_address}")
            if self.private_key:
                print("   Private Key: Found ✅")
            else:
                print("   Private Key: Missing ❌")
            
            # 2. Test API Connection
            print("\n2. Testing API Connection...")
            validator = self.check_validator_status()
            if validator:
                print("✅ API Connection Successful")
                print(f"   Validator Name: {validator['name']}")
                print(f"   Current Status: {'🔒 Jailed' if validator['isJailed'] else '✅ Active'}")
            else:
                print("❌ Failed to get validator status")
                return False
            
            # 3. Test hl-node command
            print("\n3. Testing hl-node command...")
            try:
                result = subprocess.run('~/hl-node --version', shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    print("✅ hl-node command accessible")
                else:
                    print("❌ hl-node command failed")
                    return False
            except:
                print("❌ hl-node command not found")
                return False
            
            # 4. Test Log Directory
            print("\n4. Testing Log Directory...")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(script_dir, 'logs')
            if os.path.exists(log_dir):
                print(f"✅ Log directory exists: {log_dir}")
            else:
                os.makedirs(log_dir)
                print(f"✅ Created log directory: {log_dir}")
            
            print("\n=== Configuration Test Complete ===")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {str(e)}")
            return False

def setup_logging() -> Tuple[logging.Logger, str]:
    """Setup logging configuration"""
    logger = logging.getLogger('ValidatorMonitor')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - ValidatorMonitor - %(levelname)s - %(message)s')
    
    # Setup log directory in script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(script_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Main log file
    log_file = os.path.join(log_dir, 'validator_monitor.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Detailed log file
    detailed_log = os.path.join(log_dir, 'validator_detailed.log')
    detailed_handler = RotatingFileHandler(
        detailed_log,
        maxBytes=50*1024*1024,  # 50MB
        backupCount=10
    )
    detailed_handler.setFormatter(formatter)
    detailed_handler.setLevel(logging.DEBUG)
    logger.addHandler(detailed_handler)
    
    # Stdout handler
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)
    
    # Syslog handler
    try:
        syslog_handler = SysLogHandler(address='/dev/log')
        syslog_handler.setFormatter(formatter)
        logger.addHandler(syslog_handler)
    except:
        logger.warning("Could not connect to syslog")
    
    return logger, log_dir

def load_env_file(logger) -> Optional[Dict]:
    """Load environment variables from script directory"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, '.env_hyper')
    
    try:
        logger.info(f"Looking for environment file at: {file_path}")
        with open(file_path, 'r') as file:
            env_vars = {}
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"\'')
            logger.info("Successfully loaded environment file")
            return env_vars
    except FileNotFoundError:
        logger.error(f"Environment file {file_path} not found")
        # Try to create a template .env_hyper file
        try:
            with open(file_path, 'w') as f:
                f.write("VALIDATOR_ADDRESS=your_validator_address_here\n")
                f.write("PRIVATE_KEY=your_private_key_here\n")
            logger.info(f"Created template environment file at {file_path}")
            logger.info("Please edit the file and add your validator address and private key")
        except Exception as e:
            logger.error(f"Failed to create template environment file: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error reading environment file: {str(e)}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Hyperliquid Validator Monitor')
    parser.add_argument('--test', action='store_true', help='Run configuration test')
    args = parser.parse_args()
    
    # Setup logging
    logger, log_dir = setup_logging()
    
    # Load environment variables
    env_vars = load_env_file(logger)
    if not env_vars:
        logger.error("Failed to load environment variables. Exiting...")
        sys.exit(1)
    
    # Get required variables
    PRIVATE_KEY = env_vars.get('PRIVATE_KEY')
    VALIDATOR_ADDRESS = env_vars.get('VALIDATOR_ADDRESS')
    
    # Validate required variables
    if not PRIVATE_KEY or not VALIDATOR_ADDRESS:
        logger.error("Missing required environment variables. Exiting...")
        sys.exit(1)
    
    # Create monitor instance
    monitor = ValidatorMonitor(logger, VALIDATOR_ADDRESS, PRIVATE_KEY)
    
    # Run test if requested
    if args.test:
        success = monitor.test_configuration()
        sys.exit(0 if success else 1)
    
    # Start monitoring
    logger.info("🚀 Starting validator monitoring service")
    logger.info(f"Monitoring validator: {VALIDATOR_ADDRESS}")
    monitor.monitor_loop()

if __name__ == "__main__":
    main()