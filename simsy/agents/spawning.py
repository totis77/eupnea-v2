"""Agent archetypes (flyweights) and seed-driven spawn scheduling.

An `AgentArchetype` is the shared, immutable template for a kind of agent
(its base drives, growth rates, speed); `spawn()` stamps out an instance with
rng-varied initial needs. The `Spawner` adds instances at an entrance on a
deterministic, seeded inter-arrival schedule up to a population cap.

Determinism: all randomness is drawn from the simulation's seeded RNG
(`ctx.rng`), so the entire population timeline replays identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..config import UtilityCfg
from .agent import Agent

if TYPE_CHECKING:
    import random

    from ..core.context import SimContext


@dataclass(frozen=True)
class AgentArchetype:
    name: str
    needs: dict[str, float]
    growth: dict[str, float]
    speed: float = 4.0
    radius: float = 0.6
    think_period_ticks: int = 5
    spread: float = 12.0  # +/- jitter applied to non-"Leave" initial needs
    utility_cfg: UtilityCfg | None = None
    recipes: dict | None = None  # multi-step recipes per need (e.g. how to get Caffeine)
    with_mood: bool = False      # give spawned agents a Mood (stress/impatience)

    def spawn(self, agent_id: str, pos: tuple[float, float], rng: "random.Random") -> Agent:
        needs = {}
        for k, base in self.needs.items():
            jitter = 0.0 if k == "Leave" else rng.uniform(-self.spread, self.spread)
            needs[k] = max(0.0, min(100.0, base + jitter))
        return Agent(
            agent_id, pos, needs, dict(self.growth),
            speed=self.speed,
            think_period_ticks=self.think_period_ticks,
            radius=self.radius,
            utility_cfg=self.utility_cfg,
            recipes=self.recipes,
            with_mood=self.with_mood,
        )


@dataclass
class Spawner:
    archetype: AgentArchetype
    entrance: tuple[float, float]
    max_population: int
    interval_ticks: tuple[int, int] = (15, 45)  # min/max ticks between arrivals
    _count: int = field(default=0, init=False)
    _next_tick: int = field(default=0, init=False)

    def prefill(self, agents: list[Agent], ctx: "SimContext", count: int) -> None:
        """Place `count` agents immediately (the population present at tick 0)."""
        for _ in range(min(count, self.max_population - len(agents))):
            agents.append(self._spawn(ctx))

    def update(self, agents: list[Agent], ctx: "SimContext") -> None:
        """Spawn at most one agent this tick if the schedule and cap allow."""
        if ctx.tick < self._next_tick:
            return
        if len(agents) < self.max_population:
            agents.append(self._spawn(ctx))
        lo, hi = self.interval_ticks
        self._next_tick = ctx.tick + ctx.rng.randint(lo, hi)

    def _spawn(self, ctx: "SimContext") -> Agent:
        ex, ey = self.entrance
        pos = (ex, ey + ctx.rng.uniform(-3.0, 3.0))  # fan out at the door
        agent_id = f"{self.archetype.name}{self._count:03d}"
        self._count += 1
        return self.archetype.spawn(agent_id, pos, ctx.rng)
