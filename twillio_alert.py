"""
Hyperliquid Validator Jail Monitor

This script monitors a Hyperliquid validator node and makes phone calls when the validator gets jailed.
All configuration is read from .env_twillio file.

Required .env_twillio format:
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=your_twilio_number
VALIDATOR_ADDRESS=0xd41281ea0aab1671248ef864bc6df38a5d15b3f0
ALERT_PHONE_NUMBERS=9996610098,919876543210,+919876543211
"""

import requests
import json
import time
from twilio.rest import Client
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ConfigLoader:
    @staticmethod
    def load_config():
        """
        Load configuration from .env_twillio file
        
        Returns:
            dict: Configuration parameters
        """
        if not load_dotenv('.env_twillio'):
            raise Exception("Could not load .env_twillio file")
            
        # Required environment variables
        required_vars = [
            'TWILIO_ACCOUNT_SID',
            'TWILIO_AUTH_TOKEN',
            'TWILIO_FROM_NUMBER',
            'VALIDATOR_ADDRESS',
            'ALERT_PHONE_NUMBERS'
        ]
        
        # Check all required variables exist
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required variables in .env_twillio: {', '.join(missing_vars)}")
            
        # Get phone numbers list
        phone_numbers = os.getenv('ALERT_PHONE_NUMBERS').split(',')
        phone_numbers = [num.strip() for num in phone_numbers]
        
        return {
            'twilio_sid': os.getenv('TWILIO_ACCOUNT_SID'),
            'twilio_token': os.getenv('TWILIO_AUTH_TOKEN'),
            'twilio_from': os.getenv('TWILIO_FROM_NUMBER'),
            'validator_address': os.getenv('VALIDATOR_ADDRESS'),
            'phone_numbers': phone_numbers
        }

class HyperliquidMonitor:
    def __init__(self):
        """Initialize monitor with configuration from .env_twillio"""
        # Load config
        config = ConfigLoader.load_config()
        
        self.validator_address = config['validator_address'].lower()
        self.api_url = "https://api.hyperliquid-testnet.xyz/info"
        self.twilio_client = Client(config['twilio_sid'], config['twilio_token'])
        self.twilio_from = config['twilio_from']
        self.phone_numbers = [self.format_indian_number(num) for num in config['phone_numbers']]
        self.last_jailed_status = False
        
        logger.info(f"Monitoring validator: {self.validator_address}")
        logger.info(f"Alert numbers configured: {', '.join(self.phone_numbers)}")

    def format_indian_number(self, number):
        """Format phone number to Indian format (+91XXXXXXXXXX)"""
        cleaned = ''.join(filter(str.isdigit, number))
        
        if cleaned.startswith('91'):
            cleaned = cleaned[2:]
        elif cleaned.startswith('0'):
            cleaned = cleaned[1:]
            
        if len(cleaned) != 10:
            raise ValueError(f"Invalid phone number: {number}. Must be 10 digits.")
            
        return f"+91{cleaned}"

    def get_validator_status(self):
        """Fetch validator status from Hyperliquid API"""
        try:
            payload = {"type": "validatorSummaries"}
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            for validator in response.json():
                if validator['validator'].lower() == self.validator_address:
                    return {
                        'name': validator['name'],
                        'isJailed': validator['isJailed'],
                        'stake': validator['stake'],
                        'nRecentBlocks': validator['nRecentBlocks']
                    }
                    
            logger.warning(f"Validator {self.validator_address} not found in API response")
            return None
            
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None

    def make_alert_call(self, phone_number, validator_info):
        """Make a phone call to alert about validator jailing"""
        try:
            logger.info(f"Initiating call to {phone_number}")
            
            twiml = f"""
                <?xml version="1.0" encoding="UTF-8"?>
                <Response>
                    <Say voice="alice" language="en-IN">
                        Urgent Alert! Your Hyperliquid validator {validator_info['name']} has been jailed!
                    </Say>
                    <Pause length="1"/>
                    <Say voice="alice" language="en-IN">
                        Current statistics: Recent blocks: {validator_info['nRecentBlocks']}, 
                        Stake amount: {validator_info['stake']}
                    </Say>
                    <Pause length="2"/>
                    <Say voice="alice" language="en-IN">
                        Please check your validator immediately. This requires urgent attention.
                    </Say>
                </Response>
            """
            
            call = self.twilio_client.calls.create(
                twiml=twiml,
                to=phone_number,
                from_=self.twilio_from
            )
            
            logger.info(f"Call initiated successfully to {phone_number}, SID: {call.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to call {phone_number}: {str(e)}")
            return False

    def alert_all_numbers(self, validator_info):
        """Call all configured phone numbers"""
        logger.info("Starting alert calls to all numbers...")
        for phone in self.phone_numbers:
            success = self.make_alert_call(phone, validator_info)
            status = "succeeded" if success else "failed"
            logger.info(f"Alert to {phone} {status}")
            time.sleep(2)  # Delay between calls

    def monitor_loop(self, check_interval=60):
        """Main monitoring loop"""
        logger.info("Starting monitoring loop...")
        
        while True:
            try:
                validator_info = self.get_validator_status()
                
                if validator_info is None:
                    logger.warning("Failed to get validator status. Will retry...")
                    time.sleep(check_interval)
                    continue
                
                logger.info(f"Current status - Name: {validator_info['name']}, Jailed: {validator_info['isJailed']}")
                
                if validator_info['isJailed'] and not self.last_jailed_status:
                    logger.warning("⚠️ Validator has been jailed! Starting alerts...")
                    self.alert_all_numbers(validator_info)
                    self.last_jailed_status = True
                elif not validator_info['isJailed']:
                    self.last_jailed_status = False
                
                time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(check_interval)

if __name__ == "__main__":
    try:
        # Create and start monitor
        monitor = HyperliquidMonitor()
        monitor.monitor_loop()
    except Exception as e:
        logger.error(f"Failed to start monitor: {e}")