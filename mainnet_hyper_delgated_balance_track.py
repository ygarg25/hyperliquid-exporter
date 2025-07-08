import requests
import json
import time
from datetime import datetime, timedelta

# Slack and API Configuration
SLACK_TOKEN = "xoxb-your-actual-token-here"
SLACK_CHANNEL = "#liquidation_monitor"
API_URL = "https://api.hyperliquid.xyz/info"
API_HEADERS = {"Content-Type": "application/json"}
PAYLOAD = {"type": "delegatorSummary", "user": "0xe45c96a6a32318e5df7347477963bf0de38ff7ff"}

# Interval settings (in seconds)
CHECK_INTERVAL = 15 * 60  # 15 minutes
HEARTBEAT_INTERVAL = 12 * 60 * 60  # 12 hours

# Slack Notification Function
def send_slack_notification(message):
    url = "https://slack.com/api/chat.postMessage"
    payload = {
        "channel": SLACK_CHANNEL,
        "text": message
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"{SLACK_BOT_TOKEN}"
    }
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        response.raise_for_status()
        print(f"Slack notification sent: {message}")
    except Exception as e:
        print(f"Error sending Slack notification: {e}")

# API Fetch Function
def fetch_api_data():
    try:
        response = requests.post(API_URL, json=PAYLOAD, headers=API_HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching API data: {e}")
        return None

# Monitoring Function
def monitor():
    last_heartbeat_time = datetime.min  # Initialize last heartbeat time
    while True:
        current_time = datetime.now()

        # Fetch API data
        data = fetch_api_data()
        if data:
            delegated = float(data.get("delegated", 0))
            undelegated = float(data.get("undelegated", 0))
            total_pending_withdrawal = float(data.get("totalPendingWithdrawal", 0))

            # Check heartbeat
            if (current_time - last_heartbeat_time).total_seconds() >= HEARTBEAT_INTERVAL:
                # Send a heartbeat message with the API response
                message = (
                    "--------------------------------------"
                    "\n✅ Hyperliquid Validator Mainnet:\n"
                    "Monitoring script is running fine and active.\n\n"
                    f"API Response:\n"
                    f"- Delegated: {delegated}\n"
                    f"- Undelegated: {undelegated}\n"
                    f"- Total Pending Withdrawal: {total_pending_withdrawal}"
                )
                send_slack_notification(message)
                last_heartbeat_time = current_time

            print(delegated,type(delegated),undelegated,type(undelegated),total_pending_withdrawal,type(total_pending_withdrawal),total_pending_withdrawal)

            # Check thresholds and send alerts if necessary
            if delegated < 1000:
                send_slack_notification(f"⚠️ Alert: Hyperliquid Validator Mainnet:\nDelegated value is below 10k ({delegated}). Please review!")

            if undelegated > 1000 or total_pending_withdrawal > 1000:
                send_slack_notification(
                    f"⚠️ Alert: Hyperliquid Validator Mainnet:\nUndelegated ({undelegated}) or Total Pending Withdrawal ({total_pending_withdrawal}) exceeds 10k. Please review!"
                )

        # Wait for the next interval
        print(f"Checked at {current_time}. Waiting for the next check in {CHECK_INTERVAL / 60} minutes...")
        time.sleep(CHECK_INTERVAL)

# Run the monitoring loop
if __name__ == "__main__":
    try:
        print("Starting monitoring script...")
        monitor()
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
