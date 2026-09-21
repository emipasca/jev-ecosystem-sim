"""Action resolution: goal-directed multi-tick intents, probabilistic outcomes.

Picking an action sets a goal; the animal moves toward it over ticks at its
terrain-modified speed and only performs the act on arrival/contact. Hunts
resolve on ADJACENCY with P(success) computed from the matchup of the two
animals' states + distance-closing + terrain, then rolled. The policy never
sees these odds.
"""

import math

from . import config as C
from .world import TERRAIN, NEIGHBORS8


def chebyshev(a, bx, by):
    return max(abs(a.x - bx), abs(a.y - by))


# ---------------------------------------------------------------- movement
def _move_cost(animal, terrain, sprint):
    scale = (animal.size / 30.0) ** 0.7
    cost = C.MOVE_COST_PER_CELL * scale * terrain.energy_mult
    return cost * C.SPRINT_ENERGY_MULT if sprint else cost


def _take_steps(sim, animal, pick_step, sprint):
    """Consume this tick's movement budget one greedy 8-neighbour step at a
    time. pick_step(x, y) returns the chosen next cell or None to stop."""
    world = sim.world
    terrain = world.terrain_at(animal.x, animal.y)
    speed = animal.current_speed(sprint) * terrain.speed_mult / C.SPEED_TO_CELLS
    animal.move_budget = min(animal.move_budget + speed, C.MAX_STEPS_PER_TICK + 1)
    moved = 0
    while animal.move_budget >= 1.0 and moved < C.MAX_STEPS_PER_TICK:
        nxt = pick_step(animal.x, animal.y)
        if nxt is None:
            animal.move_budget = min(animal.move_budget, 1.0)  # don't bank while blocked
            break
        nx, ny = nxt
        animal.heading = math.atan2(ny - animal.y, nx - animal.x)
        terrain = world.terrain_at(nx, ny)
        animal.energy -= _move_cost(animal, terrain, sprint)
        if sprint:
            animal.stamina = max(0.0, animal.stamina - C.SPRINT_STAMINA_PER_CELL)
            animal.sprinted = True
        world.move(animal, nx, ny)
        animal.move_budget -= 1.0
        moved += 1
        # terrain changed underfoot: recompute what the rest of the budget buys
        speed_here = animal.current_speed(sprint) * terrain.speed_mult / C.SPEED_TO_CELLS
        if speed_here <= 0:
            break
    return moved


def move_toward(sim, animal, tx, ty, sprint=False):
    world = sim.world
    rng = sim.rng

    def pick(x, y):
        cur_d = math.dist((x, y), (tx, ty))
        best, best_d = None, cur_d
        options = []
        for dx, dy in NEIGHBORS8:
            nx, ny = x + dx, y + dy
            if not world.free(nx, ny):
                continue
            d = math.dist((nx, ny), (tx, ty))
            options.append(((nx, ny), d))
            if d < best_d:
                best, best_d = (nx, ny), d
        if best:
            return best
        # blocked straight-line: sidestep along an equal-distance cell sometimes,
        # so animals slide around obstacles instead of jamming
        ties = [c for c, d in options if d <= cur_d + 0.01]
        if ties and rng.random() < 0.7:
            return rng.choice(ties)
        return None

    return _take_steps(sim, animal, pick, sprint)


def move_away(sim, animal, fx, fy, sprint=True):
    world = sim.world
    rng = sim.rng

    def pick(x, y):
        cur_d = math.dist((x, y), (fx, fy))
        best, best_score = None, None
        for dx, dy in NEIGHBORS8:
            nx, ny = x + dx, y + dy
            if not world.free(nx, ny):
                continue
            d = math.dist((nx, ny), (fx, fy))
            # prefer distance gained, with a nudge toward faster terrain
            score = d + 0.6 * world.terrain_at(nx, ny).speed_mult + rng.random() * 0.1
            if d > cur_d - 0.01 and (best_score is None or score > best_score):
                best, best_score = (nx, ny), score
        return best

    return _take_steps(sim, animal, pick, sprint)


