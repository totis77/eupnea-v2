"""Shared per-run simulation context: clock, seeded RNG, and event bus.

Everything that needs time, randomness, or events takes a SimContext rather
than reaching for wall-clock time or the global `random` module. This is the
single choke point that makes replay deterministic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .events import EventBus


@dataclass
class SimContext:
    seed: int
    dt: float = 0.1  # fixed timestep in seconds (10 ticks/sec by default)
    tick: int = 0
    rng: random.Random = field(init=False)
    events: EventBus = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.events = EventBus()

    @property
    def time(self) -> float:
        """Simulated seconds elapsed since tick 0."""
        return self.tick * self.dt
