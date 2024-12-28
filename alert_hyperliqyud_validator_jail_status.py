import requests
import time
from datetime import datetime, timezone
import threading

# Configuration for Testnet and Mainnet
CONFIG = [
    {
        "api_url": "https://api.hyperliquid-testnet.xyz/info",
        "validator_name": "ASXN",
        "alert_message": "Testnet validator is jailed!",
        "server_name": "Testnet Server"
    },
    {
        "api_url": "https://api.hyperliquid.xyz/info",
        "validator_name": "ASXN LABS",
        "alert_message": "Mainnet validator is jailed!",
        "server_name": "Mainnet Server"
    }
]

HEADERS = {'Content-Type': 'application/json'}
PAYLOAD = {"type": "validatorSummaries"}

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = ""  # Replace with your bot's token
TELEGRAM_CHAT_ID = ""  # Replace with your chat or group ID


# Function to send a Telegram message
def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": "@late281,@ygarg25,@munehisa_asxn\n" + message,
        "parse_mode": "HTML"  # Allows formatting the message with HTML
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Telegram message sent successfully.")
    else:
        print(f"Failed to send Telegram message: {response.text}")


# Function to fetch validator data
def fetch_validator_data(api_url):
    response = requests.post(api_url, headers=HEADERS, json=PAYLOAD)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data from {api_url}: {response.status_code} {response.text}")
        return None


# Function to process a single server's validator
def process_server(conf):
    while True:
        data = fetch_validator_data(conf["api_url"])
        if not data:
            print(f"No data fetched from {conf['api_url']}, retrying in 60 seconds...")
            time.sleep(60)
            continue

        for validator in data:
            if validator.get("name") == conf["validator_name"]:
                is_jailed = validator.get("isJailed", False)
                unjailable_after = validator.get("unjailableAfter", 0)
                stake = validator.get("stake", 0)

                if is_jailed:
                    alert_message = (
                        f"<b>{conf['alert_message']}</b>\n"
                        f"<b>Validator Name:</b> {conf['validator_name']}\n"
                        f"<b>Stake:</b> {stake}\n"
                        f"<b>Please investigate immediately!</b>"
                    )
                    send_telegram_message(alert_message)

                    # Calculate time to unjail with timezone-aware datetimes
                    unjailable_time = datetime.fromtimestamp(unjailable_after / 1000.0, tz=timezone.utc)
                    now = datetime.now(tz=timezone.utc)
                    time_diff = unjailable_time - now

                    print(f"{conf['server_name']}: Validator '{conf['validator_name']}' is jailed. "
                          f"Next check after {time_diff}.")
                    time.sleep(max(time_diff.total_seconds(), 600))
                else:
                    print(f"{conf['server_name']}: Validator '{conf['validator_name']}' is not jailed.")
                    time.sleep(300)


# Start monitoring
if __name__ == "__main__":
    threads = []
    for conf in CONFIG:
        thread = threading.Thread(target=process_server, args=(conf,))
        threads.append(thread)
        thread.start()

    # Join threads to keep the script running
    for thread in threads:
        thread.join()
