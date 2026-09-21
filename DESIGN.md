# Ecosystem Simulation (Jev agents)

A scratch doc for the idea. Write freely, it autosaves.

## Concept

A 2D territory populated by animals, each an autonomous agent, where the natural food chain *emerges* from individual decisions rather than being scripted. Predators hunt, prey flee and forage, and the population dynamics (who thrives, who crashes, where the equilibrium settles) fall out of the interactions. The point is emergence: set up the agents and the rules of the terrain, then watch a living food web balance itself.

## Inspiration

The Namibia beach-lions piece: https://www.smithsonianmag.com/science-nature/in-namibia-lions-are-king-of-the-beach-180981718/

Desert-adapted lions on the Skeleton Coast that learned to hunt the shoreline (cape fur seals, cormorants, flamingos), an unusual predator-prey dynamic in a harsh coastal territory. The hook: a real ecosystem finding a strange local equilibrium under pressure, exactly the kind of emergent behaviour a sim should reproduce.

## Why Jev

Jev (typesafe.ai) is a "System One Model" that outputs **typed decisions with calibrated probabilities** instead of text, trained via RLCD. Claims ~193x faster / ~444x cheaper than an LLM for automation tasks.

Why it fits: each animal is a Jev agent making a fast, cheap, calibrated typed decision every tick (hunt / flee / forage / rest / move-direction), so you can scale to a whole territory of agents without an LLM call per creature per tick. The calibrated probabilities also give you a natural way to model instinct vs risk (a hungrier predator commits to a low-confidence hunt).

## Agent state (per animal)

The point is to pick states that *couple* to each other, so behaviour emerges from the physics instead of from rules.

| State | Kind | What it does | Depends on |
| --- | --- | --- | --- |
| size / mass | trait | top speed, storage, exertion, prey eligibility, food value | grows with age |
| exertion capacity | trait | peak power for a sprint or fight | size |
| age / maturity | trait | lifecycle: size, speed, breeding | time |
| energy | resource | fuel; hits 0 = starve | eating, exertion |
| energy storage cap | resource (max) | famine tolerance | size |
| stamina | resource | burst pool; caps sustained speed | rest, exertion |
| health / condition | resource | 0 = death; also lowers speed/exertion | hunts, fights, rest |
| hydration (optional) | resource | thirst pressure | water on the map |
| hunger | drive | risk tolerance, hunt vs forage | energy |
| fear / threat | drive | flee vs forage | nearby predators |
| reproductive readiness | drive | breeding, closes the population loop | age, energy surplus |
| **speed** | **derived** | movement rate, recomputed each tick | size, energy, stamina, exertion, health |

**Body (slow-changing traits):**
- **size / mass** , the master variable. Sets top speed, energy storage, exertion capacity, base metabolism, what it can prey on vs be preyed by, and its food value when eaten.
- **exertion capacity** , peak power output, roughly a function of size/muscle. Caps how hard it can push in a sprint or a fight.
- **age / maturity** , drives size and speed over a lifecycle; very young/old are slower and better prey. Gates reproduction.

**Resources (fast-changing, the survival currencies):**
- **energy** , fuel. Drains every tick (base metabolism + exertion); refilled by eating. Hits 0 = starve.
- **energy storage capacity** , max energy, a function of size. Big animals survive famine longer but need more absolute food.
- **stamina** , short-term burst pool, separate from energy. Depletes with exertion (sprinting), regenerates at rest. Gates how *long* a chase or flee can last.
- **health / condition** , damage from failed hunts and fights; heals slowly if fed and rested. Lowers realized speed and exertion; 0 = death.
- **hydration** (optional, if terrain has water) , second resource pressure, fits the harsh-territory Namibia theme.

**Drives (the decision signals fed to Jev):**
- **hunger** , rises as energy falls; raises risk tolerance (a starving predator takes the low-confidence hunt , the calibrated-Jev tie-in).
- **fear / perceived threat** , from nearby predators; drives flee vs forage.
- **reproductive readiness** , a function of age + energy surplus; closes the population loop if we model breeding.

