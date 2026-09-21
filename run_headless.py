#!/usr/bin/env python3
"""Run the ecosystem headless and print population dynamics.

Usage: python3 run_headless.py [--ticks 600] [--seed 7] [--every 25]
"""

import argparse
import time

from sim.engine import Simulation


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=600)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--every", type=int, default=25)
    args = ap.parse_args()

    sim = Simulation(seed=args.seed)
    total_veg0 = sum(sim.world.veg)
    print(f"island seeded: {sum(1 for t in sim.world.terrain if t != 0)} land cells, "
          f"{len(sim.world.veg_cells)} vegetated, initial biomass {total_veg0:,.0f}")
    header = f"{'tick':>5} {'gazelle':>8} {'lion':>5} {'jackal':>7} {'carcass':>8} {'veg':>10}"
    print(header)

    start = time.time()
    for t in range(args.ticks + 1):
        if t % args.every == 0:
            pop = sim.population()
            print(f"{sim.tick_count:>5} {pop.get('gazelle', 0):>8} {pop.get('lion', 0):>5} "
                  f"{pop.get('jackal', 0):>7} {len(sim.world.carcasses):>8} "
                  f"{sum(sim.world.veg):>10,.0f}")
        if t < args.ticks:
            sim.step()
    elapsed = time.time() - start

    print(f"\n{args.ticks} ticks in {elapsed:.1f}s ({args.ticks / elapsed:.1f} ticks/s)")
    print("births:", dict(sim.stats["births"]))
    print("kills :", dict(sim.stats["kills"]))
    print("deaths:", dict(sim.stats["deaths"]))


if __name__ == "__main__":
    main()
