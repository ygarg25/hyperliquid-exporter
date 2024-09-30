import requests
import os
import json
import time
import logging
import subprocess
import threading
import psutil
import glob
from datetime import datetime
from prometheus_client import start_http_server, Counter, Gauge, Info
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variables
NODE_HOME = os.getenv('NODE_HOME')
if not NODE_HOME:
    NODE_HOME = os.path.expanduser('~')
NODE_BINARY = os.getenv('NODE_BINARY')
if not NODE_BINARY:
    NODE_BINARY = os.path.expanduser('~/hl-visor')
IS_VALIDATOR = os.getenv('IS_VALIDATOR', 'false').lower() == 'true'
VALIDATOR_ADDRESS = os.getenv('VALIDATOR_ADDRESS', '')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Prometheus metrics
hl_proposer_counter = Counter('hl_proposer_count', 'Count of proposals by proposer', ['proposer'])
hl_block_height_gauge = Gauge('hl_block_height', 'Block height from latest block time file')
hl_apply_duration_gauge = Gauge('hl_apply_duration', 'Apply duration from latest block time file')
hl_validator_jailed_status = Gauge('hl_validator_jailed_status', 'Jailed status of validators', ['validator', 'name'])
hl_validator_count_gauge = Gauge('hl_validator_count', 'Total number of validators')
hl_software_version_info = Info('hl_software_version', 'Software version information')
hl_software_up_to_date = Gauge('hl_software_up_to_date', 'Indicates if the current software is up to date (1) or not (0)')
hl_cpu_usage = Gauge('hl_cpu_usage', 'CPU usage percentage')
hl_memory_usage = Gauge('hl_memory_usage', 'Memory usage percentage')
hl_disk_usage = Gauge('hl_disk_usage', 'Disk usage percentage')
hl_network_in = Gauge('hl_network_in', 'Network inbound traffic (bytes/sec)')
hl_network_out = Gauge('hl_network_out', 'Network outbound traffic (bytes/sec)')
hl_peer_count = Gauge('hl_peer_count', 'Number of connected peers')
hl_latest_block_time = Gauge('hl_latest_block_time', 'Timestamp of the latest block')
hl_node_running = Gauge('hl_node_running', 'Indicates if the node is running (1) or not (0)')
hl_monitor_script_running = Gauge('hl_monitor_script_running', 'Indicates if the monitoring script is running (1) or not (0)')
hl_oldest_log_file_age = Gauge('hl_oldest_log_file_age', 'Age of the oldest log file in days')
hl_oldest_block_data_age = Gauge('hl_oldest_block_data_age', 'Age of the oldest block data in days')

# Global variables
current_commit_hash = ''
validator_mapping = {}

def get_latest_file(directory):
    latest_file = None
    latest_time = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_mtime = os.path.getmtime(file_path)
                if file_mtime > latest_time:
                    latest_time = file_mtime
                    latest_file = file_path
            except Exception as e:
                logging.error(f"Error accessing file {file_path}: {e}")

    if latest_file is None:
        logging.warning(f"No files found in the directory {directory}.")
    return latest_file

def parse_log_line(line):
    try:
        log_entry = json.loads(line)
        proposer = log_entry.get("abci_block", {}).get("proposer", None)
        if proposer:
            hl_proposer_counter.labels(proposer=proposer).inc()
            logging.info(f"Proposer {proposer} counter incremented.")
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON: {line}")
    except Exception as e:
        logging.error(f"Error processing line: {e}")

def stream_log_file(file_path, logs_dir, from_start=False):
    logging.info(f"Streaming log file: {file_path}, from_start={from_start}")
    with open(file_path, 'r') as log_file:
        if not from_start:
            log_file.seek(0, os.SEEK_END)
        while True:
            line = log_file.readline()
            if not line:
                latest_file = get_latest_file(logs_dir)
                if latest_file != file_path:
                    logging.info(f"Switching to new log file: {latest_file}")
                    return latest_file
                time.sleep(1)
                continue
            parse_log_line(line)