**Derived, not stored:**
- **speed** = f(size, current energy, remaining stamina, exertion, health). Bigger = higher top speed but superlinear energy cost; low energy/stamina/health caps the speed it can actually hit. So it is computed each tick, not a fixed stat.

### Key relationships (the emergent engine)
- energy drain/tick = base metabolism (f size) + exertion cost (rises ~with speed², so sprinting is a gamble).
- stamina caps *sustained* speed , forces the ambush-vs-chase choice; a predator that misses is now low on stamina and vulnerable.
- health down , speed/exertion down , easier prey , death spirals (a realistic positive feedback).
- size sets predator/prey eligibility + food value , this IS the food-chain structure.
- hunger up , risk tolerance up , commits to lower-confidence Jev actions.

### Rates / timescales

Yes, stats should change at different rates, and the rates are where the interesting behaviour comes from. Two principles:

- **Asymmetry (fast to lose, slow to regain)** is what makes decisions cost something:
  - stamina: fast both ways (drains in a sprint, back after a short rest).
  - energy: slow burn every tick, only refills when it actually catches food.
  - health: damage is instant (a fight), healing is slow, so a failed hunt genuinely hurts.
  - size / age: lifecycle-slow, effectively one direction (until starvation eats into mass).
- **The rate ratios are the main balance dial.** Tune stamina-regen vs energy-burn vs heal-rate and the whole ecosystem tips: too-fast stamina regen and predators run everything; too-fast energy burn and everything starves. This is the knob to expose for experiments.

## Architecture & design ideas

- **2D world**: animals move in 2D space across a territory (grid or continuous, TBD).
- **State map each tick**: render a snapshot of the whole world state every tick, positions, who's alive, hunger/energy, so you can watch it play out and replay it.
- **Per-agent decision loop**: each tick, every animal feeds its local observation (nearby animals, terrain, own hunger/energy) to Jev, which returns a typed action + confidence.
- Open: observation radius; tick rate; how many agents before Jev cost/latency bites. (Resolved: high-def grid, see Map section; terrain matters , water/shore/cover.)

## Map (v1): high-def grid island

- **Grid, high resolution.** The world is a fine grid (e.g. 256x256 or larger), so positions are precise and movement reads as smooth. High-def is cheap , grid size does not drive cost, the per-animal Jev calls do.
- **One animal per cell (for now).** A cell holds at most one animal, so animals can't stack and predation happens on **adjacency**, not co-occupation. Resources (vegetation biomass, water, a carcass) are cell properties and don't block an animal from standing there.
- **Cell state:** terrain (land / water / shore), vegetation biomass, occupant (an animal or none), carcass (energy, decaying).
- **The map is an island.** Procedural landmass (radial falloff + noise for an irregular coastline) surrounded by sea. Water is impassable to land animals and is the drink source at the shoreline. The sea is the territory boundary , no walls needed, and it makes the island a closed system.
- **Procedural vegetation.** Placed by noise (Perlin / Simplex) so it clusters into denser and sparser regions instead of a uniform sprinkle; each vegetated cell has biomass that grazes down and regrows.
- **Movement on the grid.** 8-neighbour steps; speed = cells moved per tick (a faster animal advances more cells along its path). Greedy step toward the goal, avoiding water and occupied cells, is enough for v1; add A* later if animals snag on a concave coastline.

**Emergent bonus (island + occupancy):** because water blocks movement and cells can't be shared, predators can herd prey against the shoreline and corner them , the coast becomes a natural trap. Falls out of the island + one-per-cell rules for free, and it's exactly the beach-lions inspiration.

## Terrain (v1)

Terrain modifies performance **live** based on the cell an animal is on: movement speed, move energy cost, vision (concealment), action odds (a hunt), and food. Design principle: each terrain should push a *different* axis, so terrain becomes tactical geography, not flavour.

