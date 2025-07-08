import pandas as pd
import subprocess
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

def process_unstaking(input_csv, output_csv, validator_address):
    # Read input CSV
    df = pd.read_csv(input_csv)
    
    # Initialize results list
    results = []
    
    for _, row in df.iterrows():
        if not row['comp']:  # Skip if TRUE column is False
            continue
            
        wallet_address = row['Wallet Address']
        private_key = row['private_key']
        
        # Step 1: Initial summary
        summary = get_delegator_summary(wallet_address)
        if not summary:
            results.append({
                'Wallet Address': wallet_address,
                'Delegated Amount': 'N/A',
                'Undelegated Amount': 'N/A',
                'Total Pending Withdrawals': 'N/A',
                'Unstake Status': 'Failed: No summary',
                'Withdrawal Status': 'N/A',
                'Error': 'Failed to fetch summary'
            })
            continue
        
        delegated_amount = Decimal(summary.get('delegated', '0.0'))
        undelegated_amount = Decimal(summary.get('undelegated', '0.0'))
        total_pending_withdrawals = Decimal(summary.get('totalPendingWithdrawal', '0.0'))
        
        result = {
            'Wallet Address': wallet_address,
            'Initial Delegated Amount': delegated_amount,
            'Initial Undelegated Amount': undelegated_amount,
            'Initial Total Pending Withdrawals': total_pending_withdrawals,
            'Unstake Status': 'Skipped',
            'Withdrawal Status': 'Skipped',
            'Final Delegated Amount': 'N/A',
            'Final Undelegated Amount': 'N/A',
            'Final Total Pending Withdrawals': 'N/A',
            'Error': None
        }
        
        # Step 2: Unstake if delegated amount is non-zero
        if delegated_amount > 0:
            wei_amount = int(delegated_amount * Decimal('1e8'))
            unstake_cmd = f'~/hl-node --chain Testnet --key {private_key} delegate --undelegate {validator_address} {wei_amount}'
            unstake_result = run_hl_node_command(unstake_cmd)
            time.sleep(2)  # Add delay
            
            if unstake_result and 'status":"ok' in unstake_result and '"response":{"type":"default"}' in unstake_result:
                result['Unstake Status'] = 'Success'
            else:
                result['Unstake Status'] = 'Failed'
                result['Error'] = 'Failed to unstake'
        
        # Step 3: Fetch summary again after unstaking
        summary = get_delegator_summary(wallet_address)
        if summary:
            delegated_amount = Decimal(summary.get('delegated', '0.0'))
            undelegated_amount = Decimal(summary.get('undelegated', '0.0'))
            total_pending_withdrawals = Decimal(summary.get('totalPendingWithdrawal', '0.0'))
        
        result['Final Delegated Amount'] = delegated_amount
        result['Final Undelegated Amount'] = undelegated_amount
        result['Final Total Pending Withdrawals'] = total_pending_withdrawals
        
        # Step 4: Withdraw if undelegated amount is non-zero
        if undelegated_amount > 0:
            wei_amount = int(undelegated_amount * Decimal('1e8'))
            withdraw_cmd = f'~/hl-node --chain Testnet --key {private_key} staking-withdrawal {wei_amount}'
            withdraw_result = run_hl_node_command(withdraw_cmd)
            time.sleep(2)  # Add delay
            
            if withdraw_result and 'status":"ok' in withdraw_result:
                result['Withdrawal Status'] = 'Success'
            else:
                result['Withdrawal Status'] = 'Failed'
                result['Error'] = 'Failed to withdraw'
        
        # Step 5: Fetch summary again after withdrawal
        summary = get_delegator_summary(wallet_address)
        if summary:
            result['Final Delegated Amount'] = Decimal(summary.get('delegated', '0.0'))
            result['Final Undelegated Amount'] = Decimal(summary.get('undelegated', '0.0'))
            result['Final Total Pending Withdrawals'] = Decimal(summary.get('totalPendingWithdrawal', '0.0'))
        
        results.append(result)
    
    # Create and save output CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_csv, index=False)
    print(f"Results saved to {output_csv}")

if __name__ == "__main__":
    # Configuration
    INPUT_CSV = "input_wallets.csv"
    OUTPUT_CSV = "unstaking_results.csv"
    VALIDATOR_ADDRESS = "0xd41281ea0aab1671248ef864bc6df38a5d15b3f0"
    
    process_unstaking(INPUT_CSV, OUTPUT_CSV, VALIDATOR_ADDRESS)