def move_meander(sim, animal, sprint=False):
    """A correlated random walk for when nothing is steering the animal: keep a
    rough heading, jitter it each step, drift around obstacles. Reads as natural
    milling/foraging instead of a straight march to a point."""
    world = sim.world
    rng = sim.rng

    # social bias (computed once per tick): drift toward same-species company up to
    # the comfort count, push away when more crowded than that.
    sx = sy = 0.0
    sp = animal.species
    if sp.social_cohesion or sp.social_separation:
        close = [o for o in sim.nearby_animals(animal.x, animal.y)
                 if o is not animal and o.alive and o.species is sp
                 and max(abs(o.x - animal.x), abs(o.y - animal.y)) <= sp.social_radius]
        n = len(close)
        if n:
            cx = sum(o.x for o in close) / n - animal.x
            cy = sum(o.y for o in close) / n - animal.y
            dd = math.hypot(cx, cy) or 1.0
            cx, cy = cx / dd, cy / dd
            if n < sp.social_comfort:
                w = sp.social_cohesion
            elif n > sp.social_comfort:
                w = -sp.social_separation
            else:
                w = 0.0
            sx, sy = cx * w, cy * w

    def pick(x, y):
        h = animal.heading if animal.heading is not None else rng.uniform(0, 2 * math.pi)
        h += rng.gauss(0, C.MEANDER_TURN_SIGMA)
        dx, dy = math.cos(h) + sx, math.sin(h) + sy
        best, best_score = None, None
        for ndx, ndy in NEIGHBORS8:
            nx, ny = x + ndx, y + ndy
            if not world.free(nx, ny):
                continue
            nlen = math.hypot(ndx, ndy) or 1.0
            align = (ndx * dx + ndy * dy) / nlen          # momentum toward heading
            score = align + rng.random() * C.MEANDER_ALIGN_NOISE
            if best_score is None or score > best_score:
                best, best_score = (nx, ny), score
        return best

    return _take_steps(sim, animal, pick, sprint)


# ---------------------------------------------------------------- hunt odds
def hunt_success_prob(world, pred, prey) -> float:
    """P(hunt success) from the state matchup + terrain. Hidden from policies."""
    pred_speed = pred.current_speed(sprinting=True)
    prey_speed = max(prey.current_speed(sprinting=True), 0.1)
    p = C.HUNT_BASE_SPEED_WEIGHT * (pred_speed / prey_speed)
    p += C.HUNT_STAMINA_WEIGHT * (pred.stamina_frac - prey.stamina_frac)
    p += C.HUNT_PREY_HEALTH_WEIGHT * (1.0 - prey.health_frac)
    pred_cell = world.terrain_at(pred.x, pred.y)
    prey_cell = world.terrain_at(prey.x, prey.y)
    p += C.HUNT_AMBUSH_WEIGHT * max(0.0, 1.0 - pred_cell.conceal_mult)   # ambush cover
    p += C.HUNT_BOG_WEIGHT * max(0.0, 1.0 - prey_cell.speed_mult)        # bogged prey
    # overpower: can the attacker physically bring this prey down?
    overpower = (pred.species.exertion * (0.5 + 0.5 * pred.health_frac)
                 / (prey.size * (0.35 + 0.65 * prey.health_frac)))
    p *= min(1.4, max(0.1, overpower))
    return min(C.HUNT_P_MAX, max(C.HUNT_P_MIN, p))


def resolve_attack(sim, pred, prey):
    """Adjacency reached: roll the kill. Costs are paid either way."""
    p = hunt_success_prob(sim.world, pred, prey)
    pred.stamina = max(0.0, pred.stamina - C.ATTACK_STAMINA_COST)
    if sim.rng.random() < p:
        pred.energy = min(pred.species.energy_cap, pred.energy + C.KILL_BITE_ENERGY)
        sim.kill(prey, f"hunted by {pred.species.name}")
        sim.stats["kills"][pred.species.name] += 1
        sim.log(f"{pred.species.name} #{pred.id} killed {prey.species.name} #{prey.id}")
    else:
        pred.energy -= C.ATTACK_FAIL_ENERGY
        prey.stamina = max(0.0, prey.stamina - 4.0)
        if sim.rng.random() < C.COUNTER_DAMAGE_PROB:
            pred.health -= prey.size * C.COUNTER_DAMAGE_MASS_FRAC