def proposal_count_monitor():
    logs_dir = os.path.join(NODE_HOME, "hl/data/replica_cmds")
    latest_file = get_latest_file(logs_dir)
    first_run = True
    while True:
        if latest_file:
            logging.info(f"Found latest log file: {latest_file}")
            try:
                from_start = not first_run
                new_file = stream_log_file(latest_file, logs_dir, from_start=from_start)
                if new_file:
                    latest_file = new_file
                    first_run = False
            except Exception as e:
                logging.error(f"Error while streaming the file {latest_file}: {e}")
        else:
            logging.info("No log files found. Retrying in 10 seconds...")
        time.sleep(10)

def parse_block_time_line(line):
    try:
        data = json.loads(line)
        block_height = data.get('height', None)
        block_time = data.get('block_time', None)
        apply_duration = data.get('apply_duration', None)
        if block_height is not None:
            hl_block_height_gauge.set(int(block_height))
        if apply_duration is not None:
            hl_apply_duration_gauge.set(float(apply_duration))
        logging.info(f"Updated metrics: height={block_height}, block_time={block_time}, apply_duration={apply_duration}")
    except json.JSONDecodeError:
        logging.error(f"Error parsing line: {line}")
    except Exception as e:
        logging.error(f"Error updating metrics: {e}")

def stream_block_time_file(file_path, logs_dir, from_start=False):
    logging.info(f"Streaming block time file: {file_path}, from_start={from_start}")
    with open(file_path, 'r') as log_file:
        if not from_start:
            log_file.seek(0, os.SEEK_END)
        while True:
            line = log_file.readline()
            if not line:
                latest_file = get_latest_file(logs_dir)
                if latest_file != file_path:
                    logging.info(f"Switching to new block time file: {latest_file}")
                    return latest_file
                time.sleep(1)
                continue
            parse_block_time_line(line)

def block_time_monitor():
    block_time_dir = os.path.join(NODE_HOME, 'hl/data/block_times')
    latest_file = get_latest_file(block_time_dir)
    first_run = True
    while True:
        if latest_file:
            logging.info(f"Found latest block time file: {latest_file}")
            try:
                from_start = not first_run
                new_file = stream_block_time_file(latest_file, block_time_dir, from_start=from_start)
                if new_file:
                    latest_file = new_file
                    first_run = False
            except Exception as e:
                logging.error(f"Error while streaming block time file {latest_file}: {e}")
        else:
            logging.info("No block time files found. Retrying in 5 seconds...")
        time.sleep(5)

def update_validator_mapping():
    global validator_mapping
    while True:
        try:
            logging.info("Fetching validator summaries...")
            url = 'https://api.hyperliquid-testnet.xyz/info'
            headers = {'Content-Type': 'application/json'}
            data = json.dumps({"type": "validatorSummaries"})
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            validator_summaries = response.json()
            new_mapping = {}
            for summary in validator_summaries:
                full_address = summary['validator']
                name = summary.get('name', 'Unknown')
                shortened_address = f"{full_address[:6]}..{full_address[-4:]}"
                new_mapping[shortened_address] = {'full_address': full_address, 'name': name}
            validator_mapping = new_mapping
            hl_validator_count_gauge.set(len(validator_summaries))
            logging.info(f"Validator mapping updated. Total validators: {len(validator_summaries)}")
        except Exception as e:
            logging.error(f"Error fetching validator summaries: {e}")
        time.sleep(600)

