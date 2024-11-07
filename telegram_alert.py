import asyncio
import requests
import json
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
import html

# Load .env file
load_dotenv()

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Generate log filename with timestamp
current_date = datetime.now().strftime('%Y-%m-%d')
# log_filename = f'logs/validator_alert_{current_date}.log'
log_filename = f'logs/telegram_alert.log'


# Set up logging with both file and console output
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create file handler
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

async def send_telegram_alert(bot_token, chat_id, message, tags=None):
    bot = Bot(token=bot_token)
    if tags:
        escaped_tags = [html.escape(tag) for tag in tags]
        tag_string = ' '.join(escaped_tags)
        message = f"{tag_string}\n\n{message}"
    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)
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

def parse_tags(tags_string):
    return [tag.strip() for tag in tags_string.split(',') if tag.strip()]

def main():
    logging.info("Starting validator check")
    
    # Read configuration from .env file
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("Telegram bot token or chat ID not found in .env file")
        return

    # Parse tags from .env file
    TAGS = parse_tags(os.getenv('TELEGRAM_TAGS', ''))
    logging.info(f"Parsed tags: {TAGS}")

    validator_data = get_validator_data()
    asxn_labs = find_asxn_labs_data(validator_data)

    if asxn_labs:
        message = (f"<b>ASXN LABS Validator Alert:</b>\n"
                   f"Is Jailed: <code>{asxn_labs['isJailed']}</code>\n"
                   f"Stake: <code>{asxn_labs['stake']}</code>\n"
                   f"Recent Blocks: <code>{asxn_labs['nRecentBlocks']}</code>")
        
        if asxn_labs['isJailed']:
            asyncio.run(send_telegram_alert(BOT_TOKEN, CHAT_ID, message, TAGS))
        else:
            logging.warning("ASXN LABS validator is not Jailed")
    else:
        logging.warning("Unable to fetch ASXN LABS validator data")

    logging.info("Validator check completed")

if __name__ == "__main__":
    main()