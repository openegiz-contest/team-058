# OreFlow 2.3 — Verification report

## Verified in local authoring environment (no Docker)

- **59/59 engine and report unit tests passed** after V2.3 final modifications with `python3 -m unittest discover -s team/oreflow/tests -v`; full suite output was captured and checked before packaging.
- `setup_twins.definitions()`: **159 unique Eclipse Ditto thing definitions**, including original 102, two fuel stations, 55 directed roads.
- Local API `/api/v22/assets`: 20 shovel states, 2 fuel station states, 55 roads, all derived from the same simulation event engine.
- A private road-closure What-If was calculated from a saved 71-truck operating state and included three branch outcomes and two common-time spatial snapshots, with differences observed on 13 truck states/assignments in the test case. The live mine state was unchanged by the evaluation.
- Headless Chromium rendered the actual HTML/CSS/JS frontend using captured results from the **executed local Python API** (browser network was blocked by administrator policy): 71 markers, five page navigation flows, 9 policy-comparison bars, 3 scenario outcomes, 2 scenario maps, fuel stations (2) and roads (55), with **zero JavaScript errors**. This is an intercepted fixture browser test, **not** a live Docker/browser end-to-end test.
- `node --check` JavaScript syntax and `bash -n` launcher syntax passed.

## Not verified in this environment

- No Docker executable/daemon is available: **fresh Ubuntu Docker startup and the actual MQTT → Ditto → InfluxDB → Grafana pipeline were not executed**.
- Changes must be tested on the recipient's Docker host. The strict `tools/verify-oreflow.py` exits non-zero if source twin readback or historical Influx evidence is missing.
- Real equipment fuel telemetry, GPS traces, measured ore grade, measured failures and published costs were not available. Simulation parameters must not be relabeled as measured observations.

## Key interfaces

- `/api/v22/now`, `/api/v22/assets`, `/api/v22/reports`, `/api/v22/evaluate`, `/api/v22/job`
- `/api/v23/queue-relief` (confirmed tested-action only), `/api/ditto/{thing}` (physical platform readback)
- Scenario evaluation *never* invokes `/api/v22/incident`.

## Acceptance concerns remaining

- Evaluate multiple seeds and realistic congestion conditions. The deterministic optimizer cannot guarantee superiority over a physical mine or better alternatives.
- Retained station fuel events should not be presented as an all-time dispensed fuel total after in-memory history compaction.
- The source project does not automatically push commits to the competition's private Team 058 repository.
