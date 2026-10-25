# OreFlow KZ 2.3 — Team 058 | OpenEgiz Digital Mine

**North Pit: a decision-first, open-pit haulage digital twin.** This solution represents trucks, shovels, sites, fuel stations and roads using Eclipse Ditto and a continuous discrete-event simulator. It lets dispatchers observe connected equipment, compare dispatch policies, and run isolated, reversible What-If calculations.

> **Data integrity:** OpenMines contributes an anonymized mine *configuration*; trips, diesel usage, truck movements, downtime, production and what-if effects are **simulated, not measured on a physical mine**. The map is a schematic based on model coordinates, not surveyed GPS.

## 1. Clean installation / automated judge startup

Target: **Ubuntu 24.04 amd64, Docker Engine + Compose v2**, 8 vCPU/16 GiB RAM. No preexisting volumes, passwords, cloud tokens, WSL or manual configuration are required. Run from the checked-out **repository root**:

```bash
bash scripts/oreflow-start.sh
bash scripts/oreflow-verify-ready.sh
```

The startup script creates `deploy/compose/.env` locally with random credentials (git-ignored), starts MongoDB, MQTT, the five Eclipse Ditto services, InfluxDB, Grafana and Telegraf, registers policy/MQTT connections and **159 OreFlow twins**, builds the team container and runs the mine. It intentionally avoids the optional upstream Extended API Git build with an unavailable pinned reference. The readiness script polls the **real** strict integration verifier for at most eight minutes and exits nonzero if connectivity is still incomplete. Startup depends on publicly available Docker image registries.

**Open on the judge VM:**
- **OreFlow (main interface):** http://localhost:8099
- **Grafana history dashboard:** http://localhost:3000/d/oreflow-northpit
- **Ditto service:** http://localhost:8080

Expected `tools/verify-oreflow.py` checks include fleet size, simulation clock, live MQTT, same-run Ditto readback, fuel and road twin state, Grafana, and telemetry history in InfluxDB. **Do not confuse a successful static Python test with a successful live-platform test.**

If investigating a start failure:

```bash
docker compose -p oreflow58 --env-file deploy/compose/.env \
  -f deploy/compose/docker-compose.yml -f team/oreflow/compose.yml ps
python3 tools/verify-oreflow.py
```

Do not `docker compose down -v` unless intentionally destroying all data; it is **not** a startup step.

## 2. How to demonstrate the project (5–8 minutes)

1. Visit http://localhost:8099. **Operations** shows all 71 modeled trucks, five loading sites, five dump sites, 20 shovels, two fuel stations, roads, queue counts and current production. Inspect equipment on the map without leaving the page. The labels `SIMULATED MINE` and schematic-geometry notes distinguish modeled operations from measured telemetry.
2. Click **Fleet & Equipment**. Open Truck `t001`, Fuel Station `L0` or a road; inspect state, modeled fuel and equipment metadata. Use the **Ditto readback** to check the platform-stored state. The live API `/api/ditto/t001`, `/api/ditto/fuel-l0`, and `/api/ditto/road-l0-d0` return current readback metadata including run-ID matching.
3. In **Recommendations**, inspect current queues and compare **Nearest**, **Queue-Aware** and **OreFlow** policies on the same starting state/seed; compare delivered tonnes, waiting and modeled fuel. Recommendations are estimated trials and may show no benefit. A queue-relief action can constrain **future** assignments, not teleport trucks already queued or travelling.
4. In **Scenarios** (What-If), choose **Shovel stops** or **Road closes**, select the affected asset, period and comparison horizon, then **Calculate impact**. Wait for the computed **Normal / Disrupted / Recovery** comparison, delivery curves and model-derived equipment snapshots. No incident is applied to the running mine by this button.
5. In **Reports**, inspect simulated production, equipment workload, station activity and CSV exports. CSVs distinguish source-configured values from synthetic operational records and explicitly label their columns and origin.

