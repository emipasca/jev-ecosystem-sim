"""The grid world: procedural island terrain, vegetation, carcasses, occupancy.

Terrain modifies performance live (movement speed, move energy, vision,
concealment, hunt odds) -- see DESIGN.md "Terrain (v1)". One animal per cell;
resources (vegetation, water, carcasses) are cell properties and don't block.
"""

import math
import random
from collections import deque
from dataclasses import dataclass

from . import config as C
from .noise import ValueNoise


@dataclass(frozen=True)
class TerrainType:
    key: str
    speed_mult: float    # movement speed multiplier on this cell
    energy_mult: float   # move-energy multiplier on this cell
    vision_mult: float   # multiplier on the VIEWER's vision radius here
    conceal_mult: float  # multiplier on the range at which a TARGET here is spotted (<1 hides)
    veg_cap: float       # max vegetation biomass
    passable: bool
    drink: bool          # standing here allows drinking (shore band / marsh)


SEA, BEACH, GRASS, BRUSH, FOREST, ROCK, MARSH = range(7)

TERRAIN = [
    TerrainType("sea",    0.0, 0.0, 1.0,  1.0,  0,  False, False),
    TerrainType("beach",  0.6, 1.5, 1.15, 1.25, 0,  True,  True),
    TerrainType("grass",  1.0, 1.0, 1.0,  1.0,  60, True,  False),
    TerrainType("brush",  0.85, 1.0, 0.7, 0.6,  35, True,  False),
    TerrainType("forest", 0.6, 1.0, 0.5,  0.45, 90, True,  False),
    TerrainType("rock",   0.6, 1.5, 1.4,  1.2,  0,  True,  False),
    TerrainType("marsh",  0.4, 1.8, 1.0,  1.0,  18, True,  True),
]

NEIGHBORS8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]

INF = 10 ** 9


