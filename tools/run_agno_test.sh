#!/usr/bin/env bash
# Wrapper to run the Agno processing test and write logs to logs/process_agno_test.log
set -euo pipefail

# Activate virtualenv
source .venv/bin/activate

mkdir -p logs
LOGFILE=logs/process_agno_test.log
echo "Running process_with_agno.py at $(date)" > "$LOGFILE"
python3 tools/process_with_agno.py --use-agno-py --limit 20 --root ./storage/raw_data --fileserver-base http://localhost:7700/files --verbose >> "$LOGFILE" 2>&1 || true
echo "Finished at $(date)" >> "$LOGFILE"

# Print last 200 lines for convenience
echo "--- last 200 lines of $LOGFILE ---"
tail -n 200 "$LOGFILE"
