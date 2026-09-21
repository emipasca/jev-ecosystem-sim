"""The simulation engine: seed the island, then run the tick loop.

Per animal each tick: perceive -> decide (policy) -> resolve -> update stats.
Then resources (vegetation regrowth, carcass decay) advance and the full grid
state is available via to_state() for recording/rendering.
"""

import random
from collections import Counter, deque

from . import config as C
from .actions import resolve
from .animal import Animal
from .perception import perceive
from .policy import MockPolicy
from .species import SPECIES
from .world import World


class Simulation:
    def __init__(self, seed: int = C.WORLD_SEED, policy=None):
        self.rng = random.Random(seed + 1)
        self.world = World(seed)
        self.policy = policy or MockPolicy(seed)
        self.animals = []
        self.tick_count = 0
        self.events = deque(maxlen=200)
        self.stats = {"births": Counter(), "deaths": Counter(), "kills": Counter()}
        self._seed_population()

    # ------------------------------------------------------------- setup
    def _seed_population(self):
        # washed-up carrion along the shoreline so scavengers survive the
        # cold start before the first kills happen
        shore = [i for i, d in enumerate(self.world.water_dist)
                 if 0 <= d <= C.INITIAL_CARCASS_MAX_WATER_DIST]
        for i in self.rng.sample(shore, min(C.INITIAL_CARCASSES, len(shore))):
            self.world.carcasses[i] = C.INITIAL_CARCASS_ENERGY

        predator_spots = []
        for name, count in C.INITIAL_POPULATION.items():
            sp = SPECIES[name]
            group = C.SPAWN_GROUP_SIZE.get(name, 1)
            placed = 0
            while placed < count:
                if sp.diet:  # predator groups spawn spread out and better-fed
                    x, y = self.world.random_free_cell(
                        min_dist_from=predator_spots, min_dist=C.PREDATOR_MIN_SPACING)
                    predator_spots.append((x, y))
                    energy = C.PREDATOR_START_ENERGY_FRAC
                else:
                    x, y = self.world.random_free_cell()
                    energy = 0.70
                for n in range(min(group, count - placed)):
                    spot = (x, y) if n == 0 else self._free_cell_near(x, y)
                    if spot is None:
                        continue
                    a = Animal(sp, *spot, energy_frac=energy)
                    # spread ages a little for realism, and stagger breeding so
                    # adjacent spawns don't all mate on tick 0
                    a.age += self.rng.randint(0, sp.maturity_age)
                    a.repro_cooldown = self.rng.randint(0, sp.repro_cooldown)
                    self.world.place(a, *spot)
                    self.animals.append(a)
                    placed += 1

    def _free_cell_near(self, x, y, radius=3):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if (dx or dy) and self.world.free(x + dx, y + dy):
                    return x + dx, y + dy
        return None

    # ------------------------------------------------------------- tick loop
    BUCKET = 40  # spatial-hash cell size, >= largest terrain-boosted vision + drift

    def _rebuild_index(self):
        """Coarse spatial hash so perception scans nearby animals, not all."""
        self.index = {}
        for a in self.animals:
            if a.alive:
                key = (a.x // self.BUCKET, a.y // self.BUCKET)
                self.index.setdefault(key, []).append(a)

    def nearby_animals(self, x, y):
        bx, by = x // self.BUCKET, y // self.BUCKET
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                out.extend(self.index.get((bx + dx, by + dy), ()))
        return out

    def step(self):
        order = self.animals[:]
        self.rng.shuffle(order)
        self._rebuild_index()
        for animal in order:
            if animal.alive:
                self._agent_turn(animal)
        self.world.update_resources()
        self.animals = [a for a in self.animals if a.alive]
        self.tick_count += 1

    def _agent_turn(self, animal):
        animal.sprinted = False
        per = perceive(self.world, animal, self.nearby_animals(animal.x, animal.y))
        action = self.policy.decide(per.text, per.available)
        if action not in per.available:
            action = "wander"
        if action != animal.action:
            animal.action = action
            animal.action_ticks = 0
            animal.goal = None
        else:
            animal.action_ticks += 1
        resolve(self, animal, per, action)
        if animal.alive:
            self._update_stats(animal)

    def _update_stats(self, animal):
        sp = animal.species
        metab = sp.metabolism * C.METAB_SCALE
        if animal.action == "rest":
            metab *= C.REST_METAB_FRAC
        animal.energy -= metab
        animal.hydration = max(0.0, animal.hydration - C.HYDRATION_DRAIN)

        if not animal.sprinted and animal.action != "rest":
            animal.stamina = min(sp.stamina_max, animal.stamina + C.STAMINA_REGEN_IDLE)
        if animal.energy_frac > C.HEAL_MIN_ENERGY_FRAC and animal.health < sp.health_max:
            rate = sp.heal_rate if animal.action == "rest" else sp.heal_rate * C.HEAL_AMBIENT_FRAC
            animal.health = min(sp.health_max, animal.health + rate)
        if animal.hydration <= 0:
            animal.health -= C.DEHYDRATION_DAMAGE

        animal.age += 1
        if animal.repro_cooldown > 0:
            animal.repro_cooldown -= 1
        if not animal.is_adult:  # growth: juveniles scale toward adult mass
            frac = C.OFFSPRING_SIZE_FRAC + (1 - C.OFFSPRING_SIZE_FRAC) * (animal.age / sp.maturity_age)
            animal.size = sp.mass * min(1.0, frac)

        if animal.energy <= 0:
            self.kill(animal, "starved")
        elif animal.health <= 0:
            self.kill(animal, "died of injuries/thirst")
        elif animal.age > sp.lifespan:
            self.kill(animal, "old age")

    # ------------------------------------------------------------- lifecycle
    def kill(self, animal, cause: str):
        if not animal.alive:
            return
        animal.alive = False
        self.world.clear(animal)
        self.world.add_carcass(animal.x, animal.y,
                               animal.size * C.CARCASS_ENERGY_PER_MASS)
        self.stats["deaths"][f"{animal.species.name}:{cause}"] += 1
        self.log(f"{animal.species.name} #{animal.id} {cause}")

    def spawn_offspring(self, parent, partner):
        sp = parent.species
        spot = None
        for dx, dy in [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]:
            if self.world.free(parent.x + dx, parent.y + dy):
                spot = (parent.x + dx, parent.y + dy)
                break
        parent.repro_cooldown = sp.repro_cooldown
        partner.repro_cooldown = sp.repro_cooldown
        if spot is None:
            return  # no room; cooldown still spent (a failed season)
        parent.energy -= sp.energy_cap * C.REPRO_COST_INITIATOR
        partner.energy -= sp.energy_cap * C.REPRO_COST_PARTNER
        child = Animal(sp, *spot, adult=False, energy_frac=C.OFFSPRING_ENERGY_FRAC)
        self.world.place(child, *spot)
        self.animals.append(child)
        self.stats["births"][sp.name] += 1
        self.log(f"{sp.name} #{child.id} born")

    def log(self, msg: str):
        self.events.append((self.tick_count, msg))

    # ------------------------------------------------------------- output
    def population(self) -> Counter:
        return Counter(a.species.name for a in self.animals if a.alive)

    def to_state(self) -> dict:
        """Full per-tick state for recording / the web UI."""
        w = self.world
        return {
            "tick": self.tick_count,
            "populations": dict(self.population()),
            "animals": [
                {"id": a.id, "species": a.species.name, "x": a.x, "y": a.y,
                 "action": a.action, "energy": round(a.energy_frac, 2),
                 "health": round(a.health_frac, 2), "adult": a.is_adult}
                for a in self.animals if a.alive
            ],
            "carcasses": [
                {"x": i % w.w, "y": i // w.w, "energy": round(e, 1)}
                for i, e in w.carcasses.items()
            ],
            "veg": [int(v) for v in w.veg],
            "events": [f"[{t}] {m}" for t, m in list(self.events)[-8:]],
            "stats": {k: dict(v) for k, v in self.stats.items()},
        }

    def world_static(self) -> dict:
        """Static world description, sent to the UI once."""
        w = self.world
        return {
            "w": w.w, "h": w.h,
            "terrain": list(w.terrain),
            "veg_max": [int(v) for v in w.veg_max],
            "species_colors": {name: sp.color for name, sp in SPECIES.items()},
        }
