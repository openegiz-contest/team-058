#!/usr/bin/env bash
# V2.3: preserve credentials and volumes, refresh twin definitions, then replace the app.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=deploy/compose/.env
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy it from your existing V2.1 installation; do not regenerate credentials." >&2
  exit 1
fi
PROJECT="${COMPOSE_PROJECT_NAME:-oreflow58}"
COMPOSE=(docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f deploy/compose/docker-compose.yml -f team/oreflow/compose.yml)
command -v docker >/dev/null || { echo 'Docker CLI missing' >&2; exit 1; }
docker info >/dev/null || { echo 'Start Docker Desktop before upgrading' >&2; exit 1; }
echo '[1/5] Starting existing OpenEgiz services (without replacing volumes)...'
"${COMPOSE[@]}" up -d mongodb mosquitto influxdb policies things things-search connectivity gateway ditto-nginx grafana telegraf
# Akka discovery occasionally starts with one contact point after Windows reboot.
# Only restart the gateway if all services were started but the cluster is stuck.
if ! docker exec "${PROJECT}-gateway-1" curl -fsS --max-time 6 http://localhost:8558/ready >/dev/null 2>&1; then
  sleep 12
  if ! docker exec "${PROJECT}-gateway-1" curl -fsS --max-time 6 http://localhost:8558/ready >/dev/null 2>&1; then
    echo 'Rechecking gateway after peer startup...'
    "${COMPOSE[@]}" restart gateway
  fi
fi
echo '[2/5] Building the new application without touching Ditto data...'
"${COMPOSE[@]}" build oreflow-setup
echo '[3/5] Registering all equipment, fuel-station and road twins...'
"${COMPOSE[@]}" up -d --no-deps --force-recreate oreflow-setup
setup_id=$("${COMPOSE[@]}" ps -q oreflow-setup)
setup_exit=$(docker wait "$setup_id")
if [[ "$setup_exit" != 0 ]]; then
  docker logs --tail 80 "$setup_id" >&2
  echo 'Twin setup failed. Existing Docker volumes were left unchanged.' >&2
  exit 1
fi
echo '[4/5] Recreating only OreFlow with a persistent checkpoint volume...'
"${COMPOSE[@]}" up -d --no-deps --force-recreate oreflow
echo '[5/5] Waiting for the local API...' 
ready=0
for n in $(seq 1 35);do
 if curl -fsS --max-time 3 http://127.0.0.1:8099/api/v22/now >/dev/null 2>&1;then ready=1;break;fi
 sleep 2
done
if [[ "$ready" != 1 ]];then
  echo 'OreFlow API is not ready. Check: docker logs --tail 60 '${PROJECT}'-oreflow-1' >&2
  exit 1
fi
"${COMPOSE[@]}" ps oreflow
printf '\nOreFlow 2.3 Competition Edition: http://localhost:8099\n'
printf 'Continuous mine checkpoint: Docker named volume %s_oreflow_state\n' "$PROJECT"
printf 'Full verification: python3 tools/verify-oreflow.py\n'
