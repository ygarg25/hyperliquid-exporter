import os
import subprocess

# Define commands and output files
journalctl_cmd = [
    "sudo", "journalctl", "-u","hyperliquid-visor" ,
    "--since", "2024-12-10T09:24:47",
    "--until", "2024-12-10T09:39:12"
]
journalctl_output_file = "1_journalctl_output.log"

grep_cmd = [
    "grep", "-E", "2024-12-10T09:2[5-9]:", "9"
]
grep_output_file = "1_grep_output.log"

suspicious_output_file = "1_suspicious_activity.log"

# Run journalctl command and save output
with open(journalctl_output_file, "w") as f:
    subprocess.run(journalctl_cmd, stdout=f)

# Run grep command and save output
with open(grep_output_file, "w") as f:
    subprocess.run(grep_cmd, stdout=f)

# Define suspicious patterns to look for
suspicious_patterns = ["error", "failed", "warning", "unauthorized", "critical"]

# Scan both outputs for suspicious activity
suspicious_entries = []
for log_file in [journalctl_output_file, grep_output_file]:
    with open(log_file, "r") as f:
        for line in f:
            if any(pattern in line.lower() for pattern in suspicious_patterns):
                suspicious_entries.append(line.strip())

# Save suspicious entries to a file
with open(suspicious_output_file, "w") as f:
    if suspicious_entries:
        f.write("Suspicious Activity Found:\n")
        f.write("\n".join(suspicious_entries))
    else:
        f.write("No suspicious activity detected.")

print("Analysis completed.")
print(f"Journalctl output saved to: {journalctl_output_file}")
print(f"Grep output saved to: {grep_output_file}")
print(f"Suspicious activity saved to: {suspicious_output_file}")
