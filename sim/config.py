"""All tunable constants for the ecosystem sim.

Everything balance-related lives here: stat scales, rates, terrain modifiers,
band thresholds, populations. The rate *ratios* (stamina regen vs energy burn
vs heal rate) are the main balance dials -- see DESIGN.md "Rates / timescales".
"""

# ---------------------------------------------------------------- world / map
WORLD_W = 200
WORLD_H = 200
WORLD_SEED = 7

# Island generation: elevation = noise*ELEV_NOISE_WEIGHT + ELEV_BASE - radial falloff
ELEV_NOISE_SCALE = 4.0      # noise lattice cells across the map (bigger = busier coast)
ELEV_NOISE_OCTAVES = 5
ELEV_NOISE_WEIGHT = 0.90
ELEV_BASE = 0.30
FALLOFF_EXP = 2.1           # radial falloff shape (higher = flatter middle, sharper edge)
FALLOFF_WEIGHT = 0.95
SEA_LEVEL = 0.34            # elevation at/below this is sea
BEACH_BAND = 0.030          # elevation band above sea level that becomes beach
MARSH_BAND = 0.090          # low wet land above the beach band can become marsh
MARSH_MOISTURE = 0.58
ROCK_LEVEL = 0.80           # elevation above this is rocky highland
FOREST_MOISTURE = 0.64
BRUSH_MOISTURE = 0.50
MOISTURE_NOISE_SCALE = 5.0

# Vegetation (passive resource; clusters by noise)
VEG_NOISE_SCALE = 6.0
VEG_REGROW_RATE = 0.028     # biomass per tick, toward the cell's own cap (main
                            # herbivore carrying-capacity knob, see DESIGN.md).
                            # Also couples to predation: scarce veg keeps prey
                            # moving and hungry, which makes it harder to catch.
GRAZE_RATE = 6.0            # biomass consumed per grazing tick
GRAZE_CONVERT = 0.55        # energy gained per unit biomass eaten
GRAZE_MIN = 1.5             # min biomass on the current cell worth grazing
GRAZE_TARGET_MIN = 10.0     # min biomass for a cell to count as a graze destination
GRAZE_SEARCH_RADIUS = 20    # cap on the ring search for vegetation

# Carcasses (passive resource)
CARCASS_ENERGY_PER_MASS = 4.5   # carcass energy = dead animal size * this
CARCASS_DECAY = 0.18            # energy lost to rot per tick (slow enough that a
                                # killer can come back for seconds after resting)

# ---------------------------------------------------------------- movement
SPEED_TO_CELLS = 3.0        # world-points of speed per grid cell per tick
CRUISE_FRAC = 0.55          # cruise speed as a fraction of current top speed
SPRINT_EXERTION_BOOST = 0.30  # sprint bonus: *(1 + boost * exertion/100)
GASSED_FRAC = 0.70          # sprint speed multiplier when stamina is empty
MAX_STEPS_PER_TICK = 6

MOVE_COST_PER_CELL = 0.06   # energy per cell moved, * (size/30)^0.7 * terrain mult
SPRINT_ENERGY_MULT = 2.2
SPRINT_STAMINA_PER_CELL = 1.2

# ---------------------------------------------------------------- metabolism / stats
METAB_SCALE = 0.28          # global scale on species base metabolism per tick
REST_METAB_FRAC = 0.5       # metabolism multiplier while resting
STAMINA_REGEN_IDLE = 1.2    # per tick when not sprinting
STAMINA_REGEN_REST = 4.0    # per tick while resting
HEAL_AMBIENT_FRAC = 0.3     # fraction of heal_rate applied when fed but not resting
HEAL_MIN_ENERGY_FRAC = 0.35 # below this energy fraction, no healing

HYDRATION_MAX = 100.0
HYDRATION_DRAIN = 0.25      # per tick
DRINK_RATE = 10.0           # hydration per drinking tick
DEHYDRATION_DAMAGE = 0.8    # health per tick at 0 hydration

# ---------------------------------------------------------------- hunting
# The pounce must begin OUTSIDE the prey's panic distance (THREAT_CLOSE_DIST)
# or a stalking predator can never close on alert prey.
POUNCE_RANGE = 12           # within this distance a hunter sprints; beyond, it stalks
COMMIT_RANGE = 5            # keep sprinting after already-fleeing prey only this close
                            # (chasing a bolted gazelle from farther is wasted stamina)
