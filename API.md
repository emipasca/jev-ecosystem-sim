# API contract

The single interface between the web UI and the sim backend. On the client
this contract is wrapped by `web/api.js` (the `Api` object) — the only file
that touches URLs/HTTP. All paths are **relative** (no leading slash): the app
runs behind a reverse proxy that strips a path prefix, and relative paths keep
working under any prefix. Everything is `GET` and returns JSON.

## `GET api/world` — `Api.world()`

Static world description, fetched once per run (and again after a reset).

| field | description |
|---|---|
| `w`, `h` | grid size in cells |
| `terrain` | length `w*h` array of terrain ids, row-major |
| `veg_max` | length `w*h` array, per-cell vegetation cap |
| `species_colors` | `{species_name: css_color}` |

## `GET api/state` — `Api.state()`

Latest tick state; the UI polls this ~10×/s.

| field | description |
|---|---|
| `tick` | current tick number |
| `populations` | `{species_name: count}` of living animals |
| `animals` | list of `{id, species, x, y, action, energy, health, adult, trail}` — `trail` is the last few `[x, y]` positions |
| `carcasses` | list of `{x, y, energy}` |
| `veg` | length `w*h` array of current per-cell vegetation |
| `events` | recent event log lines, oldest first |
| `stats` | per-species counters (births, deaths, kills, …) |
| `jev` | Jev policy metrics snapshot (`requests`, `avg_latency_ms`, `req_per_s`, `avg_confidence`, `errors`, `input_tokens`, `output_tokens`, `price_known`, `est_cost_usd`), or `null` when the mock policy is running |
| `jev_series` | per-tick `{requests, latency}` series for the live chart |

## `GET api/entity?id=ID` — `Api.entity(id)`

Live decision detail for one animal, polled while the inspector widget is open.
Returns `{id, alive: false}` if the animal is dead or unknown.

| field | description |
|---|---|
| `id`, `species`, `alive`, `x`, `y` | identity and position |
| `state_text` | the perception text handed to the policy |
| `action` | action currently being executed |
| `choice`, `confidence`, `probabilities`, `available` | latest decision: chosen action, its confidence, the full `{action: prob}` distribution, and the actions that were offered |
| `tick` | tick the snapshot was taken at |
| `history` | decision history, oldest first: `{tick, action, confidence, …}` |
| `path` | full movement trail as `[x, y]` pairs |

## `GET api/control?cmd=CMD[&value=V]` — `Api.control(cmd, value)`

Sim control. Commands: `play`, `pause`, `step`, `speed` (`value` = ticks/s,
clamped 0.5–60), `auto` (`value` truthy = as-fast-as-possible), `reset`
(`value` = seed), `sample` (`value` truthy = Jev sampling on).

Always responds with the resulting control state:
`{playing, ticks_per_sec, auto, seed, sample}`.

## Static assets

Anything not under `api/` is served from `web/` by an allowlisted static
handler: `/` → `index.html`, plus `style.css`, `api.js`, `app.js`
(content types `text/html`, `text/css`, `text/javascript`).