| Terrain | Move speed | Move energy | Vision / conceal | Vegetation | Special |
| --- | --- | --- | --- | --- | --- |
| sea / water | impassable | , | , | , | drink at adjacent shore |
| shallow beach | reduced | higher | exposed (high vis both ways) | none | shoreline kill-zone; drink |
| grassland (default) | baseline | baseline | normal | moderate | , |
| brush / tall grass | slightly reduced | baseline | concealed (low vis) | some | ambush cover: hunt odds up |
| forest | slow | baseline | strongly concealed | high (browse) | food-rich but low visibility; good hiding / rest |
| rocky highland | slow | higher (climb) | vantage (high vis) | none | early warning / lookout |
| marsh / wetland | very slow | much higher | normal | sparse | bogging trap; near water (drink) |

**How it plugs in:**
- **Movement**: speed and move-energy cost scale by the cell's terrain (his example: shallow beach slows you, so the coast is where a chase gets won or lost).
- **Perception**: terrain sets vision , cover shrinks it (ambush both ways), a highland lookout widens it. So the same threat reads "none" from tall grass but "closing" from a hilltop.
- **Action odds**: a hunt resolves better for the attacker in cover or on slowing terrain (prey bogged in marsh / beach), worse in the open. Terrain is a term in P(hunt success).

**Tactical geography that emerges:** predators lurk in brush near a beach and drive prey onto the slow sand; prey that reaches a highland gets early warning; the forest trades safety (cover + food) for ambush risk. Position becomes a real decision.

## Spatial model: grid world, multi-tick actions, side effects

The world is a **high-def grid** (see Map above) , the live map , even though Jev only ever perceives the coarse bands. Two resolutions on purpose: the world is precise, perception is abstracted.

**Actions are goal-directed intents, not instant.** Picking "drink" when the nearest water is a few points away does not teleport the animal , it sets the goal and the animal moves toward the water at its speed, tick by tick, and only drinks once it arrives. Same for hunt (move toward prey), eat (move to carcass), flee (move away from threat), mate (move to mate).

**So decisions have side effects.** The path matters: walking to water might cross a predator's range or bring the animal into another's vision, creating new position-based states that did not exist when it decided. Emergent encounters fall out of movement, not scripting. This is the whole point of the high-res map.

**Re-decide each tick with the new position.** Because moving changes what the animal perceives, it re-evaluates every tick: a predator that appears mid-walk-to-water flips threat to "closing", and the animal can abandon drinking and flee. The goal persists as a soft default, but fresh perception overrides it , that feedback loop is what makes the side effects meaningful.

**Cost tradeoff (flag):** re-deciding every tick is maximally responsive but multiplies Jev calls (ties to the how-many-agents-before-cost-bites question). Cheaper middle path: commit to a movement goal for several ticks, but allow a high-priority interrupt (a closing predator) to force an immediate re-decision. The re-decision cadence is a tuning dial against cost.

## Jev interface (state encoding + actions)

**State , plain text with discrete bands.** Jev is fed the animal's full state as plain text. Each continuous stat is rendered into named threshold bands, with the number of bands varying per stat (more where nuance drives the decision, fewer where it doesn't):
- energy / hunger: starving / hungry / satisfied / full
- stamina: spent / winded / fresh
- health: injured / hurt / healthy
- threat: none / predator nearby / predator closing
- nearest prey: none / distant / in range
- current action (self): idle / heading to water / chasing prey / fleeing / eating / etc, plus how long (just started / ongoing / dragging on)

**The animal sees its own current action.** Jev *is* the animal, so its in-progress action and how long it has been running are part of its perceived state. This gives continuity of intent: it knows it is already walking to water, so "continue" is a natural choice and it does not dither between goals every tick. The elapsed duration also lets give-up behaviour emerge , been chasing 10 ticks and gassed → break off.

Band boundaries are tuning knobs, like the rates. **Watch:** too-coarse bands flatten the gradients that make behaviour interesting , if hunger is only 4 steps, the hunger→risk-tolerance curve gets steppy, so give the most consequential stats a couple extra bands.

