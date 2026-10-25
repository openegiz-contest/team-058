# OreFlow KZ 2.0 — Assumption register and provenance

**Original file remains unchanged:** `team/oreflow/data/north_pit_mine.json`. Source: OpenMines `north_pit_mine.json` (MIT-licensed repository `370025263/openmines`). The North Pit example is an anonymized mining configuration, not an industrial time-series dataset.

| Parameter | Value used | Provenance / confidence |
|---|---:|---|
| Fleet (77t, 35t, 55t) | 9, 29, 33 | OpenMines source-configured |
| Nominal truck speed | 25 km/h each | OpenMines source-configured |
| Shovels | 20 across 5 loading sites | OpenMines source-configured |
| Loading shovel bucket/cycle | Per original JSON | OpenMines source-configured |
| Dumping unit counts/cycles | Per original JSON | OpenMines source-configured |
| Directed haulage road lengths | 25 loaded + 25 return segments | OpenMines source-configured |
| Tank for 35t class | 456 L | Reference class: Komatsu HD325-8; actual CLTruck model not identified |
| Tank for 55t class | 800 L | Reference class: Komatsu HD465-8; actual XHTruck model not identified |
| Tank for 77t class | 650 L | Reference class: XCMG XDR80T (72t proxy); actual OfficalTruck model not identified |
| Loaded L/km (35/55/77t) | 1.35 / 2.00 / 2.65 | **Unvalidated engineering assumptions** |
| Empty L/km (35/55/77t) | 0.90 / 1.20 / 1.65 | **Unvalidated engineering assumptions** |
| Idle L/h (35/55/77t) | 7 / 10 / 13 | **Unvalidated engineering assumptions** |
| Loaded speed multiplier | 0.85 × nominal | Simulation assumption, not real speed observation |
| Empty speed multiplier | 1.08 × nominal | Simulation assumption, not real speed observation |
| Route gradients | Deterministic -3..+3% | **Illustrative slope proxy**, no DEM or surveyed elevations |
| Grade fuel sensitivity | +3.8% L/km per 1% uphill | Bounded heuristic assumption, NOT verified physics |
| Poor road condition | +60% modeled time/fuel | Disruption assumption, NOT measured |
| Stations | 2 sites (L1, L4), 2 pumps each | Hypothetical facility placement; NOT in OpenMines |
| Pump rate | 45 L/min per pump | Hypothetical, not station measurements |
| Fuel reserve | 25% tank minimum threshold | Explicit operational rule; not a universal mine standard |
| Shift relief | 15 min at next safe event after hour 12 | Simplified 2-shift model |
| Scheduled maintenance | 18 min once/day per truck (staggered) | Simplified proactive maintenance model |
| Fuel price | 350 ₸/L default | Illustrative user-adjustable cost assumption; not a verified current retail or mine-contract price |
| Travel jitter | deterministic ±4% | Simulation variation, not sensor noise |

**What the simulator does:** calculate truck events, empty and loaded travel, queues, loading/unloading, fuel bookkeeping, preventive repairs and configurable disruptions with reproducible seeds. It publishes hypothetical truck attributes through the real Eclipse Ditto MQTT channel, where twins can be read back. It never claims actual mine deliveries, measured fuel or observed equipment failures.

**Important physical/model limitations:** Each route is a directed segment, not detailed turn-by-turn geometry. Existing routes may be long; slope proxies are *not derived* from the schematic x/y map. A fault starts at the next safe discrete-event boundary for moving trucks. Previously started operations may finish. Material is labeled generic hauled rock/ore; no proven geological grade, crusher throughput physics, blending or processing recovery. Fuel is estimated from class rates instead of engine load curves. Fleet comparisons are synthetic.

**Quality protocol:** Compare dispatch strategies with *identical seed, equipment, event assumptions and duration*. Compare disruptions against a normal run with the same strategy and seed. Check litres/tonne and tonnes/day together—lower total litres by producing fewer tonnes is not a win. Repeat tests across multiple independent deterministic seeds and disclose counterintuitive scenario results instead of forcing a positive benefit.
