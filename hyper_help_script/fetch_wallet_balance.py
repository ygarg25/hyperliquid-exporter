import pandas as pd
import requests
import time

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
        print(f"Error getting delegator summary for {wallet_address}: {e}")
        return None

def fetch_balances(input_csv, output_csv):
    # Read input CSV
    df = pd.read_csv(input_csv)
    
    # Initialize results list
    results = []
    
    for _, row in df.iterrows():
        wallet_address = row['Wallet Address']
        
        # Fetch delegator summary
        summary = get_delegator_summary(wallet_address)
        time.sleep(1)  # Delay to avoid overloading the API
        
        if summary:
            result = {
                'Wallet Address': wallet_address,
                'Delegated Amount': summary.get('delegated', 'N/A'),
                'Undelegated Amount': summary.get('undelegated', 'N/A'),
                'Total Pending Withdrawals': summary.get('totalPendingWithdrawal', 'N/A'),
                'Number of Pending Withdrawals': summary.get('nPendingWithdrawals', 'N/A'),
            }
        else:
            result = {
                'Wallet Address': wallet_address,
                'Delegated Amount': 'N/A',
                'Undelegated Amount': 'N/A',
                'Total Pending Withdrawals': 'N/A',
                'Number of Pending Withdrawals': 'N/A',
                'Error': 'Failed to fetch summary'
            }
        
        results.append(result)
    
    # Create and save output CSV
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_csv, index=False)
    print(f"Results saved to {output_csv}")

if __name__ == "__main__":
    # Configuration
    INPUT_CSV = "input_wallets.csv"  # Input file with Wallet Address column
    OUTPUT_CSV = "wallet_balances.csv"  # Output file to save API results
    
    fetch_balances(INPUT_CSV, OUTPUT_CSV)
