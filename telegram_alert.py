import asyncio
import requests
import json
import logging
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Load .env file
load_dotenv()

# Set up logging
logging.basicConfig(filename='validator_alert.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

async def send_telegram_alert(bot_token, chat_id, message, tags=None):
    bot = Bot(token=bot_token)
    if tags:
        tag_string = ' '.join(tags)
        message = f"{tag_string}\n\n{message}"
    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN)
        logging.info("Alert sent successfully")
    except TelegramError as e:
        logging.error(f"Failed to send Telegram message: {e}")

def get_validator_data():
    url = "https://api.hyperliquid-testnet.xyz/info"
    payload = json.dumps({
        "type": "validatorSummaries"
    })
    headers = {
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return json.loads(response.text)
    except requests.RequestException as e:
        logging.error(f"Failed to fetch validator data: {e}")
        return None

def find_asxn_labs_data(data):
    if data is None:
        return None
    for validator in data:
        if validator['name'] == "ASXN LABS":
            return validator
    logging.warning("ASXN LABS validator not found in the data")
    return None

def main():
    logging.info("Starting validator check")
    
    # Read configuration from .env file
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("Telegram bot token or chat ID not found in .env file")
        return

    # Add usernames or group tags here
    TAGS = os.getenv('TELEGRAM_TAGS', '').split(',')

    validator_data = get_validator_data()
    asxn_labs = find_asxn_labs_data(validator_data)

    if asxn_labs:
        message = (f"*ASXN LABS Validator Alert:*\n"
                   f"Is Jailed: `{asxn_labs['isJailed']}`\n"
                   f"Stake: `{asxn_labs['stake']}`\n"
                   f"Recent Blocks: `{asxn_labs['nRecentBlocks']}`")
        
        asyncio.run(send_telegram_alert(BOT_TOKEN, CHAT_ID, message, TAGS))
    else:
        logging.warning("Unable to fetch ASXN LABS validator data")

    logging.info("Validator check completed")

if __name__ == "__main__":
    main()