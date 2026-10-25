# OreFlow 2.2 quality and evidence

## Tested, not asserted

- 33 original engine tests passed (separately executed).
- 7 V2.1 reporting tests passed (separately executed).
- 15 new continuous-operation tests passed (separately executed).
- 7 simulated days, checked direct advancement vs many 30-minute steps: matched delivery tonnes and fuel exactly.
- 7 simulated days, no recorded model fuel shortfalls in checked seed 47 (this is NOT field validation).
- Archive compaction kept cumulative delivered tonnes, delivered trips, modeled fuel and the most recent daily report unchanged.
- Checkpoint save/reload preserved simulation time, run ID, event queue and production.
- Local HTTP API checked via real requests: current frame, configuration, reports, pause/resume, policy updates, advisory job, scenario job.
- HTML element references statically verified; JavaScript passed `node --check`; Python passed `py_compile`; Shell launcher passed `bash -n`; Compose overlay parsed as YAML.

## Not verified in this environment

- The runtime browser prohibits local HTTP navigation by administrative policy; the new CSS and controls therefore **did not** receive a live screenshot/browser-automation pass. An earlier V2.1 browser test is not evidence for V2.2.
- No Docker daemon is available in the creation environment; a real MQTT/DITTO/InfluxDB integration test must be completed on the target machine.
- There is no field telemetry to validate assumed rates, incident probabilities, fleet optimization gains or road/terrain proxies.

## Acceptance criteria for the user's PC

1. Installation starts without manually rebuilding the optional Extended API.
2. Every browser page renders; no JavaScript console errors.
3. Start / pause / resume and speed changes work. Time continues after closing Chrome, pauses when requested, and resumes from the checkpoint after a Docker restart.
4. After one simulated day, an automatically saved daily report appears; CSV exports are downloadable.
5. A scenario gives side-by-side actual simulated metrics; the user's live mine is unchanged until they press Apply.
6. Queue-aware dispatch sometimes wins or is recommended if it produces an eligible lower modeled fuel/tonne; no algorithm is permanently declared the winner.
7. Ditto readback matches run ID and has recent timestamps; InfluxDB verification returns `true` for actual new telemetry.

## Safeguards

Simulation time differs from wall time. A policy change applies to future dispatch events, not trucks mid-road. Cumulative fuel and tonnes are kept after event archiving. Historical reports are computed from events, and raw technical data remains available in the platform (when connected).
