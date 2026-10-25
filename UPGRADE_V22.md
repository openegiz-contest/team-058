# OreFlow KZ 2.2 — Continuous Mine Control

## What changed

This is a **simulation-driven decision-support tool**, not live GPS or a production mine digital twin. It preserves the OpenMines North Pit equipment configuration, 71 trucks, 20 shovels, existing MQTT/Eclipse Ditto names and the OpenEgiz services.

- **Continuous event simulation**: the same truck states, fuel, shovel schedules and queues advance past midnight. There is no fixed 24-hour end. Default 5 simulated minutes per real second; pause or choose 1, 5, 15 or 60 simulated minutes per second. Changing the rate does not alter results for the same simulated duration.
- **Restart-safe**: checkpoints are saved atomically about every 30 seconds and upon control or incident changes. A named Docker volume stores mine state. A Windows/Docker restart resumes the last checkpoint; simulation time **does not progress while Docker is stopped**. An unplanned power loss may lose up to ~30 seconds of wall-clock progress.
- **Daily reports**: every 1440 simulated minutes, event-derived JSON is written to the state volume. The website can export the rolling last-day CSV and individual completed day CSVs or print the report to PDF.
- **Bounded active history**: after daily reports are written, old raw trip/segment events are archived out of RAM, retaining at least two simulated days of detailed events. Cumulative tonnes, trips and fuel remain exact; individual older event details are retained in their saved daily aggregates, not as full trip logs.
- **Five redesigned views**: Operations, Recommendations, Scenarios, Fleet & Equipment, Reports. The main screen updates automatically; history/clock controls live in the small header.
- **Evidence-backed decisions**: at meaningful modeled congestion, the engine evaluates dispatch alternatives from the **same current mine state**. A user can also trigger forecasts. All three strategies are considered; the current policy can remain recommended.
- **What-If**: branch from the current trucks, shovel schedules, queues and tank levels, change one incident, and compare future performance. No preset gain percentages. The forecast does **not** alter the running mine unless the user explicitly applies it.
- **Live digital twin readback**: clicking a vehicle reads its stored Ditto state automatically; technical JSON is hidden behind a disclosure. The header shows overall connected/fresh status and does not claim InfluxDB history is checked from that light probe.

## Install on a PC already running OreFlow 2.1

1. Download `OreFlow_KZ_Team058_V22_Live_Control.zip` from Google Drive into Windows Downloads.
2. Open Ubuntu WSL and run:

```bash
set -e
unzip -oq "/mnt/c/Users/dzzen/Downloads/OreFlow_KZ_Team058_V22_Live_Control.zip" -d ~/OreFlow_Team058_V22
cp ~/OreFlow_Team058_V21/team-058-main/deploy/compose/.env \
   ~/OreFlow_Team058_V22/team-058-main/deploy/compose/.env
cd ~/OreFlow_Team058_V22/team-058-main
COMPOSE_PROJECT_NAME=oreflow58 bash scripts/oreflow-upgrade-running.sh
python3 tools/verify-oreflow.py
```

Do **not** delete your existing Docker volumes or regenerate `.env`. The upgrade script starts the existing platform infrastructure and recreates only the OreFlow application. Docker will add a separate `oreflow58_oreflow_state` named volume for the continuous simulation.

Open `http://localhost:8099`. No need to select a simulated run duration; the mine starts operating automatically and keeps running in Docker when the browser is closed.

## Exposed new APIs

`GET /api/v22/now`, `GET /api/v22/config`, `GET /api/v22/status`, `GET /api/v22/reports`, `GET /api/v22/day?day=1`, `GET /api/v22/job`.

`POST /api/v22/control` `{ "playing": false }` or `{ "rate": 5 }`.

`POST /api/v22/evaluate` `{ "kind":"advice", "horizon_hours":4 }` or `{ "kind":"scenario", "scenario":"shovel_outage", "affected":"shovel-3-1", "duration_min":120, "delay_min":15, "horizon_hours":4 }`.

`POST /api/v22/policy` `{ "policy":"balanced" }` changes **future** dispatch assignments only.

`POST /api/v22/incident` with the same incident selector explicitly applies it to the operating mine.

Old API paths remain present where compatible; the new interface uses `/api/v22/*`. The live verifier now tests the continuous run rather than expecting a fixed-duration replay.

## Important modeling limits

- This does not ingest live physical measurements. It uses source-derived OpenMines configuration and an event model that generates all operations.
- Tank capacities are reference-class proxies and assumed rates—not confirmed field fuel measurements. Road grades, maintenance, breakdowns, shift relief and fuel station rules are assumptions.
- Dispatch policies are heuristics, not proven globally optimal algorithms. Advice is one modeled, deterministic paired-state comparison. Claims of real-world gains would need external validation.
- High simulation speeds may appear jumpy on the map. Speed is adjustable but event calculations should stay deterministic.
- The optional standalone Extended API Git build is *not* required to run OreFlow.
- The Docker-host MQTT → Ditto → InfluxDB integration has to be verified on the actual user's machine after installation; local Python tests cannot substitute for that.
- Checkpoints are local Python pickle files in the private Docker volume; do not copy untrusted files into that directory.

## Troubleshooting

If the UI responds but data isn't reaching Ditto, run `python3 tools/verify-oreflow.py`, then check `docker ps -a --filter name=oreflow58`, `docker logs --tail 60 oreflow58-oreflow-1`, and `docker logs --tail 60 oreflow58-connectivity-1`.

If the full verifier reports only `influx_twin_data: false`, the issue is the Ditto outgoing MQTT target and/or Telegraf to InfluxDB, not the continuous simulation logic. Preserve the volumes while diagnosing.

The state checkpoint is recovered on process restart by default. To start a truly **fresh mine**, keep a copy of the existing checkpoint first and explicitly clear just the `oreflow58_oreflow_state` volume, not the MongoDB or InfluxDB volumes.
