DATA_PATH="/home/dfuse/hl/data"

# Delete data older than 5 days.
# find "$DATA_PATH" -mindepth 1 -depth -mtime +5 -delete
find "$DATA_PATH" -mindepth 1 -mtime +5 -exec rm -rf {} +

