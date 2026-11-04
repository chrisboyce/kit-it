"""Stable randomness, so one model can have variety without any two prints differing.

Vary(p, "planter2") gives the same draws on every build, because the stream comes from
the kit's variation_seed and that key, not from the clock. Keying by name, not by order,
means adding a part or a draw elsewhere doesn't reshuffle anything else.

Every draw names its nominal value, and p.variety scales the distance from it: 0 gives
the plain template everywhere, 1 the full range. Stay inside what the part's fit and
neighbors allow; the collision and connectivity checks catch what doesn't.
"""

import random


class Vary:
    def __init__(self, p, *key):
        self.amount = p.variety
        self.rng = random.Random("/".join(map(str, (p.variation_seed, *key))))

    def between(self, lo, hi, nominal):
        return nominal + self.amount * (self.rng.uniform(lo, hi) - nominal)

    def chance(self, probability):
        """Only ever true with some variety on, so the default stays the template."""
        return self.rng.random() < probability * self.amount

    def pick(self, options):
        """options[0] is the nominal."""
        choice = self.rng.choice(options)
        return choice if self.amount > 0 else options[0]