HUNT_BASE_SPEED_WEIGHT = 0.32
HUNT_STAMINA_WEIGHT = 0.22
HUNT_PREY_HEALTH_WEIGHT = 0.18
HUNT_AMBUSH_WEIGHT = 0.22   # * (1 - conceal of the attacker's cell)
HUNT_BOG_WEIGHT = 0.30      # * (1 - speed_mult of the prey's cell): beach/marsh trap
HUNT_P_MIN = 0.03
HUNT_P_MAX = 0.92
ATTACK_STAMINA_COST = 6.0
ATTACK_FAIL_ENERGY = 2.0
COUNTER_DAMAGE_PROB = 0.35  # chance a failed attack injures the attacker
COUNTER_DAMAGE_MASS_FRAC = 0.12  # damage = prey size * this
KILL_BITE_ENERGY = 35.0     # the killer gorges first; the rest becomes carcass
EAT_BITE_BASE = 4.0         # carcass energy per eating tick = base + size * factor
EAT_BITE_SIZE_FACTOR = 0.04
CARRION_SCENT_MULT = 2.5    # scavengers detect carcasses at vision * this (smell, not sight)
WEAK_PREY_HEALTH_FRAC = 0.55   # below this health, prey counts as "weak" (jackal-huntable)
WEAK_PREY_SIZE_FRAC = 0.70     # below this fraction of adult mass, ditto (juveniles)

# ---------------------------------------------------------------- reproduction
REPRO_ENERGY_FRAC = 0.72    # both partners need at least this energy fraction
REPRO_COST_INITIATOR = 0.25 # fraction of energy cap
REPRO_COST_PARTNER = 0.15
OFFSPRING_SIZE_FRAC = 0.35  # newborn size as a fraction of adult mass
OFFSPRING_ENERGY_FRAC = 0.50

# ---------------------------------------------------------------- perception bands
HUNGER_STARVING = 0.15      # energy fraction thresholds
HUNGER_HUNGRY = 0.45
HUNGER_SATISFIED = 0.80
THIRST_PARCHED = 0.15
THIRST_THIRSTY = 0.45
STAMINA_SPENT = 0.20
STAMINA_WINDED = 0.55
HEALTH_INJURED = 0.35
HEALTH_HURT = 0.75
THREAT_CLOSE_DIST = 8       # cells; a detected predator this close reads "closing"
# "In range" must reach beyond the prey's panic distance (THREAT_CLOSE_DIST=8),
# or prey grazes safely at 9-12 cells and an opportunistic predator never engages.
PREY_IN_RANGE_DIST = 12     # cells; detected prey this close reads "in range"
ACTION_JUST_STARTED = 3     # ticks
ACTION_DRAGGING = 10        # ticks

# ---------------------------------------------------------------- populations
# DESIGN.md seeds 40 gazelle, but on this island (~27k land cells) that prey
# density starves the lions before the herd can recruit; 70 rides out the
# early predation dip. The pyramid shape is preserved.
INITIAL_POPULATION = {"gazelle": 70, "lion": 4, "jackal": 10}
PREDATOR_MIN_SPACING = 30   # cells between spawned predator groups, so they start spread out
SPAWN_GROUP_SIZE = {"lion": 2}  # lions spawn in pairs (coalitions) so mates can meet
PREDATOR_START_ENERGY_FRAC = 0.90  # carnivores spawn better-fed (no carrion exists at t=0)
INITIAL_CARCASSES = 12      # washed-up carrion near the coast at t=0 (scavenger cold start)
INITIAL_CARCASS_ENERGY = 90.0
INITIAL_CARCASS_MAX_WATER_DIST = 6

# ---------------------------------------------------------------- misc
WANDER_LEG_DIST = 25        # wander picks a random point about this far away
WANDER_REPICK_TICKS = 20

# ---------------------------------------------------------------- Jev (TypeSafe) API
JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_TIMEOUT = 15.0          # seconds per request before falling back to the heuristic
# Estimated pricing for the cost metric. Set these to TypeSafe's published rate
# ($ per 1,000,000 tokens) once confirmed; 0 leaves cost at $0 (tokens still tracked).
JEV_PRICE_PER_1M_INPUT = 0.0
JEV_PRICE_PER_1M_OUTPUT = 0.0
JEV_MAX_CONCURRENCY = 16     # parallel Jev decide() calls per tick
HISTORY_MAXLEN = 400         # per-animal decision history kept for the inspector
