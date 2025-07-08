#!/bin/bash

# Record start time
START_TIME=$(date "+%Y-%m-%d %H:%M:%S")
echo "Script started at: $START_TIME"

DATA_PATH="/home/dfuse/hl/data"

# Define how many hours of recent data to keep
HOURS_TO_KEEP=24

echo "Starting pruning of data older than ${HOURS_TO_KEEP} hours..."

# Find directories and files older than specified hours and remove them
find "$DATA_PATH" -mindepth 1 -type d -mmin +$((HOURS_TO_KEEP*60)) -exec rm -rf {} \; 2>/dev/null || true

# Alternative approach with specific directories if needed
for dir in replica_cmds node_logs visor_child_stderr rate_limited_ips; do
    echo "Pruning old data in $dir..."
    find "$DATA_PATH/$dir" -mindepth 1 -type d -mmin +$((HOURS_TO_KEEP*60)) -exec rm -rf {} \; 2>/dev/null || true
done

# Clean up tmp files older than 12 hours
echo "Cleaning tmp files older than 12 hours..."
find /home/dfuse/hl/tmp -type f -mmin +720 -exec rm -f {} \; && echo "Files older than 12 hours deleted."

echo "Pruning completed at: $(date "+%Y-%m-%d %H:%M:%S")"
echo "Total execution time: $(($(date +%s) - $(date -d "$START_TIME" +%s))) seconds"


# Delete data older than 5 days.
# find "$DATA_PATH" -mindepth 1 -depth -mtime +5 -delete
# find "$DATA_PATH" -mindepth 1 -mtime +5 -exec rm -rf {} +