**Actions , gated by what's in vision, reached by movement.** Proximity is NOT the mask (see Spatial model): an action is available if its target is perceived anywhere in vision, and the animal moves to it over ticks. Masked only when the target is unknown entirely:
- hunt , if prey is in vision (move toward it, resolve on contact)
- eat , if a carcass is in vision (move to it, eat on arrival)
- drink , if water is in vision (move to it, drink on arrival)
- flee / sprint , if a threat is perceived; costs stamina, capped/failing when spent
- rest / wander , always available (wander is how it searches when nothing useful is in vision)
- mate , if reproductive-ready and a mate is in vision (move to it)

**Mask vs attempt.** Hard-mask the physically impossible (eat with no food). But leave the risky-but-possible actions available (a starving animal attempting a low-odds hunt), so the calibrated-decision desperation still emerges instead of being ruled out.

## Action resolution (outcome probability)

Two *different* probabilities, don't conflate them:
- **P(choose)** , Jev's calibrated confidence in picking the action. This is about the *decision*.
- **P(succeed)** , the chance the action actually works once taken (hunt lands, prey escapes). This is about the *world*.

Outcome probability comes from the **matchup of states**, not from Jev and not from pure randomness:
- P(hunt success) = f(predator speed / stamina / health vs prey speed / stamina / health, distance, cover / terrain), then roll against it to resolve. So the stats and their couplings pay off at the moment of truth.

**Jev never sees the odds , that's the point.** The animal decides purely from its *perceived* state (hunger, prey in range, own stamina / health); Jev's calibrated confidence IS its instinct. Handing it the true success odds would turn the decision model into a lookup table and kill the emergence. The odds stay hidden and only resolve the outcome , whether the instinct was good shows up in whether the animal survives, not in a number it was told.

Keep it probabilistic (roll), not deterministic: variance means upsets happen (prey sometimes escapes a faster predator), which is what stops the ecosystem collapsing to whoever holds the highest single stat.

## Spec (v0)

First pass, expect it to change. Ranges are placeholders to tune.

### Stored state (per animal, mutates each tick)
| Field | Type | Range | Notes |
| --- | --- | --- | --- |
| species | enum | , | sets traits + diet |
| pos | (x, y) float | world bounds | position |
| heading | float | 0..2π | facing / last move dir |
| age | float | 0..lifespan | ticks alive |
| size | float | 0..size_max | grows with age; master trait |
| energy | float | 0..energy_cap | fuel; 0 = starve |
| stamina | float | 0..stamina_max | burst pool |
| health | float | 0..health_max | 0 = death |
| hydration | float | 0..hydration_max | optional |
| alive | bool | , | dead body becomes a carcass |

### Traits (constant per species; small per-individual variance)
size_max, energy_cap (f size), stamina_max, health_max, exertion_capacity (f size), base_metabolism (f size), vision_radius, heal_rate, maturity_age, lifespan, diet (list of prey species), sprint_cost, drink_need.

### Derived state (computed each tick, never stored)
| Field | From | Notes |
| --- | --- | --- |
| speed | size, energy, stamina, health, exertion | actual current top speed |
| hunger band | energy / energy_cap | starving/hungry/satisfied/full |
| stamina band | stamina / stamina_max | spent/winded/fresh |
| health band | health / health_max | injured/hurt/healthy |
| threat | nearest predator in vision | none/nearby/closing |
| nearest prey | scan vision for diet species | none/distant/in-range |
| can_mate | age, energy surplus, mate in range | gates the mate action |

These bands are what get rendered to plain text and fed to Jev. Raw numbers stay hidden.

### Actions (the typed decision set)
| Action | Precondition (mask) | Effect |
| --- | --- | --- |
| wander / move(dir) | always | move at cruise speed; low energy, no stamina |
| sprint(dir) | stamina > 0 | move at top speed; high stamina + energy cost |
| hunt(target) | prey in range | roll P(success) from matchup: success = kill (target → carcass), fail = energy/stamina spent + possible injury |
| flee(dir) | threat present | sprint away from threat |
| eat | on a carcass / food | + energy (bounded by energy_cap) |
| drink | near water | + hydration |
| rest | always | + stamina, + health (slow); minimal energy drain |
| mate | can_mate | spawn offspring; large energy cost |

