#!/usr/bin/env bash
# Wait for genuine, live end-to-end stack readiness without inventing status.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v python3 >/dev/null 2>&1; then echo "python3 required" >&2; exit 1; fi
for attempt in $(seq 1 48); do
  if python3 tools/verify-oreflow.py; then
    echo "OreFlow verified on the actual Docker stack."
    exit 0
  fi
  if [ "$attempt" -ge 48 ]; then break; fi
  echo "Telemetry / Ditto synchronization incomplete ($attempt/48). Retrying in 10 seconds..."
  sleep 10
done
echo "OreFlow did not pass strict integration verification within 8 minutes. Check Docker logs; no data was reset." >&2
exit 1
