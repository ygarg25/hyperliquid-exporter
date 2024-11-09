#!/usr/bin/python3
"""
Hyperliquid Sentinel (hyperliquid_validator_safeguard.py)
=====================================

A comprehensive validator monitoring system for the Hyperliquid network with multi-channel alerts and non-blocking unjailing.

Features
--------
1. Monitoring:
   - Tracks the status of all network validators and specific validators
   - Detects jailing status and initiates unjailing process after a specified wait time
   - Non-blocking unjail functionality to allow continuous monitoring

2. Alerts:
   - Sends Telegram alerts to separate groups for specific and all validators
   - Initiates phone calls (Twilio) when a specific validator is jailed
   - Configurable alert settings for both combined and individual alerts

3. Testing:
   - Includes tests for Telegram alerts, phone calls, API connectivity, and unjail commands

Installation Guide
----------------
1. System Requirements:
   - Python 3.7+
   - pip (Python package manager)
   - Internet connectivity
   - Linux/Unix environment (for hl-node)

2. Dependencies Installation:
   ```bash
   pip install python-telegram-bot twilio python-dotenv requests asyncio

3. Directory Setup:
   ```bash
   mkdir -p ~/hlq_sentinel
   cd ~/hlq_sentinel
   mkdir logs
   ```

4. Environment Files Setup:
   a) Create .env_alert:
      ```
      TELEGRAM_BOT_TOKEN=your_bot_token
      TELEGRAM_CHAT_ID_SPECIFIC=your_specific_validator_chat_id
      TELEGRAM_CHAT_ID_ALL=your_all_validators_chat_id
      MONITOR_TYPE=both
      VALIDATOR_ADDRESS=your_validator_address
      PRIVATE_KEY=your_private_key
      TELEGRAM_TAGS=@late281,@ygarg25,@munehisa_asxn
      
      # Validator tag mapping (in JSON format)
      # This is used to tag specific people on alerts for each validator
      VALIDATOR_TAG_MAPPING={"ASXN LABS": ["@ygarg25", "@munehisa_asxn"], "Protecc Labs": ["@The0xOmnia", "@Oxmagnus"]}


      ```

   b) Create .env_twillio:
      ```
      TWILIO_ACCOUNT_SID=your_sid
      TWILIO_AUTH_TOKEN=your_token
      TWILIO_FROM_NUMBER=your_twilio_number
      ALERT_PHONE_NUMBERS=number1,number2,number3
      ```

Running the Script
----------------
1. Basic Operation:
   ```bash
   python hyperliquid_validator_safeguard.py
   ```

2. Test Mode:
   ```bash
   # Full system test
   python hyperliquid_validator_safeguard.py --test

   # Individual tests
   python hyperliquid_validator_safeguard.py --test-telegram
   python hyperliquid_validator_safeguard.py --test-calls
   python hyperliquid_validator_safeguard.py --test-api
   python hyperliquid_validator_safeguard.py --test-unjail
   ```

3. Monitoring Options:
   ```bash
   # All validators
   python hyperliquid_validator_safeguard.py --mode all

   # Specific validator
   python hyperliquid_validator_safeguard.py --mode specific

   # Both with custom intervals
   python hyperliquid_validator_safeguard.py --mode both --interval 300 --unjail-wait 1800
   ```

4. Alert Options:
   ```bash
   # Telegram alerts for specific validator
   python hyperliquid_validator_safeguard.py --alerts telegram --mode specific

   # Phone call alerts for specific validator
   python hyperliquid_validator_safeguard.py --alerts calls --mode specific

   # Combined alerts for specific and all validators
   python hyperliquid_validator_safeguard.py --alerts both --mode both
   ```

5. Running as Service:
   a) Create service file:
      ```bash
      sudo nano /etc/systemd/system/hlq-sentinel.service
      ```
      
   b) Add content:
      ```
      [Unit]
      Description=Hyperliquid Sentinel Monitor
      After=network.target

      [Service]
      Type=simple
      User=your_user
      WorkingDirectory=/path/to/hlq_sentinel
      ExecStart=/usr/bin/python3 /path/to/hlq_sentinel/hyperliquid_validator_safeguard.py
      Restart=always
      RestartSec=30

      [Install]
      WantedBy=multi-user.target
      ```

   c) Enable and start:
      ```bash
      sudo systemctl enable hlq-sentinel
      sudo systemctl start hlq-sentinel
      ```

Monitoring & Maintenance
----------------------
1. Check Status:
   ```bash
   sudo systemctl status hlq-sentinel
   ```

2. View Logs:
   ```bash
   # Main log
   tail -f logs/validator_monitor.log

   # Error log
   tail -f logs/validator_error.log

   # Specific logs
   tail -f logs/calls.log
   tail -f logs/telegram_alerts.log
   tail -f logs/unjail_operations.log
   ```

3. Service Management:
   ```bash
   # Stop service
   sudo systemctl stop hlq-sentinel

   # Restart service
   sudo systemctl restart hlq-sentinel

   # Disable service
   sudo systemctl disable hlq-sentinel
   ```

Troubleshooting
-------------
1. Logging Issues:
   - Check directory permissions
   - Verify log rotation
   - Ensure disk space

2. Alert Problems:
   - Validate Telegram token/chat ID
   - Check Twilio credentials
   - Verify internet connectivity

3. Monitoring Issues:
   - Confirm API endpoint
   - Check validator address
   - Verify private key

4. Service Problems:
   - Check service status
   - Verify Python path
   - Check user permissions
"""

