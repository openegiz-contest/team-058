# OreFlow 2.3 — Competition Edition upgrade

## What changed compared with V2.2

| Component | Actual change | Evidence |
|---|---|---|
| Mine model | Added two fuel-station and 55 directed-road Ditto twins (102 → **159**) | `setup_twins.py`, new tests |
| Twin telemetry | Fuel station state, pump count/queues, road closures/degradation, shovel availability from simulation events sent via MQTT | `server.py`, `MineRun.asset_states()` |
| Spatial visualization | Real HTML/SVG mine map from original schematic coordinates; 71 selectable truck markers, loading/dump sites, fuel stations | `static/app.js` |
| Recovery | Three isolated branches: normal, disrupted, and disruption with tested dispatch policy | `continuous.py`, scenario API |
| Congestion | Optional site-specific **future** load-dispatch exclusion, tested from current state | `ContinuousMine._evaluate`, `apply_site_relief` |
| UX | Five pages, graphs, in-place equipment details, fuel & road tabs, platform readback on selection | `static/` |
| Reliability | No full legacy comparisons at server startup; road messages sent on changes, upgrade script initializes new twins | `server.py`, scripts |

## Do not misrepresent the simulation

- Coordinates are a schematic projection of OpenMines loading/dump nodes, not measured GPS. Vehicle motion is calculated from source road lengths, modeled loads and queues.
- Manufacturer-class fuel tank capacities and rates are **assumptions/reference proxies**, not verified actual models in the mine.
- Only *new* assignments can avoid an overloaded loading site; trucks already reserved at a shovel are **not** forcibly rebooked. No L→L intersite road exists in the source graph.
- Queue-relief is offered only if a direct, deterministic branch shows sufficient improvement; it can be rejected when no gain is found.
- What-If changes are **isolated forecasts**. Testing does not introduce an outage into the operating mine. An optional confirmed recovery action can change supported future dispatch rules only.
- Fuel-station reported cumulative dispensed litres currently reflects retained in-memory fuel events (up to the recent history kept by checkpoint archiving). It is not a lifetime counter after long simulation archiving.
- Performance gains against nearest-route are **simulator-specific**; compare queue-aware as a credible baseline too.

## Requirements for an actual competition submission

1. Test **fresh** on clean Docker Ubuntu using `bash scripts/oreflow-start.sh`; verify no manual intervention and capture logs.
2. Run `python3 tools/verify-oreflow.py` and confirm all flags, including **fuel-station and road Ditto readbacks** and `influx_twin_data`.
3. Open all five pages in a real browser; test a shovel failure and a road closure, inspect their side-by-side affected-equipment maps and confirm recoveries come from actual simulation branches.
4. Check that `SUBMISSION.md` begins with the team-authored **Concept**, and include `README.md`, `SUBMISSION.md`, `presentation.pdf` on the team repository's `main` branch.
5. Do not claim the release is field-calibrated or complete until these checks pass.