# ---------------------------------------------------------------- resolution
def resolve(sim, animal, per, action):
    world = sim.world
    handler = {
        "wander": _do_wander, "rest": _do_rest, "graze": _do_graze,
        "drink": _do_drink, "eat": _do_eat, "hunt": _do_hunt,
        "flee": _do_flee, "mate": _do_mate,
    }.get(action, _do_wander)
    handler(sim, animal, per)


def _do_wander(sim, animal, per):
    # no target is steering it: meander (correlated random walk), don't march
    animal.goal = None
    move_meander(sim, animal, sprint=False)


def _do_rest(sim, animal, per):
    animal.stamina = min(animal.species.stamina_max,
                         animal.stamina + C.STAMINA_REGEN_REST)
    # rest is also where healing mostly happens (update_stats adds heal_rate)


def _do_graze(sim, animal, per):
    world = sim.world
    i = world.idx(animal.x, animal.y)
    if world.veg[i] >= C.GRAZE_MIN:
        bite = min(world.veg[i], C.GRAZE_RATE)
        world.veg[i] -= bite
        animal.energy = min(animal.species.energy_cap,
                            animal.energy + bite * C.GRAZE_CONVERT)
    elif per.veg_target:
        animal.goal = ("point", per.veg_target)
        move_toward(sim, animal, *per.veg_target, sprint=False)
    else:
        # hungry but no grass in sight: meander to search rather than freeze
        animal.goal = None
        move_meander(sim, animal, sprint=False)


def _do_drink(sim, animal, per):
    world = sim.world
    if world.water_dist[world.idx(animal.x, animal.y)] == 0:
        animal.hydration = min(C.HYDRATION_MAX, animal.hydration + C.DRINK_RATE)
    elif per.water:
        animal.goal = ("point", per.water)
        move_toward(sim, animal, *per.water, sprint=False)


def _do_eat(sim, animal, per):
    world = sim.world
    if per.carcass is None:
        return
    cx, cy = per.carcass
    animal.goal = ("point", per.carcass)
    if chebyshev(animal, cx, cy) <= 1:
        i = world.idx(cx, cy)
        if i in world.carcasses:
            bite = min(world.carcasses[i],
                       C.EAT_BITE_BASE + animal.size * C.EAT_BITE_SIZE_FACTOR)
            room = animal.species.energy_cap - animal.energy
            eaten = min(bite, room)
            animal.energy += eaten
            world.carcasses[i] -= eaten
            if world.carcasses[i] <= 0:
                del world.carcasses[i]
    else:
        move_toward(sim, animal, cx, cy, sprint=False)


def _do_hunt(sim, animal, per):
    prey = per.prey
    if prey is None or not prey.alive:
        _do_wander(sim, animal, per)  # lost sight of it; drift until re-decided
        return
    animal.goal = ("animal", prey)
    d = animal.dist_to(prey)
    if chebyshev(animal, prey.x, prey.y) <= 1:
        resolve_attack(sim, animal, prey)
    elif d <= C.POUNCE_RANGE and (prey.action != "flee" or d <= C.COMMIT_RANGE):
        # the burst: pounce on surprised prey, or commit if already on top of it
        move_toward(sim, animal, prey.x, prey.y, sprint=True)
        if animal.alive and prey.alive and chebyshev(animal, prey.x, prey.y) <= 1:
            resolve_attack(sim, animal, prey)
    else:
        move_toward(sim, animal, prey.x, prey.y, sprint=False)  # stalk / shadow


def _do_flee(sim, animal, per):
    if per.threat is None:
        _do_wander(sim, animal, per)
        return
    animal.goal = ("animal", per.threat)
    move_away(sim, animal, per.threat.x, per.threat.y, sprint=True)


def _do_mate(sim, animal, per):
    mate = per.mate
    if mate is None or not mate.alive:
        return
    animal.goal = ("animal", mate)
    if chebyshev(animal, mate.x, mate.y) <= 1:
        sim.spawn_offspring(animal, mate)
    else:
        move_toward(sim, animal, mate.x, mate.y, sprint=False)