def print_usage():
    """Print script usage information"""
    print("""
Hyperliquid Sentinel - Usage Guide
================================


Basic Usage: 
    python hyperliquid_validator_safeguard.py # Run with default settings

Test Mode: 
    python hyperliquid_validator_safeguard.py --test            # Run all tests 
    python hyperliquid_validator_safeguard.py --test-telegram   # Test Telegram 
    python hyperliquid_validator_safeguard.py --test-calls      # Test calls 
    python hyperliquid_validator_safeguard.py --test-api        # Test API 
    python hyperliquid_validator_safeguard.py --test-unjail     # Test unjail

Monitor Options: 
    python hyperliquid_validator_safeguard.py --mode all        # Monitor all validators 
    python hyperliquid_validator_safeguard.py --mode specific   # Monitor specific validator 
    python hyperliquid_validator_safeguard.py --mode both       # Monitor both

Alert Options: 
    python hyperliquid_validator_safeguard.py --alerts telegram # Telegram only 
    python hyperliquid_validator_safeguard.py --alerts calls    # Calls only 
    python hyperliquid_validator_safeguard.py --alerts both     # Both alerts

Custom Settings: 
python hyperliquid_validator_safeguard.py --interval 300        # Set check interval 
python hyperliquid_validator_safeguard.py --unjail-wait 1800    # Set unjail wait time

For more information, please refer to the documentation. """)

#!/usr/bin/python3
"""
[Previous documentation remains the same...]
"""

import asyncio
import requests
import json
import time
import subprocess
import logging
import os
import sys
import signal
import argparse
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from twilio.rest import Client
import html
from logging.handlers import RotatingFileHandler, SysLogHandler
from typing import Optional, Dict, List, Union
from pathlib import Path

# Constants
CHECK_INTERVAL = 300  # 5 minutes
UNJAIL_WAIT_TIME = 1800  # 30 minutes

# Global cache for API data
_last_fetched_data = None
_last_fetch_time = 0
CACHE_EXPIRY = 60  # Cache data for 60 seconds

API_ENDPOINT = 'https://api.hyperliquid-testnet.xyz/info'

# # Validator mappings for notifications
# VALIDATOR_TAG_MAPPING = {
#     "ASXN LABS": ["@ygarg25", "@munehisa_asxn"],
#     "Protecc Labs": ["@The0xOmnia", "@Oxmagnus"],
# }

class LoggerSetup:
    @staticmethod
    def setup_logger():
        """Set up comprehensive logging system"""
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        logger.handlers = []  # Clear existing handlers
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Define all log files
        log_files = {
            'main': 'validator_monitor.log',
            'error': 'validator_error.log',
            'calls': 'calls.log',
            'telegram': 'telegram_alerts.log',
            'unjail': 'unjail_operations.log',
            'test': 'test_operations.log'
        }
        
        # Create handlers for each log file
        for log_type, filename in log_files.items():
            handler = RotatingFileHandler(
                os.path.join(logs_dir, filename),
                maxBytes=50*1024*1024,  # 50MB
                backupCount=7
            )
            handler.setFormatter(formatter)
            if log_type == 'error':
                handler.setLevel(logging.ERROR)
            logger.addHandler(handler)
        
        return logger

