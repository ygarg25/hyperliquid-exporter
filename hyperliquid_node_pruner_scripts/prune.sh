#!/bin/bash

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

echo "Pruning completed."


# Delete data older than 5 days.
# find "$DATA_PATH" -mindepth 1 -depth -mtime +5 -delete
# find "$DATA_PATH" -mindepth 1 -mtime +5 -exec rm -rf {} +

