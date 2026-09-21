# Ecosystem Simulation (Jev agents)

A 2D grid-island ecosystem where every animal is an autonomous agent and the food chain
*emerges* from individual decisions rather than being scripted. Each animal's choices are made
by [Jev](https://typesafe.ai) (TypeSafe's "System One" model), which returns a typed decision
with calibrated probabilities from a plain-text description of what the animal perceives.

Predators hunt, prey flee and forage, populations rise and crash, and the whole web looks for a
balance on its own. Pure Python standard library, no dependencies.

## The idea

- **The world is a high-def grid island** (procedural coastline, surrounded by infinite sea) with
  seven terrain types (beach, grassland, brush, forest, rocky highland, marsh, water) that change
  movement, vision and hunt odds. Vegetation is procedurally clustered and regrows.
- **Animals are agents.** Gazelle (prey), lion (apex predator), jackal (scavenger). Each has body
  traits (size, exertion, vision), resources that change at different rates (energy, stamina,
  health, hydration) and drives (hunger, fear). Speed is derived each tick, never stored.
- **Decisions come from Jev.** Each tick an animal's state is rendered into coarse plain-text
  bands (`hunger: starving`, `threat: predator closing`, `nearest prey: in range`, ...) and the
  legal actions become a Choice question. Jev returns the action plus a probability per option.
  **Jev never sees the raw numbers or the success odds** — it decides on instinct from perception,
  and whether that instinct was good shows up in whether the animal survives.
- **Actions are goal-directed and multi-tick.** "drink" walks the animal to water over several
  ticks; the path has side effects (it might cross a predator's range), and the animal re-decides
  each tick. Outcomes (does a hunt land?) are rolled from the matchup of stats and terrain.

See [DESIGN.md](DESIGN.md) for the full design and [JEV_API.md](JEV_API.md) for the Jev integration.

## Run it

Python 3.11+, no dependencies.

```bash
# headless: run the sim and print populations over time
python3 run_headless.py --ticks 600

# with the browser UI (drag to pan, scroll to zoom, click an animal to inspect it)
python3 run_server.py --policy mock          # heuristic policy, no API key needed
python3 run_server.py --policy jev           # real Jev decisions (needs an API key)
# then open http://127.0.0.1:8000
```

### Using Jev

Get an API key from the [TypeSafe console](https://console.typesafe.ai/keys) and expose it:

```bash
export TYPESAFE_API_KEY="apikey_..."
python3 run_server.py --policy jev
```

The key is read from `$TYPESAFE_API_KEY` (or `~/.typesafe/config.json`). **Never commit it.**
Each animal makes one Jev Choice call per tick; the decide phase runs concurrently, and the UI
shows live Jev metrics (requests, latency, throughput, confidence, tokens).

## The UI

- Fullscreen island in an infinite sea; **drag** to pan, **scroll** to zoom.
- **Click an animal** to open a floating widget with its live perception, the chosen action, a
  probability bar per action, and its **decision history over time** (action + confidence each
  tick).
- Play / pause / step / speed, live per-species populations, an event ticker, and the Jev metrics.

## Layout

```
sim/config.py      every tunable constant (stat scales, rates, terrain, populations, Jev)
sim/noise.py       value-noise / fbm for the island and vegetation
sim/world.py       the grid, terrain, vegetation, carcasses, occupancy
sim/species.py     species trait tables
sim/animal.py      per-animal state + derived speed + decision history
sim/perception.py  builds the plain-text banded state + the legal action mask
sim/policy.py      MockPolicy (heuristic) and JevPolicy (TypeSafe API) behind one interface
sim/actions.py     movement, goal-seeking, probabilistic action resolution
sim/engine.py      the tick loop (perceive -> decide -> resolve -> update)
sim/server.py      stdlib HTTP server + JSON API
web/index.html     the canvas UI
```

## Policy interface

The engine only ever calls `policy.decide_verbose(state_text, available_actions)`. Swap the brain
by swapping the policy — nothing else changes.
