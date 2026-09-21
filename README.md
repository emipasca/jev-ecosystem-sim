# Ecosystem Island

A from-scratch ecosystem simulation: a procedurally generated grid island where
gazelle, lion and jackal agents perceive, decide and act each tick, and the food
web (grazing, ambush predation, scavenging, starvation, breeding) emerges from
individual decisions. Design spec: `DESIGN.md`.

Pure Python 3 stdlib — no third-party dependencies.

## Run

```bash
# headless: prints population dynamics over time
python3 run_headless.py --ticks 600 --seed 7 --every 25

# browser UI: play/pause/step, live map on a canvas
python3 run_server.py            # then open http://127.0.0.1:8000
python3 run_server.py --port 9000 --seed 42
```

(Any Python ≥ 3.10 works; a venv is fine but nothing needs installing:
`python3 -m venv .venv && source .venv/bin/activate` if you want one.)

## Layout

```
sim/
  config.py      all tunable constants (rates, terrain, bands, populations)
  noise.py       tiny value-noise / fbm implementation (no deps)
  world.py       grid island: terrain generation, vegetation, carcasses,
                 occupancy (one animal per cell), water distance field
  species.py     species trait tables (from DESIGN.md)
  animal.py      per-animal stored state + derived speed
  perception.py  banded plain-text state + legal action mask (what Jev sees)
  policy.py      Policy interface, MockPolicy heuristic, JevPolicy stub  <-- Jev goes here
  actions.py     goal-directed multi-tick resolution, movement, hunt odds
  engine.py      the tick loop: perceive -> decide -> resolve -> update
  server.py      stdlib HTTP server for the web UI
web/index.html   canvas renderer + controls (polls /api/state)
run_headless.py  CLI runner
run_server.py    web UI runner
```

## The policy boundary

The engine only ever calls:

```python
Policy.decide(perceived_state_text: str, available_actions: list[str]) -> str
```

`perceived_state_text` is the full banded plain-text state (hunger / thirst /
stamina / health / threat / prey / carcass / water / vegetation / mate /
current action + how long it has been running). `MockPolicy` is a readable
survival heuristic; `JevPolicy` in `sim/policy.py` is the drop-in stub for the
TypeSafe Jev API (see the TODO) — nothing else needs to change.

Per DESIGN.md, the policy never sees raw numbers, coordinates or outcome odds;
P(hunt success) is computed from the state matchup + terrain in
`sim/actions.py:hunt_success_prob` and rolled by the world.

## Notes

- Populations oscillate and differ by seed — that's the point. Typical arc:
  early predation dip, lions settle at 1-3 with kill-guarding, jackals ride the
  carrion economy, gazelles grow toward the vegetation-limited carrying
  capacity and then churn (boom / overgraze / starve).
- If gazelles boom past ~700 the tick rate drops (more agents); lower
  `VEG_REGROW_RATE` in `sim/config.py` to shrink the herbivore ceiling.
- Balance dials live in `sim/config.py`; the big ones are `METAB_SCALE`,
  `VEG_REGROW_RATE`, `CARCASS_*`, sprint/stamina costs and the band thresholds.
