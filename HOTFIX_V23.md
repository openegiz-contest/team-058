# OreFlow V2.3 — Stability and Data Export Fix

This is a full project archive; replaces the previous V2.3 source without erasing the OpenEgiz Docker volumes.

## Important: what is real data?

- **Source** exports contain source configuration values from OpenMines North Pit: truck capacity and nominal speed, shovel bucket/cycle specs, directed road distances. These are configuration values, not truck telemetry or GPS.
- **Simulated** exports contain OreFlow-generated hourly aggregates, trip completions, refueling activity, truck activity intervals and shovel loading activity. None are measured by real physical vehicles.
- Recent event CSVs cover the last 24 simulated hours. Older detailed intervals are compacted to bounded history; completed day summaries are saved separately.

## Bugs fixed

- Compatible with older trusted saved MineRun checkpoints missing `restricted_load_site` and `restricted_until`. Fixes the What-If exception.
- What-If calculation failures are shown persistently in the result panel. No changes to the live mine from evaluating a scenario.
- Pause and resume from Operations with clear confirmation.
- Explicit **Start fresh mine** resets trucks, times, queues and simulated history to Day 1; archives the old checkpoint and daily JSON reports in the same Docker volume. No source data is altered. Refreshing the browser **does not reset the simulation**.
- CSV export selector separates source configuration CSVs from modeled operating results, with named columns and `record_origin`.

## Recommended first installation for a genuinely fresh simulated run

Run from this project's root after copying `deploy/compose/.env` from the previous working installation:

```bash
COMPOSE_PROJECT_NAME=oreflow58 bash scripts/oreflow-upgrade-fresh.sh
python3 tools/verify-oreflow.py
```

Use `scripts/oreflow-upgrade-running.sh` for *subsequent upgrades* when you want the mine to resume its saved simulation instead. To reset manually, press **Start fresh mine** on Operations and confirm twice.

The source configuration remains unchanged. The Docker host is the required final integration test for Eclipse Ditto, MQTT, Telegraf, InfluxDB and Grafana; a source-code hotfix does not certify those connections.

## Tests

```bash
python3 -m unittest -v team/oreflow/tests/test_hotfix_v23.py
node --check team/oreflow/static/app.js
bash -n scripts/oreflow-upgrade-fresh.sh
```