class ConfigLoader:
    @staticmethod
    def load_config() -> Dict:
        """Load configuration from both .env_alert and .env_twillio"""
        # Load both env files
        load_dotenv('.env_alert')
        load_dotenv('.env_twillio')
        
        config = {
            # Telegram config
            'telegram_token': os.getenv('TELEGRAM_BOT_TOKEN'),
            'telegram_chat_id_specific': os.getenv('TELEGRAM_CHAT_ID_SPECIFIC'),
            'telegram_chat_id_all': os.getenv('TELEGRAM_CHAT_ID_ALL'),
            'monitor_type': os.getenv('MONITOR_TYPE', 'all').lower(),

            'telegram_tags': os.getenv('TELEGRAM_TAGS', '').split(','),
            
            # Validator config
            'validator_address': os.getenv('VALIDATOR_ADDRESS'),
            'private_key': os.getenv('PRIVATE_KEY'),
            
            # Twilio config
            'twilio_sid': os.getenv('TWILIO_ACCOUNT_SID'),
            'twilio_token': os.getenv('TWILIO_AUTH_TOKEN'),
            'twilio_from': os.getenv('TWILIO_FROM_NUMBER'),
            'phone_numbers': os.getenv('ALERT_PHONE_NUMBERS', '').split(',')
        }

        # Load and parse validator tag mapping
        validator_tag_mapping = os.getenv('VALIDATOR_TAG_MAPPING')
        if validator_tag_mapping:
            try:
                config['validator_tag_mapping'] = json.loads(validator_tag_mapping)
            except json.JSONDecodeError:
                logging.error("Failed to parse VALIDATOR_TAG_MAPPING from .env file")
                config['validator_tag_mapping'] = {}  # Fallback to empty mapping if parsing fails

        return config

    @staticmethod
    def validate_config(config: Dict) -> bool:
        """Validate required configuration for both specific and general Telegram chat IDs"""
        required = {
            'telegram': ['telegram_token', 'telegram_chat_id_specific', 'telegram_chat_id_all'],
            'validator': ['validator_address', 'private_key'],
            'twilio': ['twilio_sid', 'twilio_token', 'twilio_from']
        }
        
        missing = []
        for category, fields in required.items():
            for field in fields:
                if not config.get(field):
                    missing.append(f"{category}:{field}")
        
        if missing:
            logging.error(f"Missing required configuration: {', '.join(missing)}")
            return False
        return True


class AlertManager:
    def __init__(self, config: Dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.telegram_bot = None
        self.twilio_client = None
        
        # Initialize Telegram and Twilio clients
        if config['telegram_token']:
            self.telegram_bot = Bot(token=config['telegram_token'])
        
        if all([config['twilio_sid'], config['twilio_token'], config['twilio_from']]):
            self.twilio_client = Client(config['twilio_sid'], config['twilio_token'])
    
    async def send_alert(self, message: str, alert_type: str = 'both', specific: bool = False, remaining_unjail_time: Optional[int] = None):
        """Send alert through configured channels, with specific=True for specific validator alerts"""
        if alert_type in ['telegram', 'both'] and self.telegram_bot:
            await self.send_telegram_alert(message, specific=specific, remaining_unjail_time=remaining_unjail_time)
        
        if alert_type in ['call', 'both'] and specific and self.twilio_client:
            await self.make_calls(message)

    async def send_telegram_alert(self, message: str, specific: bool = False, remaining_unjail_time: Optional[int] = None):
        """Send Telegram alert to specific or general chat, with optional tags"""
        try:
            chat_id = self.config['telegram_chat_id_specific'] if specific else self.config['telegram_chat_id_all']
            global_tags = ' '.join(html.escape(tag) for tag in self.config.get('telegram_tags', []))
            
            if specific and remaining_unjail_time is not None:
                # Add remaining unjail time to specific validator message
                validator_name = "ASXN LABS"  # Example placeholder
                stake = "1001551886053"  # Example placeholder
                recent_blocks = 0  # Example placeholder
                message = (
                    f"{global_tags}\n\n"
                    f"<b>{validator_name} Validator Alert:</b>\n"
                    f"Is Jailed: <code>True</code>\n"
                    f"Stake: <code>{stake}</code>\n"
                    f"Recent Blocks: <code>{recent_blocks}</code>\n"
                    f"Time left until unjail attempt: <code>{remaining_unjail_time} minutes</code>\n"
                )
            else:
                message = f"{global_tags}\n\n{message}"
            
            await self.telegram_bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.HTML
            )
            self.logger.info("Telegram alert sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to send Telegram alert: {e}")

    async def make_calls(self, alert_message: str):
        """Make phone calls to all configured numbers"""
        if not self.config['phone_numbers']:
            return
        
        for phone in self.config['phone_numbers']:
            try:
                phone = self.format_phone_number(phone)
                twiml = f"""
                    <?xml version="1.0" encoding="UTF-8"?>
                    <Response>
                        <Say voice="alice" language="en-IN">
                            {alert_message}
                        </Say>
                        <Pause length="2"/>
                        <Say voice="alice" language="en-IN">
                            Please check your validator immediately.
                        </Say>
                    </Response>
                """
                
                call = self.twilio_client.calls.create(
                    twiml=twiml,
                    to=phone,
                    from_=self.config['twilio_from']
                )
                
                self.logger.info(f"Call initiated to {phone}, SID: {call.sid}")
                await asyncio.sleep(2)  # Wait between calls
                
            except Exception as e:
                self.logger.error(f"Failed to call {phone}: {e}")
    
    @staticmethod
    def format_phone_number(number: str) -> str:
        """Format phone number to E.164 format"""
        cleaned = ''.join(filter(str.isdigit, number))
        if cleaned.startswith('91'):
            cleaned = cleaned[2:]
        elif cleaned.startswith('0'):
            cleaned = cleaned[1:]
        
        return f"+91{cleaned}" if len(cleaned) == 10 else number


