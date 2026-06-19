"""Micro-scene isolating Groups.

A handful of agents share a `group_id` and head for the same exit. The Locomotion
system steers each toward the group's centroid, so they cross the room together
as a cluster rather than fanning out into independent lines.
"""

from __future__ import annotations

from simsy.agents.agent import Agent
from simsy.config import Config
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.sim import Simulation
from simsy.world.registry import WorldRegistry
from simsy.world.smart_object import Affordance, SmartObject


def build(config: Config | None = None, seed: int = 0, group_size: int = 4) -> Simulation:
    cfg = config or Config()
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    world.add(
        SmartObject(
            "exit", "Exit", (12.0, 0.0), [Affordance("Leave", 100.0)],
            slots=12, interaction_ticks=1, despawns=True,
        )
    )
    grid = NavGrid(-16.0, -12.0, 16.0, 12.0, cell=1.0, inflate=cfg.agent.radius)

    agents = [
        Agent(
            f"m{i}", (-12.0, (i - (group_size - 1) / 2) * 2.5),
            {"Leave": 50.0}, {"Leave": 1.0},
            speed=cfg.agent.speed, radius=cfg.agent.radius,
            think_period_ticks=1, utility_cfg=cfg.utility, group_id="group1",
        )
        for i in range(group_size)
    ]
    return Simulation(ctx, world, agents, grid, spawner=None, config=cfg)
