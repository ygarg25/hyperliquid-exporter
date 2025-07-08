import pandas as pd
import subprocess
import json
import requests
import time
from decimal import Decimal

def run_hl_node_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        print(f"Error running command: {e}")
        return None

def get_delegator_summary(wallet_address):
    url = "https://api.hyperliquid-testnet.xyz/info"
    payload = {
        "type": "delegatorSummary",
        "user": wallet_address
    }
    try:
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print(f"Error getting delegator summary: {e}")
        return None

def process_wallets(input_csv, output_csv, validator_address):
    # Read input CSV
    df = pd.read_csv(input_csv)
    
    # Initialize results lists
    results = []
    
    for index, row in df.iterrows():
        # print(row)
        # exit()
        if not row['comp']:  # Skip if TRUE column is False
            continue
            
        wallet_address = row['Wallet Address']
        private_key = row['private_key']
        current_balance = Decimal(str(row['Current HYPE Balance']))
        
        # Calculate wei amount
        wei_amount = int(current_balance * Decimal('1e8'))
        
        # Step 1: Run staking deposit command
        deposit_cmd = f'~/hl-node --chain Testnet --key {private_key} staking-deposit {wei_amount}'
        print(deposit_cmd)
        deposit_result = run_hl_node_command(deposit_cmd)
        print(deposit_result)
        time.sleep(2)  # Add delay between commands
        
        # Step 2: Run delegate command
        delegate_cmd = f'~/hl-node --chain Testnet --key {private_key} delegate {validator_address} {wei_amount}'
        delegate_result = run_hl_node_command(delegate_cmd)
        time.sleep(2)  # Add delay between commands
        
        # Step 3: Get delegator summary
        summary = get_delegator_summary(wallet_address)
        
        # Store results
        result = {
            'Wallet Address': wallet_address,
            'Private Key': private_key,
            'Genesis Balance': row['Genesis Balance'],
            'Current HYPE Balance': current_balance,
            'Wei Amount': wei_amount,
            'Deposit Status': 'Success' if deposit_result and 'status":"ok' in deposit_result else 'Failed',
            'Delegate Status': 'Success' if delegate_result and 'status":"ok' in delegate_result else 'Failed',
            'Delegated Amount': summary.get('delegated', 'N/A') if summary else 'N/A',
            'Undelegated Amount': summary.get('undelegated', 'N/A') if summary else 'N/A',
            'Pending Withdrawals': summary.get('totalPendingWithdrawal', 'N/A') if summary else 'N/A'
        }
        
        results.append(result)
        
    # Create and save output CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_csv, index=False)
    print(f"Results saved to {output_csv}")

if __name__ == "__main__":
    # Configuration
    INPUT_CSV = "input_wallets.csv"
    OUTPUT_CSV = "staking_results.csv"
    VALIDATOR_ADDRESS = "0xd41281ea0aab1671248ef864bc6df38a5d15b3f0"
    
    process_wallets(INPUT_CSV, OUTPUT_CSV, VALIDATOR_ADDRESS)