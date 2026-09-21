"""Perception: build the banded, plain-text state an animal decides from.

Two resolutions on purpose (DESIGN.md): the world is a precise grid, but the
decision model only ever sees coarse named bands rendered as plain text --
raw numbers and true odds stay hidden. Terrain modifies vision live: the
viewer's cell scales its vision radius, the target's cell conceals it.
"""

import math
from dataclasses import dataclass, field

from . import config as C
from .world import TERRAIN


@dataclass
class Perception:
    text: str = ""
    available: list = field(default_factory=list)
    # Structured targets for the RESOLUTION side (never shown to the policy):
    threat = None          # nearest Animal that could hunt me, if detected
    threat_band: str = "none"
    prey = None            # nearest huntable Animal in vision
    prey_band: str = "none"
    carcass = None         # (x, y) of nearest carcass in vision/scent
    carcass_band: str = "none"
    water = None           # (x, y) of nearest drink spot
    water_band: str = "none"
    veg_target = None      # (x, y) of a graze-worthy cell
    veg_band: str = "none"
    mate = None            # nearest willing mate in vision


def band(value, thresholds):
    """thresholds: list of (upper_bound, name); last entry is the fallback."""
    for bound, name in thresholds[:-1]:
        if value <= bound:
            return name
    return thresholds[-1][1]


def could_hunt(pred, prey) -> bool:
    if prey.species.name not in pred.species.diet:
        return False
    if pred.species.hunts_weak_only and not prey.is_weak:
        return False
    return True


def is_threat(me, other) -> bool:
    """Fear is broader than diet: a jackal fears a lion even though lions
    don't hunt jackals (that's what keeps it off a lion's kill), while a
    healthy adult gazelle doesn't fear a weak-only hunter like the jackal."""
    if other.species.name not in me.species.threats:
        return False
    if other.species.hunts_weak_only and not me.is_weak:
        return False
    return True


def duration_band(ticks: int) -> str:
    if ticks < C.ACTION_JUST_STARTED:
        return "just started"
    if ticks <= C.ACTION_DRAGGING:
        return "ongoing"
    return "dragging on"


