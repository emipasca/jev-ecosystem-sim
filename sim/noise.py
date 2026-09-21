"""Tiny self-contained value-noise implementation (no dependencies).

Smoothly interpolated lattice noise plus fractal Brownian motion (fbm) for
layered detail. Good enough for coastlines, moisture and vegetation clumping.
"""

import math
import random


class ValueNoise:
    def __init__(self, seed: int):
        rnd = random.Random(seed)
        perm = list(range(256))
        rnd.shuffle(perm)
        self.perm = perm + perm

    def _lattice(self, xi: int, yi: int) -> float:
        return self.perm[(self.perm[xi & 255] + yi) & 255] / 255.0

    def noise2(self, x: float, y: float) -> float:
        """Smooth value noise in roughly [0, 1]."""
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        u = xf * xf * (3.0 - 2.0 * xf)  # smoothstep
        v = yf * yf * (3.0 - 2.0 * yf)
        a = self._lattice(xi, yi)
        b = self._lattice(xi + 1, yi)
        c = self._lattice(xi, yi + 1)
        d = self._lattice(xi + 1, yi + 1)
        return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v

    def fbm(self, x: float, y: float, octaves: int = 4,
            lacunarity: float = 2.0, gain: float = 0.5) -> float:
        """Fractal sum of noise2 octaves, normalized to roughly [0, 1]."""
        total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
        for _ in range(octaves):
            total += amp * self.noise2(x * freq, y * freq)
            norm += amp
            amp *= gain
            freq *= lacunarity
        return total / norm
