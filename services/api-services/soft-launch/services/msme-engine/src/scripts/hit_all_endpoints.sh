#!/usr/bin/env bash
set -euo pipefail

# Wrapper: run the Python automation test harness in src/scripts
# Usage: BASE_URL=http://127.0.0.1:8500 bash src/scripts/hit_all_endpoints.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/automation_test_endpoints.py"

if [ ! -f "$PY_SCRIPT" ]; then
  echo "automation_test_endpoints.py not found in $SCRIPT_DIR"
  exit 2
fi

echo "Running automation tests using $PY_SCRIPT"
if [ -n "${BASE_URL:-}" ]; then
  BASE_URL="$BASE_URL" python "$PY_SCRIPT" --run all
else
  python "$PY_SCRIPT" --run all
fi