def parse_consensus_log_line(line):
    global validator_mapping
    try:
        data = json.loads(line)
        jailed_validators = data[1][1].get('jailed_validators', [])
        round_to_stakes = data[1][1].get('execution_state', {}).get('round_to_stakes', [])
        all_validators = set()
        for round_entry in round_to_stakes:
            validators_list = round_entry[1]
            for validator_entry in validators_list:
                validator_short = validator_entry[0]
                all_validators.add(validator_short)
        for validator_short in all_validators:
            mapping_entry = validator_mapping.get(validator_short, {})
            full_address = mapping_entry.get('full_address', validator_short)
            name = mapping_entry.get('name', 'Unknown')
            is_jailed = 1 if validator_short in jailed_validators else 0
            hl_validator_jailed_status.labels(validator=full_address, name=name).set(is_jailed)
            status_str = "jailed" if is_jailed else "not jailed"
            logging.info(f"Validator {full_address} ({name}) is {status_str}.")
    except Exception as e:
        logging.error(f"Error parsing consensus log line: {e}")

def stream_consensus_log_file(file_path, logs_dir, from_start=False):
    logging.info(f"Streaming consensus log file: {file_path}, from_start={from_start}")
    with open(file_path, 'r') as log_file:
        if not from_start:
            log_file.seek(0, os.SEEK_END)
        while True:
            line = log_file.readline()
            if not line:
                latest_file = get_latest_file(logs_dir)
                if latest_file != file_path:
                    logging.info(f"Switching to new consensus log file: {latest_file}")
                    return latest_file
                time.sleep(1)
                continue
            parse_consensus_log_line(line)

def consensus_log_file_monitor():
    consensus_dir = os.path.join(NODE_HOME, f"hl/data/consensus{VALIDATOR_ADDRESS}")
    if not os.path.exists(consensus_dir):
        logging.error(f"Consensus directory {consensus_dir} does not exist. Are you sure you're a validator?")
        return
    first_run = True
    while True:
        latest_file = get_latest_file(consensus_dir)
        if latest_file:
            logging.info(f"Found latest consensus file: {latest_file}")
            try:
                from_start = not first_run
                new_file = stream_consensus_log_file(latest_file, consensus_dir, from_start=from_start)
                if new_file:
                    latest_file = new_file
                    first_run = False
            except Exception as e:
                logging.error(f"Error while streaming consensus file {latest_file}: {e}")
        else:
            logging.info("No consensus log files found. Retrying in 10 seconds...")
        time.sleep(10)