def perceive(world, animal, animals) -> Perception:
    p = Perception()
    t_here = world.terrain_at(animal.x, animal.y)
    vision = animal.species.vision * t_here.vision_mult

    # --- other animals: nearest threat and nearest huntable prey.
    # Detection range = my (terrain-scaled) vision * the target cell's conceal.
    nearest_threat, threat_dist = None, None
    nearest_prey, prey_dist = None, None
    nearest_mate, mate_dist = None, None
    self_can_mate = (animal.is_adult and animal.repro_cooldown == 0
                     and animal.energy_frac >= C.REPRO_ENERGY_FRAC)
    for other in animals:
        if other is animal or not other.alive:
            continue
        d = animal.dist_to(other)
        if d > vision:  # cheap upper bound before the conceal check
            continue
        detect = vision * world.terrain_at(other.x, other.y).conceal_mult
        if d > detect:
            continue
        if is_threat(animal, other) and (threat_dist is None or d < threat_dist):
            nearest_threat, threat_dist = other, d
        if could_hunt(animal, other) and (prey_dist is None or d < prey_dist):
            nearest_prey, prey_dist = other, d
        if (self_can_mate and other.species is animal.species and other.is_adult
                and other.repro_cooldown == 0
                and other.energy_frac >= C.REPRO_ENERGY_FRAC
                and (mate_dist is None or d < mate_dist)):
            nearest_mate, mate_dist = other, d

    p.threat = nearest_threat
    if nearest_threat is not None:
        p.threat_band = ("predator closing" if threat_dist <= C.THREAT_CLOSE_DIST
                         else "predator nearby")
    p.prey = nearest_prey
    if nearest_prey is not None:
        p.prey_band = "in range" if prey_dist <= C.PREY_IN_RANGE_DIST else "distant"
        if nearest_prey.action == "flee":  # visibly bolting -- chase is a gamble
            p.prey_band += ", fleeing"
    p.mate = nearest_mate

    # --- carcasses: scavengers smell carrion well beyond sight
    scent = vision * (C.CARRION_SCENT_MULT if animal.species.scavenger else 1.0)
    best_c, best_cd = None, None
    for i, energy in world.carcasses.items():
        cx, cy = i % world.w, i // world.w
        d = math.dist((animal.x, animal.y), (cx, cy))
        if d <= scent and (best_cd is None or d < best_cd):
            best_c, best_cd = (cx, cy), d
    p.carcass = best_c
    if best_c is not None:
        if best_cd <= 2:
            p.carcass_band = "at hand"
        elif best_cd <= 8:
            p.carcass_band = "close"
        else:
            p.carcass_band = "in sight"

    # --- water (precomputed walking-distance field)
    i_here = world.idx(animal.x, animal.y)
    wd = world.water_dist[i_here]
    if wd == 0:
        p.water, p.water_band = world.water_src[i_here], "here"
    elif wd <= vision:
        p.water, p.water_band = world.water_src[i_here], "in sight"

    # --- vegetation (herbivores): current cell, else nearest worthwhile patch
    if animal.species.herbivore:
        if world.veg[i_here] >= C.GRAZE_MIN:
            p.veg_target, p.veg_band = (animal.x, animal.y), "here"
        else:
            found = _nearest_veg(world, animal.x, animal.y,
                                 min(int(vision), C.GRAZE_SEARCH_RADIUS))
            if found:
                p.veg_target, p.veg_band = found, "in sight"

    # --- legal actions (masked only when the target is unknown entirely)
    avail = ["wander", "rest"]
    if p.threat is not None:
        avail.append("flee")
    if p.prey is not None:
        avail.append("hunt")
    if p.carcass is not None and animal.species.scavenger:
        avail.append("eat")
    if p.water is not None:
        avail.append("drink")
    if p.veg_target is not None:
        avail.append("graze")
    if p.mate is not None:
        avail.append("mate")
    p.available = avail

    # --- the plain-text banded state (the ONLY thing the policy sees)
    hunger = band(animal.energy_frac, [(C.HUNGER_STARVING, "starving"),
                                       (C.HUNGER_HUNGRY, "hungry"),
                                       (C.HUNGER_SATISFIED, "satisfied"),
                                       (None, "full")])
    thirst = band(animal.hydration_frac, [(C.THIRST_PARCHED, "parched"),
                                          (C.THIRST_THIRSTY, "thirsty"),
                                          (None, "fine")])
    stamina = band(animal.stamina_frac, [(C.STAMINA_SPENT, "spent"),
                                         (C.STAMINA_WINDED, "winded"),
                                         (None, "fresh")])
    health = band(animal.health_frac, [(C.HEALTH_INJURED, "injured"),
                                       (C.HEALTH_HURT, "hurt"),
                                       (None, "healthy")])
    p.text = "\n".join([
        f"species: {animal.species.name}",
        f"hunger: {hunger}",
        f"thirst: {thirst}",
        f"stamina: {stamina}",
        f"health: {health}",
        f"threat: {p.threat_band}",
        f"nearest prey: {p.prey_band}",
        f"carcass: {p.carcass_band}",
        f"water: {p.water_band}",
        f"vegetation: {p.veg_band}",
        f"mate: {'in sight' if p.mate else 'none'}",
        f"current action: {animal.action} ({duration_band(animal.action_ticks)})",
    ])
    return p


def _nearest_veg(world, x, y, max_r):
    """Ring search outward for the nearest cell worth walking to for grazing."""
    for r in range(1, max_r + 1):
        best, best_d = None, None
        for dx in range(-r, r + 1):
            for dy in (-r, r) if abs(dx) != r else range(-r, r + 1):
                nx, ny = x + dx, y + dy
                if not world.in_bounds(nx, ny):
                    continue
                if world.veg[world.idx(nx, ny)] >= C.GRAZE_TARGET_MIN:
                    d = dx * dx + dy * dy
                    if best_d is None or d < best_d:
                        best, best_d = (nx, ny), d
        if best:
            return best
    return None
