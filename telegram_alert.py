import asyncio
import requests
import json
from telegram import Bot
from telegram.constants import ParseMode

async def send_telegram_alert(bot_token, chat_id, message, tags=None):
    bot = Bot(token=bot_token)
    if tags:
        tag_string = ' '.join(tags)
        message = f"{tag_string}\n\n{message}"
    await bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN)

def get_validator_data():
    url = "https://api.hyperliquid-testnet.xyz/info"
    payload = json.dumps({
        "type": "validatorSummaries"
    })
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers, data=payload)
    return json.loads(response.text)

def find_asxn_labs_data(data):
    for validator in data:
        if validator['name'] == "ASXN LABS":
            return validator
    return None

def main():
    # Replace with your actual Telegram bot token and chat ID
    BOT_TOKEN = '7591859108:AAH127pmsz14bUT6NHjcKAyAftTTTLHL9YI'
    CHAT_ID = '-1002277436693'

    # Add usernames or group tags here
    TAGS = ['@ygarg25', '@late281']


    validator_data = get_validator_data()
    asxn_labs = find_asxn_labs_data(validator_data)

    if asxn_labs:
        message = (f"*ASXN LABS Validator Alert:*\n"
                   f"Is Jailed: `{asxn_labs['isJailed']}`\n"
                   f"Stake: `{asxn_labs['stake']}`\n"
                   f"Recent Blocks: `{asxn_labs['nRecentBlocks']}`")
        
        asyncio.run(send_telegram_alert(BOT_TOKEN, CHAT_ID, message, TAGS))
        print("Alert sent successfully!")
    else:
        print("ASXN LABS validator not found in the data.")

if __name__ == "__main__":
    main()