def software_version_monitor():
    global current_commit_hash
    while True:
        try:
            result = subprocess.run([NODE_BINARY, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            version_output = result.stdout.decode('utf-8').strip()
            parts = version_output.split('|')
            if len(parts) >= 3:
                commit_line = parts[0]
                date = parts[1]
                uncommitted_status = parts[2]
                commit_parts = commit_line.split(' ')
                if len(commit_parts) >= 2:
                    commit_hash = commit_parts[1]
                else:
                    commit_hash = ''
                current_commit_hash = commit_hash
                hl_software_version_info.info({'commit': commit_hash, 'date': date})
                logging.info(f"Updated software version: commit={commit_hash}, date={date}")
            else:
                logging.error(f"Unexpected version output format: {version_output}")
        except Exception as e:
            logging.error(f"Error getting software version: {e}")
        time.sleep(60)

def check_software_update():
    global current_commit_hash
    url = 'https://binaries.hyperliquid.xyz/Testnet/hl-visor'
    local_latest_binary = '/tmp/hl-visor-latest'
    while True:
        try:
            logging.info("Downloading the latest binary...")
            result = subprocess.run(['curl', '-sSL', '-o', local_latest_binary, url], check=True)
            os.chmod(local_latest_binary, 0o755)
            result = subprocess.run([local_latest_binary, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            latest_version_output = result.stdout.decode('utf-8').strip()
            parts = latest_version_output.split('|')
            if len(parts) >= 3:
                commit_line = parts[0]
                latest_date = parts[1]
                uncommitted_status = parts[2]
                commit_parts = commit_line.split(' ')
                if len(commit_parts) >= 2:
                    latest_commit_hash = commit_parts[1]
                else:
                    latest_commit_hash = ''
                if current_commit_hash == '':
                    logging.warning("Current commit hash is not available yet.")
                else:
                    if current_commit_hash == latest_commit_hash:
                        hl_software_up_to_date.set(1)
                        logging.info("Software is up to date.")
                    else:
                        hl_software_up_to_date.set(0)
                        logging.info("Software is NOT up to date.")
            else:
                logging.error(f"Unexpected latest version output format: {latest_version_output}")
        except Exception as e:
            logging.error(f"Error checking software update: {e}")
        time.sleep(300)

def monitor_system_resources():
    while True:
        hl_cpu_usage.set(psutil.cpu_percent())
        memory = psutil.virtual_memory()
        hl_memory_usage.set(memory.percent)
        disk = psutil.disk_usage('/')
        hl_disk_usage.set(disk.percent)
        net_io = psutil.net_io_counters()
        hl_network_in.set(net_io.bytes_recv)
        hl_network_out.set(net_io.bytes_sent)
        time.sleep(60)

def fetch_peer_count():
    while True:
        try:
            # Assuming there's an API endpoint to get peer count
            response = requests.get('http://localhost:8545/peer_count')
            peer_count = response.json()['count']
            hl_peer_count.set(peer_count)
        except Exception as e:
            logging.error(f"Error fetching peer count: {e}")
        time.sleep(300)

def fetch_latest_block_time():
    while True:
        try:
            # Assuming there's an API endpoint to get the latest block
            response = requests.get('http://localhost:8545/latest_block')
            block_time = response.json()['timestamp']
            hl_latest_block_time.set(block_time)
        except Exception as e:
            logging.error(f"Error fetching latest block time: {e}")
        time.sleep(60)

# def check_node_running():
#     while True:
#         try:
#             cmd = "pgrep -f 'hl-visor run-non-validator'"
#             result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#             if result.returncode == 0:
#                 hl_node_running.set(1)
#                 logging.info("Node is running.")
#             else:
#                 hl_node_running.set(0)
#                 logging.warning("Node is not running!")
#                 restart_cmd = "~/hl-visor run-non-validator"
#                 subprocess.Popen(restart_cmd, shell=True, start_new_session=True)
#                 logging.info("Attempting to restart the node.")
#         except Exception as e:
#             logging.error(f"Error checking node status: {e}")
#         time.sleep(60)

# def check_node_running():
#     while True:
#         try:
#             # Check the status of the hyperliquid-visor service
#             cmd = "systemctl is-active hyperliquid-visor.service"
#             result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
#             if result.stdout.strip() == 'active':
#                 hl_node_running.set(1)
#                 logging.info("Node is running.")
#             else:
#                 hl_node_running.set(0)
#                 logging.warning("Node is not running!")
                
#                 # Attempt to restart the service
#                 restart_cmd = "sudo systemctl restart hyperliquid-visor.service"
#                 subprocess.run(restart_cmd, shell=True)
#                 logging.info("Attempting to restart the node.")
#         except Exception as e:
#             logging.error(f"Error checking node status: {e}")
#             hl_node_running.set(0)  # Assume node is not running if there's an error
#         time.sleep(60)

def check_node_running():
    """
    This function monitors the status of the hyperliquid-visor service using systemctl. 
    If the service is not running, it attempts to restart the service. 
    It also monitors the service logs for warnings and errors.
    """
    while True:
        try:
            # Check the status of the hyperliquid-visor service
            cmd = "systemctl is-active hyperliquid-visor.service"
            result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.stdout.strip() == 'active':
                hl_node_running.set(1)
                logging.info("Node is running.")

                # Capture and check logs for warnings or errors using journalctl
                log_cmd = "journalctl -u hyperliquid-visor.service --since '5 minutes ago' --no-pager | grep -iE 'error'"
                # log_cmd = "journalctl -u hyperliquid-visor.service --since '5 minutes ago' --no-pager | grep -iE 'warn|error'"
                log_result = subprocess.run(log_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if log_result.stdout:
                    # Log any warning or error messages from the service
                    logging.warning(f"Service warnings/errors detected: {log_result.stdout.strip()}")
                    
                    # Optionally, set a metric for warning/error detection
                    hl_node_running.set(0.5)  # Custom value indicating warnings/errors in the logs
                else:
                    logging.info("No warnings or errors detected in the logs.")
                    
            else:
                hl_node_running.set(0)
                logging.warning("Node is not running!")

                # Attempt to restart the service
                restart_cmd = "sudo systemctl restart hyperliquid-visor.service"
                restart_result = subprocess.run(restart_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                if restart_result.returncode == 0:
                    logging.info("Node restarted successfully.")
                else:
                    logging.error(f"Failed to restart node: {restart_result.stderr}")

        except Exception as e:
            logging.error(f"Error checking node status or logs: {e}")
            hl_node_running.set(0)  # Assume node is not running if there's an error
        
        # Sleep for 60 seconds before checking again
        time.sleep(60)

def update_monitor_script_status():
    while True:
        hl_monitor_script_running.set(1)
        logging.info("Monitor script is running.")
        time.sleep(60)

def check_oldest_data():
    while True:
        try:
            log_dir = os.path.join(NODE_HOME, "hl/data/replica_cmds")
            log_files = glob.glob(os.path.join(log_dir, "*"))
            if log_files:
                oldest_log = min(log_files, key=os.path.getctime)
                oldest_log_age = (datetime.now() - datetime.fromtimestamp(os.path.getctime(oldest_log))).days
                hl_oldest_log_file_age.set(oldest_log_age)
                logging.info(f"Oldest log file is {oldest_log_age} days old")

            block_dir = os.path.join(NODE_HOME, "hl/data/block_times")
            block_files = glob.glob(os.path.join(block_dir, "*"))
            if block_files:
                oldest_block = min(block_files, key=os.path.getctime)
                oldest_block_age = (datetime.now() - datetime.fromtimestamp(os.path.getctime(oldest_block))).days
                hl_oldest_block_data_age.set(oldest_block_age)
                logging.info(f"Oldest block data is {oldest_block_age} days old")
        except Exception as e:
            logging.error(f"Error checking oldest data: {e}")
        time.sleep(3600)

if __name__ == "__main__":
    # Start Prometheus HTTP server on port 8086
    logging.info("Starting Prometheus HTTP server on port 8086")
    start_http_server(8086)
    logging.info("Prometheus HTTP server started on port 8086")

    # Start monitoring threads
    threads = [
        (proposal_count_monitor, "proposal count monitoring"),
        (block_time_monitor, "block time monitoring"),
        (update_validator_mapping, "validator mapping updater"),
        (software_version_monitor, "software version monitoring"),
        (check_software_update, "software update checking"),
        (monitor_system_resources, "system resource monitoring"),
        (fetch_peer_count, "peer count monitoring"),
        (fetch_latest_block_time, "latest block time monitoring"),
        (check_node_running, "node status monitoring"),
        (update_monitor_script_status, "monitor script status"),
        (check_oldest_data, "oldest data monitoring")
    ]

    if IS_VALIDATOR:
        if not VALIDATOR_ADDRESS:
            logging.error("VALIDATOR_ADDRESS is not set. Cannot start consensus log monitor.")
        else:
            threads.append((consensus_log_file_monitor, "consensus log monitoring"))

    for thread_func, thread_name in threads:
        thread = threading.Thread(target=thread_func)
        thread.daemon = True
        thread.start()
        logging.info(f"Started {thread_name} thread.")

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except Exception as e:
        logging.critical(f"Monitoring script encountered an unhandled exception: {e}")
        hl_monitor_script_running.set(0)
        raise