### Environment (world state)
- **Space**: 2D, W x H (grid or continuous, TBD). Bounded territory.
- **Terrain cells**: open / water / cover. Water enables drink; cover lowers a hunt's success odds (prey hides); terrain can modulate speed.
- **Entities**: animals, carcasses (energy value, decays over ticks), vegetation/food for herbivores (regrows on a timer).
- **Tick loop**: for each animal, perceive (build derived bands from local world) → decide (Jev picks a legal action) → resolve (apply effects, roll outcomes) → update stats (metabolism, regen, aging) → then render the full state map for that tick.
- **Clock**: discrete ticks; a global step count drives regrowth, aging, decay.

## Species (v1)

A minimal 3-species web on top of vegetation (an environment resource that regrows). Numbers are relative placeholders on a 0..100 stat scale, distances/speeds in world-points; all tunable. The chain: vegetation → gazelle → lion, with jackal as scavenger/opportunist.

| Species | Role | Diet | Mass | Top spd | Stamina | Health | Exertion | Energy cap | Metab/tick | Vision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gazelle | prey / herbivore | vegetation | 30 | 9 | 90 | 40 | 30 | 60 | 1.0 | 22 |
| Lion | apex predator | gazelle (+ carrion) | 190 | 11 | 45 | 100 | 95 | 200 | 2.5 | 18 |
| Jackal | scavenger / opportunist | carrion + weak/young gazelle | 15 | 8 | 70 | 30 | 20 | 45 | 0.8 | 20 |

**Balance intuition (why these numbers).** The dynamics should fall out of the stats, not rules:
- Lion top speed (11) > gazelle (9), so a lion CAN run one down , but lion stamina (45) is half the gazelle's (90) and its metabolism is high, so a gazelle that detects early and runs outlasts the chase. Predation becomes ambush and surprise, not raw footraces. Exactly the tension we want.
- Gazelle survives on wide vision (22) + endurance, dies when caught flat-footed (low health, 40).
- Jackal is too weak (exertion 20) to take a healthy gazelle, so it lives off carcasses lions leave and picks off the young/injured. A real scavenger niche that also cleans the map.

**Initial state (a freshly spawned adult):**
- energy = 70% of energy_cap, stamina = 100%, health = 100%, hydration = 80%
- age = maturity_age (start as adults; optionally spread ages for realism)
- size = adult mass (above), position = random within the territory

**Initial population (world seed):**
- gazelle x40, lion x4, jackal x10 (prey-heavy pyramid), plus many regrowing vegetation patches.
- Predators spawned spread out so they don't all converge on one herd at t=0.

**Reskin note:** the Namibia coastal theme maps straight onto this , seal (prey, eats fish patches) / lion (predator) / jackal (scavenger). Same numbers, different labels.

### Resources (non-agents)

Vegetation, water and carcasses are **passive**: they hold state and change over time but make no decisions, so no Jev call, cheap to run. Only animals are agents.

- **Vegetation** (producer tier, the gazelle's food): patches with a biomass level that drops when grazed and regrows on a timer up to a cap. This is what self-regulates the system from the bottom , too many gazelle overgraze, biomass crashes, gazelle starve, population falls, *even with no lions*. Regrowth rate is a major balance knob (fast → herbivore boom → predator boom; slow → everyone starves).
- **Water**: fixed pools; enables drink; infinite in v1 (can add depletion later).
- **Carcasses**: spawned when an animal dies, carry an energy value that decays over ticks, the jackal's main food, gone when eaten or rotted.

Bottom-up (food supply) + top-down (predation) control together give the self-correcting population cycle , the classic predator-prey oscillation, grounded in real mechanics.

## Open questions

- How is the food chain defined, hardcoded predator/prey table, or learned?
- What's the win condition / what are we actually watching for, a stable equilibrium, or interesting collapses?
- Scale target: how many animals in one territory?
