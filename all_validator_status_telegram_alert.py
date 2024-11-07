import asyncio
import requests
import json
import logging
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
import html
import re

# Load .env file
load_dotenv()

# Set up logging
logging.basicConfig(filename='validator_alert_1.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Directory for mapping validators to tags
VALIDATOR_TAG_MAPPING = {
    # "Testing":["@ygarg25","@munehisa_asxn"],
    # "ASXN LABS": ["@ygarg25","@munehisa_asxn"],
    "Protecc Labs": ["@The0xOmnia","@Oxmagnus"],
    # Add more mappings as needed
}

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

def analyze_validator_data(data):
    if data is None:
        return None
    
    total_validators = len(data)
    active_validators = sum(1 for v in data if not v['isJailed'])
    jailed_validators = sum(1 for v in data if v['isJailed'])
    jailed_names = [v['name'] for v in data if v['isJailed']]
    
    return {
        'total': total_validators,
        'active': active_validators,
        'jailed': jailed_validators,
        'jailed_names': jailed_names
    }

def parse_tags(tags_string):
    return [tag.strip() for tag in re.findall(r'@\w+', tags_string)]

def get_jailed_validators_and_tags(jailed_names):
    jailed_validators = {}
    for validator, tags in VALIDATOR_TAG_MAPPING.items():
        if validator in jailed_names:
            jailed_validators[validator] = tags
    return jailed_validators

def main():
    logging.info("Starting validator check")
    
    # Read configuration from .env file
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = "-1002383379601"

    
    if not BOT_TOKEN or not CHAT_ID:
        logging.error("Telegram bot token or chat ID not found in .env file")
        return

    # Parse tags from .env file
    TAGS_STRING = os.getenv('TELEGRAM_TAGS', '')
    TAGS = parse_tags(TAGS_STRING)
    logging.info(f"Original TAGS_STRING: {TAGS_STRING}")
    logging.info(f"Parsed tags: {TAGS}")

    validator_data = get_validator_data()
    analysis = analyze_validator_data(validator_data)

    if analysis:
        jailed_names_list = "\n".join(f"• {html.escape(name)}" for name in analysis['jailed_names']) if analysis['jailed_names'] else "• None"
        message = (f"<b>Validator Summary:</b>\n"
                   f"Total Validators: <code>{analysis['total']}</code>\n"
                   f"Active Validators: <code>{analysis['active']}</code>\n"
                   f"Jailed Validators: <code>{analysis['jailed']}</code>\n\n"
                   f"<b>Jailed Validator Names:</b>\n{jailed_names_list}")

        # Add personalized messages for jailed validators with tags
        jailed_validators = get_jailed_validators_and_tags(analysis['jailed_names'])
        logging.info(f"Jailed validators and their tags: {jailed_validators}")
        
        if jailed_validators:
            message += "\n\n<b>Tagged Jailed Validators:</b>"
            for validator, tags in jailed_validators.items():
                escaped_validator = html.escape(validator)
                escaped_tags = [html.escape(tag) for tag in tags]
                tags_list = ", ".join(escaped_tags)
                
                message += f"\n{escaped_validator}: {tags_list}"
                message += f"\n\nAttention {tags_list}! Your validator(s) have been jailed. Please check and take necessary actions.\n"
        
        # asyncio.run(send_telegram_alert(BOT_TOKEN, CHAT_ID, message, TAGS))
        asyncio.run(send_telegram_alert(BOT_TOKEN, CHAT_ID, message))


    else:
        logging.warning("Unable to fetch or analyze validator data")

    logging.info("Validator check completed")

if __name__ == "__main__":
    main()