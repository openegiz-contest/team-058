# QA report — OreFlow KZ 2.1

## Verified in this build environment (2026-10-24)

- 40 tests passed: existing 33 engine/unit tests plus 7 reporting tests.
- V2 API smoke test passed (including arbitrary directed closure, fleet subsets and invalid-input rejection).
- Local HTTP smoke test passed. The outdated V1-specific expectation `15323 tonnes` was replaced with a duration/positive-output assertion because the V2 default is a 24-hour simulated run.
- Browser navigated all six pages with zero JavaScript exceptions and tested a configurable road closure.
- Browser acceptance also verified all 71 map markers, both 24-hour hourly charts, a CSV report download, and a 4-hour shovel outage; the requested scenario was actually processed and reported.
- Production aggregation equals the simulation's delivery total; class-delivery totals equal that same total.
- Model-estimated hourly fuel and activity time reconcile with run-level totals within rounding tolerance.
- All 20 shovel activities are aggregated from actual loading service records with matching original shovel names (not synthetic placeholders).
- Original source `north_pit_mine.json` binary hash matches OreFlow V2.
- JS syntax, Python compilation and Compose YAML parsing passed.

## Computation performance

- Default 24-hour MineRun executes locally in under 1 second in the sampled environment; complete application activation (run + matched comparison and normal baseline) finished in about 1.4 seconds in a browser test. Actual times vary with PC capacity and scenario.
- Calculations now run in an asynchronous HTTP job, keeping the last completed mine available until the new simulation finishes. Repeating an identical scenario can reuse the last completed result without storing an unbounded cache.
- The 30/90/180-second playback choices map to simulated minutes per real second correctly, rather than the old misleading 180× / 360× settings.

## Known limitations and honest boundaries

- The optimized policy is a transparent heuristic, not an ML model validated on real mine logs.
- Physical GPS, surveyed road grades, actual diesel burn, true shovel fuel, measured failure rates, mineral assay provenance and refinery outputs are not available for this fleet.
- Loading-site metrics count loading service, which can include incomplete end-of-day loads; the delivered-tonnage metric counts only finished unloads. They need not match.
- Browser PDF export invokes native Print / Save as PDF rather than a server-side PDF renderer. This is intentional and works offline in supported browsers.
- No live Docker daemon, physical MQTT broker, Ditto or InfluxDB was accessible during this development session. User must run on-host integration verifier after upgrading. No claim that these were tested here.
- Mine map uses OpenMines schematic site positions and directed distance matrices; it is not surveyed road geometry or satellite imagery.
