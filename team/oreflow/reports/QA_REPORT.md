# OreFlow KZ — Team 058: verification and evidence report

**Build basis:** Untouched `team-058-main(3).zip` OpenEgiz scaffold plus independently authored `team/oreflow/`. No legacy OreFlow project ZIP, design or tests were used as a source.

**Evidence source:** Official OpenMines North Pit JSON (MIT), SHA-256 `a966a72a6bfa91a86bcd6c3cdcccd9df5d4e83cdb36217a4ac4505ee77c0f16c`.

## Executed checks (authoring environment)

| Check | Actual result | Meaning |
|---|---|---|
| Source/config counts | PASS | 71 trucks; 3 types 9+29+33; 20 shovels; 5 load + 5 dump |
| Engine unit tests | **18/18 PASS** | Unique trucks, no overlapping state segments, mass conservation, capacity and road constraints, deterministic seeds, scenarios and rollback |
| Python compilation | PASS | Engine, API and Ditto setup modules compile |
| Website JavaScript | PASS | `node --check` reports no syntax errors |
| Shell syntax | PASS | `scripts/oreflow-start.sh` |
| Docker Compose static YAML | PASS | Both base and OreFlow overlay parse |
| Grafana JSON | PASS | UID `oreflow-northpit`, 3 panels with numeric Influx Flux queries |
| HTTP integration smoke checks | **13/13 PASS** | HTML/CSS/JS, frame, config, comparison, seed benchmark, scenario activation, clock control, active trip export API, invalid policy rejection |
| Browser UI interaction | PASS (network proxy limitation) | Browser rendering and client-side clicks: 71 markers, equipment inspector, dispatch comparison, 11-seed benchmark, shovel outage, platform status and evidence page |
| Simulation run seed 42 | PASS / measured within simulator | Closest 10,049 t; queue aware 14,781 t; optimizer 15,323 t |
| Held-out seed experiment | PASS / measured within simulator | 11 seeds 21–31, normal mean paired production change +52.46%; optimizer beats closest in 11/11 |
| PDF presentation rendering | PASS | 10 pages generated from benchmark and actual UI preview, inspected as rendered PNG |

### No claims of the following tests being passed

- **Actual Docker build and clean Ubuntu judge VM startup:** not executed here; no Docker daemon is available in the authoring environment.
- **MQTT broker handshake and 102 persisted Ditto twins:** integration code is present but must run in user's OpenEgiz stack.
- **InfluxDB persistence and real Grafana Flux results:** not independently verified against a running stack.
- **Real physical machine measurements or prediction accuracy:** there are no real truck telemetry targets; engine produces simulator data, and the optimizer is a heuristic policy, not a trained ML model.

Do **not** report the end-to-end platform as verified until `python3 tools/verify-oreflow.py` returns exit code 0 on a running Docker host. That tool checks broker status, Ditto real HTTP readback, active run ID and actual Influx records. Grafana's HTTP readiness does not prove every individual panel query; visually check the provisioned dashboard as the final confirmation.

## Policy selection and holdout discipline

The policy grid was explored on seeds 11–14 and checked on 15–18. The resulting weights are fixed in `engine.py`: `dump=0.05`, `queue=0.8`, `site=-0.2`. Seeds 21–31 were reserved for the final comparative evaluation. This is heuristic simulation tuning, not a train/validation/test split of real labeled mining telemetry.

Source road distances are directed; the website displays a topological schematic rather than geographically calibrated road polylines. Individual queue duration is based on equipment availability, not a randomized cosmetic dashboard.

## Holdout summary (simulation only)

| Scenario | Mean production change vs closest | Better runs |
|---|---:|---:|
| Normal | +52.46% | 11/11 |
| Shovel outage | +77.67% | 11/11 |
| Road closure | +76.17% | 11/11 |
| Fleet reduction to 50 | +45.30% | 11/11 |

For full per-seed values and generated trip histories see `benchmark.json`, `benchmark.csv` and `sample_haul_trips.csv`.

## Limitations affecting physical realism

- Event simulation is independently authored; it does **not** execute the native OpenMines runtime.
- Simplified travel times use original road lengths and speed multiplied by seeded variation (±4%). No measured speed profile, slope, rainfall, fuel or tyre wear.
- Shovel dispatch uses a site-level availability schedule. Downtime stops one specified service device; no emergency partial-load recovery.
- A road closure blocks *new entry to that link* during its window, not a physically complex reroute for vehicles already travelling.
- Queue observation at the 240-minute horizon is right-censored and described accordingly.
- Results are strong relative to a deliberately simple closest-route baseline; a mine-specific production optimizer might outperform our policy.

### Next required verification to qualify as a fully proven connected digital twin

```bash
bash scripts/oreflow-start.sh
python3 tools/verify-oreflow.py
```

Check browser UI at `http://localhost:8099` and Grafana at `http://localhost:3000/d/oreflow-northpit`. Confirm that changing and resetting a scenario creates a new run and is reflected in Ditto's run identifier and timestamped Influx records.
