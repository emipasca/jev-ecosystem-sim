"""The animal: stored state per DESIGN.md's spec table, plus derived speed.

Stored: species, pos, heading, age, size, energy, stamina, health, hydration,
alive (and the current multi-tick intent). Speed is DERIVED each tick from
size, energy, stamina, health and exertion -- never stored.
"""

import math
from collections import deque

from . import config as C
from .species import Species


class Animal:
    _next_id = 1

    def __init__(self, species: Species, x: int, y: int, *, adult: bool = True,
                 energy_frac: float = 0.70, hydration_frac: float = 0.80):
        self.id = Animal._next_id
        Animal._next_id += 1
        self.species = species
        self.x = x
        self.y = y
        self.heading = 0.0                    # radians, last move direction
        self.age = species.maturity_age if adult else 0
        self.size = species.mass if adult else species.mass * C.OFFSPRING_SIZE_FRAC
        self.energy = species.energy_cap * energy_frac
        self.stamina = species.stamina_max
        self.health = species.health_max
        self.hydration = C.HYDRATION_MAX * hydration_frac
        self.alive = True

        # Multi-tick intent (goal-directed actions, not instant)
        self.action = "idle"
        self.action_ticks = 0
        self.goal = None            # ("point", (x, y)) or ("animal", Animal)
        self.move_budget = 0.0      # fractional cells carried between ticks
        self.sprinted = False       # sprinted this tick (blocks stamina regen)
        self.repro_cooldown = 0
        self.jev_detail = None      # latest decision detail (served by /api/entity)
        self.history = deque(maxlen=C.HISTORY_MAXLEN)  # (tick, action, confidence) over time

    # ------------------------------------------------------------- fractions
    @property
    def energy_frac(self):
        return self.energy / self.species.energy_cap

    @property
    def stamina_frac(self):
        return self.stamina / self.species.stamina_max

    @property
    def health_frac(self):
        return self.health / self.species.health_max

    @property
    def hydration_frac(self):
        return self.hydration / C.HYDRATION_MAX

    @property
    def size_frac(self):
        return self.size / self.species.mass

    @property
    def is_adult(self):
        return self.age >= self.species.maturity_age

    @property
    def is_weak(self):
        """Huntable by weak-only predators: injured or juvenile."""
        return (self.health_frac < C.WEAK_PREY_HEALTH_FRAC
                or self.size_frac < C.WEAK_PREY_SIZE_FRAC)

    # ------------------------------------------------------------- derived speed
    def current_speed(self, sprinting: bool) -> float:
        """Actual top speed right now, in world-points/tick (before terrain).

        speed = f(size, energy, stamina, health, exertion): condition caps what
        the body can actually hit; exertion buys sprint burst; empty stamina
        means the sprint collapses ("gassed").
        """
        t = self.species
        base = (t.top_speed
                * (0.45 + 0.55 * self.size_frac)
                * (0.55 + 0.45 * self.health_frac)
                * (0.65 + 0.35 * min(1.0, self.energy_frac * 2.2)))
        if sprinting:
            if self.stamina > 1.0:
                return base * (1.0 + C.SPRINT_EXERTION_BOOST * t.exertion / 100.0)
            return base * C.GASSED_FRAC
        return base * C.CRUISE_FRAC

    def dist_to(self, other) -> float:
        return math.dist((self.x, self.y), (other.x, other.y))