**Undo / revert What-If:** scenario calculations are isolated forecasts. Close the result or choose another scenario to return to the unchanged live Operations view. No destructive "apply outage" step is needed. For a deliberate new simulated run, choose **Start fresh mine** on Operations; it archives previous simulated history and restarts at Day 1. Browser refresh and Pause/Resume do **not** reset the mine.

## 3. Architecture & project code

```text
OpenMines North Pit JSON -> OreFlow event engine -> MQTT -> Eclipse Ditto
                                                     |      |
                                                     |      +--> /api/ditto/* asset readback
                                                     +--> Telegraf -> InfluxDB -> Grafana
OreFlow continuous API -> spatial interface, policy trials, private What-If branches, CSV
```

The simulator publishes modeled equipment attributes using the OpenEgiz MQTT/Ditto pathway. The interface also uses simulator-derived API views for continuous map animation and What-If previews, and exposes explicit Ditto readback; **not every on-screen map pixel is fetched individually from Ditto**. This hybrid architecture is a known limitation, not a claim of direct physical GPS streaming.

- `team/oreflow/engine.py` — source-configured, capacity/queue/fuel-constrained mine model and scenario computation.
- `team/oreflow/continuous.py` — persisted ongoing mine, reports, recommendations and simulation clock.
- `team/oreflow/server.py` — telemetry publisher, Ditto readback, evaluation jobs, controls and export routes.
- `team/oreflow/setup_twins.py` — declares **159 twins** (1 mine, 71 trucks, 20 shovels, 5 loads, 5 dumps, 2 fuel stations and 55 directed road connections).
- `team/oreflow/static/` — five-page visual UI, including enhanced road/queue/failure views and three-way scenario charts.
- `team/oreflow/data/north_pit_mine.json` — original source configuration, unchanged.
- `team/oreflow/reports/ASSUMPTIONS_V2.md` — detailed model and measurement assumptions.
- `SUBMISSION.md` — concept, module/scenario explanations, data provenance and limitations.
- `presentation.pdf` — visual presentation and on-stand demonstration.

## 4. Non-Docker checks

```bash
python3 -m unittest discover -s team/oreflow/tests -q
python3 -m compileall -q team/oreflow
node --check team/oreflow/static/app.js  # if Node.js is installed
bash -n scripts/oreflow-start.sh scripts/oreflow-verify-ready.sh
```

The full unit suite includes some computationally intensive multi-day simulations; it is not required before launching the platform. Local/browser-fixture checks and user-reported live-platform diagnostics are described in [`SUBMISSION.md`](SUBMISSION.md). **A completely clean judge-environment build has not been independently reproduced by this package author.**

## 5. Provenance, licenses, limitations

- Original anonymized North Pit configuration: [OpenMines](https://github.com/370025263/openmines), MIT; local copy `team/oreflow/OPENMINES_LICENSE`.
- OpenEgiz template and its vendored components preserve their own notices/licenses; see `LICENSE`, `NOTICE`, `LICENSES/`.
- Team-authored OreFlow changes are submitted on MIT terms as required by the contest. No personal/corporate private data is supplied.
- Fuel tank classes are proxy reference values; liters/km, fuel pumps, price, shifts, maintenance, road grades and failure schedules are **assumptions**, not field measurements. The source provides **no live truck GPS or authenticated industrial sensors**.
- Recovery proposals are **simulation decisions**, not validated real-mine optimization. Disruptions can produce zero or counterintuitive positive modeled production; results are not clamped to predetermined wins.
- The scenario spatial comparison includes normal/disrupted states; the recovery case has a calculated production curve, but does **not** invent an unavailable recovery-position snapshot.

For existing local installations, use `scripts/oreflow-upgrade-running.sh` to retain simulator checkpoints. A fresh local run is different: `scripts/oreflow-upgrade-fresh.sh`. **Neither upgrade command is required for judge startup.**

Official contest rules: https://openegiz-contest.github.io/kk/rules/ ; judge VM: https://openegiz-contest.github.io/ru/environment/