class World:
    def __init__(self, seed: int = C.WORLD_SEED):
        self.w = C.WORLD_W
        self.h = C.WORLD_H
        self.rng = random.Random(seed)
        self._generate(seed)
        self.occupant = [None] * (self.w * self.h)  # Animal or None; one per cell
        self.carcasses = {}                         # cell index -> remaining energy
        self._compute_water_field()

    # ------------------------------------------------------------- indexing
    def idx(self, x: int, y: int) -> int:
        return y * self.w + x

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.w and 0 <= y < self.h

    def terrain_at(self, x: int, y: int) -> TerrainType:
        return TERRAIN[self.terrain[self.idx(x, y)]]

    def passable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and TERRAIN[self.terrain[self.idx(x, y)]].passable

    def free(self, x: int, y: int) -> bool:
        return self.passable(x, y) and self.occupant[self.idx(x, y)] is None

    # ------------------------------------------------------------- generation
    def _generate(self, seed: int):
        w, h = self.w, self.h
        elev_noise = ValueNoise(seed)
        moist_noise = ValueNoise(seed + 101)
        veg_noise = ValueNoise(seed + 202)

        self.terrain = bytearray(w * h)
        self.elevation = [0.0] * (w * h)
        for y in range(h):
            ny = y / h * 2 - 1
            for x in range(w):
                nx = x / w * 2 - 1
                d = math.sqrt(nx * nx + ny * ny) / 1.41421  # 0 centre, 1 corner
                e = elev_noise.fbm(x / w * C.ELEV_NOISE_SCALE, y / h * C.ELEV_NOISE_SCALE,
                                   octaves=C.ELEV_NOISE_OCTAVES)
                elev = e * C.ELEV_NOISE_WEIGHT + C.ELEV_BASE - (d ** C.FALLOFF_EXP) * C.FALLOFF_WEIGHT
                i = self.idx(x, y)
                self.elevation[i] = elev
                if elev <= C.SEA_LEVEL:
                    t = SEA
                else:
                    moist = moist_noise.fbm(x / w * C.MOISTURE_NOISE_SCALE,
                                            y / h * C.MOISTURE_NOISE_SCALE)
                    if elev < C.SEA_LEVEL + C.BEACH_BAND:
                        t = BEACH
                    elif elev < C.SEA_LEVEL + C.MARSH_BAND and moist > C.MARSH_MOISTURE:
                        t = MARSH
                    elif elev > C.ROCK_LEVEL:
                        t = ROCK
                    elif moist > C.FOREST_MOISTURE:
                        t = FOREST
                    elif moist > C.BRUSH_MOISTURE:
                        t = BRUSH
                    else:
                        t = GRASS
                self.terrain[i] = t

        # Vegetation clusters: each cell gets its own cap from noise (permanent
        # dense/sparse regions), regrows toward that cap after grazing.
        self.veg_max = [0.0] * (w * h)
        self.veg = [0.0] * (w * h)
        self.veg_cells = []
        for y in range(h):
            for x in range(w):
                i = self.idx(x, y)
                cap = TERRAIN[self.terrain[i]].veg_cap
                if cap <= 0:
                    continue
                v = veg_noise.fbm(x / w * C.VEG_NOISE_SCALE, y / h * C.VEG_NOISE_SCALE)
                factor = min(1.0, max(0.05, (v - 0.30) * 1.8))
                self.veg_max[i] = cap * factor
                self.veg[i] = self.veg_max[i]
                self.veg_cells.append(i)

    def _compute_water_field(self):
        """Multi-source BFS from every drinkable cell (shore band + marsh),
        giving each land cell its walking distance to water and the nearest
        drink spot. Static -- computed once."""
        w, h = self.w, self.h
        self.water_dist = [INF] * (w * h)
        self.water_src = [None] * (w * h)
        q = deque()
        for y in range(h):
            for x in range(w):
                i = self.idx(x, y)
                t = TERRAIN[self.terrain[i]]
                if not t.passable:
                    continue
                drinkable = t.drink
                if not drinkable:  # any land cell touching sea is a shoreline drink spot
                    for dx, dy in NEIGHBORS8:
                        nx2, ny2 = x + dx, y + dy
                        if self.in_bounds(nx2, ny2) and self.terrain[self.idx(nx2, ny2)] == SEA:
                            drinkable = True
                            break
                if drinkable:
                    self.water_dist[i] = 0
                    self.water_src[i] = (x, y)
                    q.append((x, y))
        while q:
            x, y = q.popleft()
            i = self.idx(x, y)
            d = self.water_dist[i]
            for dx, dy in NEIGHBORS8:
                nx2, ny2 = x + dx, y + dy
                if not self.in_bounds(nx2, ny2):
                    continue
                j = self.idx(nx2, ny2)
                if TERRAIN[self.terrain[j]].passable and self.water_dist[j] > d + 1:
                    self.water_dist[j] = d + 1
                    self.water_src[j] = self.water_src[i]
                    q.append((nx2, ny2))

    # ------------------------------------------------------------- occupancy
    def place(self, animal, x: int, y: int):
        i = self.idx(x, y)
        assert self.occupant[i] is None, "cell already occupied"
        self.occupant[i] = animal
        animal.x, animal.y = x, y

    def move(self, animal, nx: int, ny: int):
        self.occupant[self.idx(animal.x, animal.y)] = None
        self.place(animal, nx, ny)

    def clear(self, animal):
        i = self.idx(animal.x, animal.y)
        if self.occupant[i] is animal:
            self.occupant[i] = None

    def random_free_cell(self, min_dist_from=(), min_dist=0):
        """A random unoccupied land cell, optionally far from given points."""
        for _ in range(4000):
            x = self.rng.randrange(self.w)
            y = self.rng.randrange(self.h)
            if not self.free(x, y):
                continue
            if min_dist and any(math.dist((x, y), p) < min_dist for p in min_dist_from):
                continue
            return x, y
        raise RuntimeError("could not find a free cell")

    # ------------------------------------------------------------- resources
    def add_carcass(self, x: int, y: int, energy: float):
        i = self.idx(x, y)
        self.carcasses[i] = self.carcasses.get(i, 0.0) + energy

    def update_resources(self):
        for i in self.veg_cells:
            if self.veg[i] < self.veg_max[i]:
                self.veg[i] = min(self.veg_max[i], self.veg[i] + C.VEG_REGROW_RATE)
        if self.carcasses:
            gone = []
            for i in self.carcasses:
                self.carcasses[i] -= C.CARCASS_DECAY
                if self.carcasses[i] <= 0:
                    gone.append(i)
            for i in gone:
                del self.carcasses[i]
