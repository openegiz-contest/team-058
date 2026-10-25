#!/usr/bin/env bash
# Explicit user-requested new mine, without deleting original OpenEgiz volumes.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-oreflow58}" bash scripts/oreflow-upgrade-running.sh
printf '\nStarting NEW simulated mine; archiving the previously saved checkpoint...\n'
curl -fsS --max-time 25 \
  -H 'Content-Type: application/json' \
  -d '{"confirm":"START_FRESH"}' \
  http://127.0.0.1:8099/api/v23/fresh-start
printf '\nNew run started. Reload http://localhost:8099\n'
