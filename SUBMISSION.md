# Concept — OreFlow KZ / North Pit Decision Twin

**Enterprise / scope.** OreFlow KZ represents the **haulage and loading operation of a North Pit-inspired open-pit mine**. It is a source-configured *virtual* operation based on an anonymized configuration from the open-source OpenMines project, not a monitored commercial mine. Its emphasis is the operational relationship among dispatching, shovel capacity, road availability, fuel access and achievable deliveries.

**Who uses it.** Mine dispatchers, shift supervisors and equipment planners who need to understand why trucks wait, whether equipment failure will impact deliveries, and which feasible assignment policy to test next.

**Decision it helps make.** **Where should each available truck be sent, and what should the dispatcher change after a road or shovel failure?** Operators can compare alternatives from a common starting state, inspect queue and fuel trade-offs, and run isolated disruption/recovery forecasts.

**Why this concept.** A moving truck map alone would not justify a digital twin. The value comes from equipment-linked process states, constraints and observable consequences of decisions. The existing OpenMines North Pit parameters give a transparent fleet and road configuration; Eclipse Ditto provides persisted, queryable twins rather than an animation with no platform identity. We deliberately focus on depth of haulage behavior instead of claiming unimplemented geology, blasting or processing modules.

## Team

- **Team 058, OreFlow KZ** — Zhenisbek Umaraliev (sole project contributor as currently reported).
- **Registered GitHub login:** `jenisbekk`.
- Competition repository: `https://github.com/openegiz-contest/team-058` (submit on **main**, not via this ZIP alone).

## Implemented mine / what is original

**Team implementation:** a continuous, event-driven North Pit simulation and monitoring/control center, source-aware truck class capacities, loading/unloading resource constraints, site queues, modeled diesel, fuel stations, scheduled maintenance, equipment state histories, policy comparisons, isolated what-if calculations, exportable operation records, a five-page spatial UI and scenario visualization.

**OpenEgiz platform:** Docker-hosted Eclipse Ditto things, policies, MQTT connectivity, Telegraf, InfluxDB, Grafana and original template components. The sample mine/template does not count as team-authored work. OreFlow extends the platform with its own distinct equipment graph and behavior.

**Eclipse Ditto model:** **159 defined things** in namespace `org.openegiz.oreflow`: 1 mine; 71 trucks (9 of 77 t, 29 of 35 t, 33 of 55 t); 20 shovels; 5 loading sites; 5 dumping sites; 2 fuel stations; and 55 directed road connections. Mine states and asset updates are published over MQTT and observable using the API's Ditto readback. Road topology is source-configured and drawn schematically, not real GIS routing.

**End-to-end path:** OreFlow engine → MQTT → Ditto persisted twins; Ditto events → Telegraf → InfluxDB → Grafana. The OreFlow API also serves simulation-derived map frames and hypothetical branch snapshots. An operator can verify the current run with `/api/ditto/mine-01`, `/api/ditto/t001`, `/api/ditto/fuel-l0` and `/api/ditto/road-l0-d0`.

## Working modules and how to see them

| Module | Implemented operation | On-stand demonstration |
|---|---|---|
| **Haulage / dispatch** | Truck loading, loaded/empty travel, dump service, queues and Nearest/Queue-Aware/OreFlow assignments | `http://localhost:8099` → **Operations** and **Recommendations** |
| **Equipment monitoring and maintenance** | Per-truck states, shovel availability, preventive maintenance/shift relief, downtime and refueling | **Fleet & Equipment** → select truck, shovel or station |
| **Fuel/energy planning (modeled)** | Tank and consumption estimates, two fuel stations, station queues, fuel histories, litres-per-tonne metrics | **Operations** → fuel stations; **Reports** → modeled fuel |
| **Decision support / custom module** | Compare dispatch policies, queue-relief alternatives and trade-offs via repeated deterministic simulation | **Recommendations** → analyze congestion and compare policies |
| **Reports and evidence** | Hourly/daily production, truck events, shovel work, fuel, source-configuration/operation CSVs | **Reports** → choose labeled CSV export |

Modules describe functions **as implemented**, not certification of real mine operations. The scenario interface can report no benefit when no tested policy helps.

## What-If scenarios, demonstration and undo

All scenarios in **Scenarios** are simulated in isolated branches; clicking **Calculate impact** does not alter the running mine. The comparison uses the same modeled starting conditions to calculate **Normal / Disrupted / Recovery** outcomes and presents delivery, waiting and fuel comparisons. UI scenario options include:

| Scenario | Modeled consequences | How to demonstrate | How to undo |
|---|---|---|---|
| Shovel stops | The selected shovel becomes unavailable; queues/service/assignments and tonnes may change | **Scenarios** → **Shovel stops** → choose shovel/time/horizon → **Calculate impact** | Exit or rerun another scenario; live run never changed |
| Road closes | New truck departures on the selected directed connection are restricted during the modeled outage | **Scenarios** → **Road closes** → select road → calculate; inspect road/map and deliveries | Exit or rerun; no live road closure applied |
| Fuel station unavailable | Refueling availability and queue may change if the station would be used during the interval | **Scenarios** → **Fuel station** → choose L0/L3 → calculate | Exit or rerun; live station remains unchanged |
| Truck failure/reduced fleet | Fewer available modeled trucks; potential throughput and queue effects | **Scenarios** → **Truck failure** → calculate | Exit or rerun; no truck disabled live |
| Dump unavailable / road condition | Model-specific destination restriction or slower roads | **Scenarios** → choose corresponding card → calculate | Exit or rerun; no persistent incident |

**Evidence boundary:** Road/shovel outcome calculations and scenario UI flows have been locally exercised. Some scenario combinations may have zero effect or unexpectedly increase modeled output due to rerouting or queue redistribution; not every control configuration has been individually live-verified. Recovery **production** curves are computed; there is no invented third recovery-position map where that API field is absent.

## Where to see visualization

Open **http://localhost:8099**. The spatial view draws model-defined loading/dumping sites, moving truck symbols, shovel identifiers, two fuel points, directed road lines, queue counts, failed-equipment indicators and incident markers. Click an asset for in-place detail rather than navigating away. **Scenarios** provides normal vs disruption map snapshots and three curves; **Reports** houses numerical charts. The visualization uses geometry inferred for a schematic display, not surveyed geographic positions. Screenshots in `presentation.pdf` come from the implemented browser client driven by recorded simulator API responses, not real mine cameras.

## Data and assumptions / licenses

**Source-configured data:** `team/oreflow/data/north_pit_mine.json` from [OpenMines](https://github.com/370025263/openmines), under MIT license (copy in `team/oreflow/OPENMINES_LICENSE`). It supplies truck class counts, rated capacity/speeds, shovels, loading/unloading sites and directed distance matrix. **It is not real-time telemetry and does not identify a survey-verified mine layout.**

**Synthetic data:** generated truck trips, locations along schematic routes, queue minutes, shipment/production totals, diesel usage, downtime, refueling, failures and all What-If/recovery outcomes. Modeled tank capacities are equipment-class proxies; rates, slope factors, fuel pumps, maintenance, fuel price and failure processes are documented assumptions in [`team/oreflow/reports/ASSUMPTIONS_V2.md`](team/oreflow/reports/ASSUMPTIONS_V2.md). No physical sensors or ore-grade assays are connected. CSV exports carry source/simulation provenance labels.

**License compatibility:** Team-authored changes are offered under MIT terms. The original OpenEgiz template preserves its `LICENSE`, `NOTICE`, `LICENSES/` files and bundled third-party conditions. OpenMines source is MIT-licensed. No proprietary dataset or user login is included.

## Tests, reproducibility and limitations

**Static/local evidence**: Authoring-environment testing covered engine and report suites, scenario isolation, twin schema cardinality, CSV schemas, server API trials, browser-fixture rendering and JS checks. After the stabilization hotfix, targeted release tests passed. These are distinct from a clean Ubuntu judge build.

**User machine evidence**: The project owner ran the Docker stack and shared diagnostics where MQTT, Ditto basic readback, 71-truck model, fuel readback, Grafana and InfluxDB history succeeded. Follow-up live readbacks showed **the same run-ID** for `mine-01`, truck `t001`, two fuel stations and a road; the setup container log showed **159 registered twins**. The owner subsequently said a rerun of the full verifier was done, but **did not supply the final 16-check output in this conversation**. A fresh zero-volume Ubuntu 24.04 build is not independently confirmed here. The actual verification command is `bash scripts/oreflow-verify-ready.sh`.

**Important limits:** This is a discrete-event approximation, not validated plant physics. Different policies may trade throughput for fuel; no policy is guaranteed optimal or better in a real mine. Road grades/coordinates are schematic. Some UI elements are served by simulator-derived API snapshots, while the equipment inspector verifies persisted Ditto twins; **the entire live map is not driven exclusively by Ditto reads**. Fuel/maintenance data are modeled, not field-measured. What-If scenarios are *isolated counterfactual calculations*, not destructive updates of active twins.

## Submission files

- `README.md` — clean VM launch and reproducible demo instructions.
- `SUBMISSION.md` — this concept-first disclosure, module/scenario procedures, provenance and limits.
- `presentation.pdf` — visual overview plus on-stand demonstration and source limitations.

Deadline: **25 October 2026 at 23:59 Astana time (UTC+5)**. Only content committed to Team 058's **main** branch at freeze counts. Contest rules: https://openegiz-contest.github.io/kk/rules/
