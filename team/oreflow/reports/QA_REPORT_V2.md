# OreFlow KZ 2.0 — Quality and evidence report

Generated from actual execution of the **upgraded independent discrete-event simulator** (not field sensors).

## Verification results

- **33/33** simulation/unit tests passed; original 18 tests preserved and 15 new tests added (fuel accounting, class-specific tanks, refueling, directional road closures, specific shovels/trucks, fleet mixes, deterministic 24-hour replay, invalid-input rejection).
- **HTTP API smoke passed:** status/config/frame/overview/trips/fuel-events, two valid new activation payloads, playback/seek, and invalid policy rejection.
- **Browser interaction passed** in headless Chromium with local API bridged through Python (browser network restricted in this environment): 71 truck markers, eight scenario buttons, custom directed road, specific shovel, class-level fleet mix, fuel comparison, twin-card fallback; **zero page errors**. Screenshots: `ui_preview_v2.png`, `ui_whatif_v2.png`.
- **Static checks passed:** JavaScript syntax via `node --check`, shell launcher syntax via `bash -n`.
- **NOT VERIFIED HERE:** actual Docker start/restart, persistent MQTT→Ditto→InfluxDB→Grafana on the user's WSL host, and availability of optional Extended API. Run `python3 tools/verify-oreflow.py` on the host after upgrading. The browser's Ditto response was expectedly "not verified" without Docker credentials. No fabricated verification.

## 24-hour default mine, seed 42 (balanced dispatch)

| Measure | Simulation result |
|---|---:|
| Fleet | 71 trucks |
| Simulated duration | 1440 minutes (24h) |
| Delivered rock/ore as modeled | 103,066 tonnes |
| Completed haul deliveries | 2,132 |
| Diesel used (modeled) | 35,420.72 L |
| Litres per tonne | 0.3437 L/t |
| Refueling events started | 70 |
| Planned maintenance events | 71 |
| Total shift/maintenance downtime | 2,343.0 truck-minutes |
| Fuel shortfalls (seed 42) | 0.00 L |

Fuel pump locations, tank reference matches, flow rate, vehicle fuel burn, route grade, maintenance schedule, fuel price and road condition factors are **explicit modeled assumptions**; see `ASSUMPTIONS_V2.md`.

## Paired dispatch comparison, identical source, 11 seeds (21–31)

- Nearest-route rule vs selected smart dispatch (balanced objective): **93.10% mean improvement in simulated delivered tonnes** across 11 runs. Positive in **11/11** seeded comparisons.
- This is an internal simulator benchmark, **not** real mine savings, held-out field generalization, reinforcement-learning improvement or ML R²/F1. The nearest-route comparator is intentionally simple; improvements reflect both limitations of that baseline and the assumptions in our model.
- Fuel-saving dispatch may burn fewer litres/day mainly because it produces fewer tonnes. Always compare *litres per tonne*, production and total litres. No objective is claimed optimal under all conditions.

## Do not force a disruption to show a loss

The example L3→D5 closure increased delivered tonnes on seed 42. This can occur because prohibiting a congested lane forces a more productive flow under the current dispatch heuristic. It is **not evidence that closing a real road increases output**. Some shovel failures similarly have counterintuitive outputs. Preserve these results as diagnostics of the simulator, and scrutinize model validity instead of manipulating the numbers.

## Remaining realism gaps

- No real journey, GPS, fuel tank identification, ore assay, driver shift log, road elevation or fuel telemetry.
- Truck failures and maintenance are event-boundary operations, not dynamic mechanical reliability estimates.
- Refueling is implemented at *hypothetical* loading-site pumps. Real route geometry and grades remain unknown.
- Crusher physics, ore-waste segregation, blending and mill recovery are not linked to measured geological datasets.
- Need an actual WSL+Docker acceptance run and full live service connectivity before treating this ZIP as deployment-verified.

Reproduction: `python3 -m unittest discover -s team/oreflow/tests -v`, `python3 tools/test-v2-api.py`, `node --check team/oreflow/static/app.js`. Full numerical data: `benchmark_v2_24h.json` and `.csv`.
