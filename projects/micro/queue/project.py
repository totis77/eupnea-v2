"""Micro-scene isolating the Queue feature.

One 1-slot espresso counter with a waiting line, a far exit, and a handful of
agents that want Caffeine first and then to Leave. A line forms and serializes
through the single slot; once served, an agent's Leave drive dominates and it
vacates to the exit (so it doesn't squat on the slot and block the next in line).
No walls, nothing else — the "test a feature without building the whole
environment" workflow: a feature gets its own minimal project.
"""

from __future__ import annotations

from simsy.agents.agent import Agent
from simsy.config import Config
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.sim import Simulation
from simsy.world.registry import WorldRegistry
from simsy.world.smart_object import Affordance, SmartObject


def build(config: Config | None = None, seed: int = 0, n_agents: int = 3) -> Simulation:
    cfg = config or Config()  # engine defaults; no project config needed
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    counter = SmartObject(
        "counter", "CoffeeCounter", (8.0, 0.0),
        [Affordance("Caffeine", 40.0)], slots=1, interaction_ticks=10,
    )
    counter.enable_queue(direction=(-1.0, 0.0), spacing=1.5, gap=2.0)
    world.add(counter)
    world.add(
        SmartObject(
            "exit", "Exit", (-10.0, 0.0),
            [Affordance("Leave", 100.0)], slots=8, interaction_ticks=1, despawns=True,
        )
    )

    grid = NavGrid(-12.0, -12.0, 12.0, 12.0, cell=1.0, inflate=cfg.agent.radius)

    # Each wants Caffeine first (high, no growth so it only drains by serving),
    # with a steadily-growing Leave. Start ~55 so one 40-unit serving drops
    # Caffeine below the idle threshold; by then Leave dominates and the agent
    # departs, vacating the slot for the next in line. Slightly different starts
    # keep selection deterministic; they think every tick so the line forms fast.
    agents = [
        Agent(
            f"q{i}", (-8.0, (i - (n_agents - 1) / 2) * 2.0),
            {"Caffeine": 55.0 - i, "Leave": 0.0}, {"Caffeine": 0.0, "Leave": 2.5},
            speed=cfg.agent.speed, radius=cfg.agent.radius,
            think_period_ticks=1, utility_cfg=cfg.utility,
        )
        for i in range(n_agents)
    ]
    return Simulation(ctx, world, agents, grid, spawner=None, config=cfg)