class ValidatorMonitor:
    def __init__(self, config: Dict, alert_manager: AlertManager, logger: logging.Logger):
        self.config = config
        self.alert_manager = alert_manager
        self.logger = logger
        self.in_unjail_wait = False
        self.unjail_start_time = None  # Track when the unjail wait started

    async def schedule_unjail(self, validator_name: str, validator_info: Dict):
        """Wait for UNJAIL_WAIT_TIME before attempting to unjail, avoiding duplicate unjail attempts."""
        self.in_unjail_wait = True  # Prevent duplicate unjail tasks
        self.unjail_start_time = time.time()  # Record the start time for calculating remaining time
        
        try:
            jail_message = f"🚨 Alert: Hyperliquid Node <b>{validator_info['name']}</b> has been jailed! Unjailing attempt will be made after {UNJAIL_WAIT_TIME // 60} minutes."
            await self.alert_manager.send_alert(jail_message, alert_type='both', specific=True, remaining_unjail_time=UNJAIL_WAIT_TIME // 60)
            await asyncio.sleep(UNJAIL_WAIT_TIME)
            
            # Attempt to unjail the validator
            if await self.unjail_validator(validator_name, validator_info):
                # Successful unjail, reset the flag
                self.in_unjail_wait = False
                success_message = f"✅ Successfully unjailed {validator_name}."
                await self.alert_manager.send_alert(success_message, alert_type='both', specific=True)
            else:
                failure_message = f"❌ Failed to unjail {validator_name}. Manual intervention required."
                await self.alert_manager.send_alert(failure_message, alert_type='both', specific=True)

        except Exception as e:
            self.logger.error(f"Error during unjail process: {e}")
        finally:
            # Ensure the flag is reset if unjail failed
            if not self.in_unjail_wait:
                self.in_unjail_wait = False
                self.unjail_start_time = None

    async def get_remaining_unjail_time(self) -> int:
        """Calculate the remaining time in minutes until unjail attempt."""
        if self.unjail_start_time:
            elapsed_time = time.time() - self.unjail_start_time
            remaining_time = max(UNJAIL_WAIT_TIME - elapsed_time, 0)  # Ensure non-negative time
            return int(remaining_time // 60)  # Return remaining time in minutes
        return 0

    async def unjail_validator(self, validator_name: str, validator_info: Dict) -> bool:
        """Unjails the validator based on cached validator information."""
        if validator_info['isJailed']:
            try:
                cmd = f'~/hl-node --chain Testnet --key {self.config["private_key"]} send-signed-action \'{{"type": "CSignerAction", "unjailSelf": null}}\''
                self.logger.info(f"Executing unjail for {validator_name}")
                
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.stdout:
                    self.logger.info(f"Unjail output: {result.stdout}")
                if result.stderr:
                    self.logger.error(f"Unjail error: {result.stderr}")
                    
                return result.returncode == 0
            except Exception as e:
                self.logger.error(f"Unjail error: {e}")
                return False
        else:
            self.logger.info(f"Validator {validator_name} is not jailed.")
            return False
        

    async def check_validator_status(self):
        """Check specific validator status and handle jailing"""
        try:
            response = requests.post(
                API_ENDPOINT,
                headers={'Content-Type': 'application/json'},
                json={"type": "validatorSummaries"}
            )
            validators = response.json()

            validator = next(
                (v for v in validators if v['validator'].lower() == self.config['validator_address'].lower()),
                None
            )

            if not validator:
                self.logger.warning(f"Validator {self.config['validator_address']} not found")
                return

            return validator
        except Exception as e:
            self.logger.error(f"Error checking validator status: {e}")
            return None

class TestManager:
    def __init__(self, config: Dict, alert_manager: AlertManager, logger: logging.Logger):
        self.config = config
        self.alert_manager = alert_manager
        self.logger = logger
    
    async def test_telegram(self) -> bool:
        """Test Telegram alerts"""
        try:
            test_message = (
                "<b>🧪 Validator Monitor Test</b>\n"
                "Testing Telegram alerts functionality.\n"
                "If you see this message, Telegram alerts are working!"
            )
            await self.alert_manager.send_alert(test_message, 'telegram')
            return True
        except Exception as e:
            self.logger.error(f"Telegram test failed: {e}")
            return False
    
    async def test_twilio(self) -> bool:
        """Test Twilio calls"""
        try:
            test_message = "This is a test call from your Hyperliquid validator monitor. If you hear this message, phone alerts are working!"
            await self.alert_manager.make_calls(test_message)
            return True
        except Exception as e:
            self.logger.error(f"Twilio test failed: {e}")
            return False
    
    async def test_api(self) -> bool:
        """Test API connectivity"""
        try:
            response = requests.post(
                API_ENDPOINT,
                headers={'Content-Type': 'application/json'},
                json={"type": "validatorSummaries"}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            self.logger.error(f"API test failed: {e}")
            return False
    
    async def test_unjail(self) -> bool:
        """Test unjail command"""
        try:
            cmd = f'~/hl-node --version'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Unjail test failed: {e}")
            return False
    
    async def run_all_tests(self):
        """Run all tests"""
        print("\n=== Running Validator Monitor Tests ===\n")
        
        tests = [
            ("API Connection", self.test_api()),
            ("Telegram Alerts", self.test_telegram()),
            ("Phone Calls", self.test_twilio()),
            ("Unjail Command", self.test_unjail())
        ]
        
        results = []
        for test_name, test_coro in tests:
            print(f"Testing {test_name}...")
            try:
                result = await test_coro
                status = "✅ PASSED" if result else "❌ FAILED"
                results.append((test_name, status))
            except Exception as e:
                results.append((test_name, f"❌ ERROR: {str(e)}"))
        
        print("\n=== Test Results ===")
        for test_name, status in results:
            print(f"{test_name}: {status}")

async def fetch_validator_data():
    """Fetch validator data from the API, with caching to reduce calls."""
    global _last_fetched_data, _last_fetch_time

    # Check if we have recent data and use it if still valid
    current_time = time.time()
    if _last_fetched_data and (current_time - _last_fetch_time < CACHE_EXPIRY):
        return _last_fetched_data

    try:
        response = requests.post(
            API_ENDPOINT,
            headers={'Content-Type': 'application/json'},
            json={"type": "validatorSummaries"}
        )
        response.raise_for_status()
        _last_fetched_data = response.json()
        _last_fetch_time = current_time
        return _last_fetched_data
    except Exception as e:
        logging.error(f"Error fetching validator data: {e}")
        return None

# Use cached data in check_all_validators and monitor_loop

async def check_all_validators(alert_manager: AlertManager):
    """Monitor all validators using cached data if available."""
    logger = logging.getLogger('all_validators')
    validators = await fetch_validator_data()
    if validators is None:
        logger.error("Failed to retrieve validator data.")
        return

    total = len(validators)
    active = sum(1 for v in validators if not v['isJailed'])
    jailed = total - active

    # Collect jailed validator names and tags
    jailed_validators = [v['name'] for v in validators if v['isJailed']]
    tagged_jailed = {name: alert_manager.config['validator_tag_mapping'].get(name, []) for name in jailed_validators if name in alert_manager.config['validator_tag_mapping']}
    
    # Create the summary message for "all validators"
    message = (
        f"<b>Validator Summary:</b>\n"
        f"Total Validators: <code>{total}</code>\n"
        f"Active Validators: <code>{active}</code>\n"
        f"Jailed Validators: <code>{jailed}</code>\n\n"
        f"<b>Jailed Validator Names:</b>\n"
    )

    # List jailed validators
    message += "\n".join(f"• {name}" for name in jailed_validators)

    # List tagged validators
    if tagged_jailed:
        message += "\n\n<b>Tagged Jailed Validators:</b>\n"
        for name, tags in tagged_jailed.items():
            tags_str = ', '.join(tags)
            message += f"{name}: {tags_str}\n"
        
        # Add a final attention line
        attention_tags = ', '.join({tag for tags in tagged_jailed.values() for tag in tags})
        message += f"\nAttention {attention_tags}! Your validator(s) have been jailed. Please check and take necessary actions."

    await alert_manager.send_alert(message, alert_type='telegram', specific=False)
    
async def monitor_loop(args, config, monitor, alert_manager):
    """Main monitoring loop, allowing for combined alerts and non-blocking unjail handling."""
    logger = logging.getLogger()
    interval = args.interval or CHECK_INTERVAL
    mode = args.mode or config['monitor_type']

    while True:
        try:
            # Fetch latest validator data once per loop
            validators = await fetch_validator_data()
            if validators is None:
                logger.error("Failed to retrieve validator data.")
                await asyncio.sleep(interval)
                continue

            if mode in ['specific', 'both'] and config['validator_address']:
                validator_info = next(
                    (v for v in validators if v['validator'].lower() == config['validator_address'].lower()),
                    None
                )
                if validator_info and validator_info['isJailed'] and not monitor.in_unjail_wait:
                    # Start a separate task for the unjail process to avoid blocking the loop
                    asyncio.create_task(monitor.schedule_unjail(config['validator_address'], validator_info))
                else:
                    # Send alerts for both specific and all validators if needed
                    await alert_manager.send_alert("Specific validator status update", alert_type='telegram', specific=True)
                    await alert_manager.send_alert("All validators status update", alert_type='telegram', specific=False)

            if mode in ['all', 'both']:
                await check_all_validators(alert_manager)

            await asyncio.sleep(interval)

        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(interval)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger = logging.getLogger()
    logger.info("Received shutdown signal. Cleaning up...")
    sys.exit(0)

async def main(args):
    """Main function"""
    # Setup logger first
    logger = LoggerSetup.setup_logger()
    logger.info("Starting Hyperliquid Sentinel...")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Load and validate configuration
        config = ConfigLoader.load_config()
        if not ConfigLoader.validate_config(config):
            logger.error("Invalid configuration. Exiting...")
            return
        
        # Initialize components
        alert_manager = AlertManager(config, logger)
        monitor = ValidatorMonitor(config, alert_manager, logger)
        test_manager = TestManager(config, alert_manager, logger)
        
        # Handle test commands
        if args.test or args.test_telegram or args.test_calls or args.test_api or args.test_unjail:
            if args.test:
                await test_manager.run_all_tests()
            else:
                if args.test_telegram:
                    await test_manager.test_telegram()
                if args.test_calls:
                    await test_manager.test_twilio()
                if args.test_api:
                    await test_manager.test_api()
                if args.test_unjail:
                    await test_manager.test_unjail()
            return
        
        # Start monitoring loop
        await monitor_loop(args, config, monitor, alert_manager)
        
    except Exception as e:
        logger.error(f"Critical error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Hyperliquid Sentinel - Validator Monitoring System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add command line arguments
    parser.add_argument('--help-usage', action='store_true', help='Show detailed usage guide')
    parser.add_argument('--mode', choices=['all', 'specific', 'both'], help='Monitor mode')
    parser.add_argument('--alerts', choices=['telegram', 'calls', 'both'], help='Alert methods')
    parser.add_argument('--interval', type=int, help='Check interval in seconds')
    parser.add_argument('--unjail-wait', type=int, help='Unjail wait time in seconds')
    parser.add_argument('--test', action='store_true', help='Run all tests')
    parser.add_argument('--test-telegram', action='store_true', help='Test Telegram')
    parser.add_argument('--test-calls', action='store_true', help='Test calls')
    parser.add_argument('--test-api', action='store_true', help='Test API')
    parser.add_argument('--test-unjail', action='store_true', help='Test unjail')
    
    args = parser.parse_args()
    
    if args.help_usage:
        print_usage()
        sys.exit(0)
    
    # Start the monitor
    asyncio.run(main(args))      
