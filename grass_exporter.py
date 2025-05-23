import os
import time
import logging
import psutil
import requests
from prometheus_client import start_http_server, Gauge
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables and create logs directory
load_dotenv()
os.makedirs('logs', exist_ok=True)

# Set up logging with rotation
def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    # log_file = os.path.join('logs', f'grn_exporter_{datetime.now().strftime("%Y-%m-%d")}.log')
    log_file = os.path.join('logs', f'grn_exporter.log')

    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers to prevent duplicates
    if logger.handlers:
        for handler in logger.handlers:
            logger.removeHandler(handler)
    
    # Add rotating file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=30
    )
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    
    logging.info("Logging setup completed")

# Initialize logging
setup_logging()

# Prometheus metrics
grn_cpu_usage = Gauge('grn_cpu_usage', 'CPU usage percentage')
grn_memory_usage = Gauge('grn_memory_usage', 'Memory usage percentage')
grn_disk_usage = Gauge('grn_disk_usage', 'Disk usage percentage')
grn_health_status = Gauge('grn_health_status', 'Health status (1 for OK, 0 for not OK)')

def check_health():
    try:
        response = requests.get('https://grassrouter.asxn.xyz/health')
        if response.status_code == 200 and response.json().get('status') == 'ok':
            return 1
        else:
            return 0
    except Exception as e:
        logging.error(f"Error checking health status: {e}")
        return 0

def monitor_system_resources():
    while True:
        grn_cpu_usage.set(psutil.cpu_percent())
        memory = psutil.virtual_memory()
        grn_memory_usage.set(memory.percent)
        disk = psutil.disk_usage('/')
        grn_disk_usage.set(disk.percent)
        health_status = check_health()
        grn_health_status.set(health_status)
        logging.info(f"Updated metrics - CPU: {psutil.cpu_percent()}%, Memory: {memory.percent}%, Disk: {disk.percent}%, Health: {health_status}")
        time.sleep(60)

if __name__ == "__main__":
    # Start Prometheus HTTP server on port 8086
    logging.info("Starting Prometheus HTTP server on port 8086")
    start_http_server(8086)
    logging.info("Prometheus HTTP server started on port 8086")

    # Start monitoring thread
    try:
        monitor_system_resources()
    except Exception as e:
        logging.critical(f"Monitoring script encountered an unhandled exception: {e}")
        raise