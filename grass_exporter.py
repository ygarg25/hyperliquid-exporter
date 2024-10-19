import os
import time
import logging
import psutil
from prometheus_client import start_http_server, Gauge
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(filename='hl_exporter.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Prometheus metrics
hl_cpu_usage = Gauge('hl_cpu_usage', 'CPU usage percentage')
hl_memory_usage = Gauge('hl_memory_usage', 'Memory usage percentage')
hl_disk_usage = Gauge('hl_disk_usage', 'Disk usage percentage')

def monitor_system_resources():
    while True:
        hl_cpu_usage.set(psutil.cpu_percent())
        memory = psutil.virtual_memory()
        hl_memory_usage.set(memory.percent)
        disk = psutil.disk_usage('/')
        hl_disk_usage.set(disk.percent)
        logging.info(f"Updated metrics - CPU: {psutil.cpu_percent()}%, Memory: {memory.percent}%, Disk: {disk.percent}%")
        time.sleep(60)

if __name__ == "__main__":
    print("ssss")
    # Start Prometheus HTTP server on port 8086
    logging.info("Starting Prometheus HTTP server on port 8086")
    start_http_server(8086)
    logging.info("Prometheus HTTP server started on port 8086")
    print("ssss")
    # Start monitoring thread
    try:
        monitor_system_resources()
    except Exception as e:
        logging.critical(f"Monitoring script encountered an unhandled exception: {e}")
        raise