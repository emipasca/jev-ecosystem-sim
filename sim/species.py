"""Species trait tables (constant per species). Values from DESIGN.md's v1 table."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Species:
    name: str
    color: str                  # UI dot colour
    diet: tuple = ()            # species names it hunts
    threats: tuple = ()         # species names it fears when detected
    herbivore: bool = False     # grazes vegetation
    scavenger: bool = False     # eats carcasses
    hunts_weak_only: bool = False  # only injured/juvenile prey (jackal)
    mass: float = 0.0           # adult size; the master trait
    top_speed: float = 0.0      # world-points/tick at peak condition
    stamina_max: float = 0.0
    health_max: float = 0.0
    exertion: float = 0.0       # peak power; overpower term in hunts, sprint boost
    energy_cap: float = 0.0
    metabolism: float = 0.0     # base energy drain per tick (scaled by config)
    vision: float = 0.0         # vision radius in cells (terrain-modified)
    heal_rate: float = 0.0      # health per resting tick
    maturity_age: int = 0       # ticks to adulthood
    lifespan: int = 0           # ticks
    repro_cooldown: int = 0     # ticks between breeding
    # social: while wandering/searching, drift toward same-species company up to a
    # comfort count, and spread out when more crowded than that.
    social_radius: float = 0.0   # cells within which same-species neighbours count
    social_comfort: int = 0      # preferred number of nearby same-species animals
    social_cohesion: float = 0.0  # pull toward the group when under comfort
    social_separation: float = 0.0  # push away when over comfort


SPECIES = {
    "gazelle": Species(
        name="gazelle", color="#f0e3bc",
        diet=(), threats=("lion", "jackal"), herbivore=True,
        mass=30, top_speed=9, stamina_max=90, health_max=40, exertion=30,
        energy_cap=60, metabolism=1.0, vision=22,
        heal_rate=0.25, maturity_age=350, lifespan=5000, repro_cooldown=220,
        social_radius=14, social_comfort=12, social_cohesion=0.9, social_separation=0.2,
    ),
    "lion": Species(
        name="lion", color="#e0862e",
        diet=("gazelle",), scavenger=True,
        mass=190, top_speed=11, stamina_max=45, health_max=100, exertion=95,
        energy_cap=200, metabolism=2.5, vision=18,
        heal_rate=0.35, maturity_age=900, lifespan=8000, repro_cooldown=700,
        social_radius=16, social_comfort=2, social_cohesion=0.5, social_separation=0.8,
    ),
    "jackal": Species(
        name="jackal", color="#4c4a55",
        diet=("gazelle",), threats=("lion",), scavenger=True, hunts_weak_only=True,
        mass=15, top_speed=8, stamina_max=70, health_max=30, exertion=20,
        energy_cap=45, metabolism=0.8, vision=20,
        heal_rate=0.2, maturity_age=300, lifespan=4000, repro_cooldown=400,
        social_radius=14, social_comfort=3, social_cohesion=0.4, social_separation=0.5,
    ),
}
