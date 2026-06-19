"""Micro-scene isolating Mood/affect.

A single slow counter forces a line. Guests carry a `Mood`: stress climbs while
they wait in the queue and bleeds off otherwise, and stress feeds their Leave
drive — so a guest stuck waiting grows impatient and is likelier to give up.
"""

from __future__ import annotations

from simsy.agents.agent import Agent
from simsy.config import Config
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.sim import Simulation
from simsy.world.registry import WorldRegistry
from simsy.world.smart_object import Affordance, SmartObject


def build(config: Config | None = None, seed: int = 0, n_agents: int = 5) -> Simulation:
    cfg = config or Config()
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    counter = SmartObject(
        "counter", "CoffeeCounter", (8.0, 0.0),
        [Affordance("Caffeine", 40.0)], slots=1, interaction_ticks=25,
    )
    counter.enable_queue(direction=(-1.0, 0.0), spacing=1.5, gap=2.0)
    world.add(counter)
    world.add(SmartObject(
        "exit", "Exit", (-10.0, 0.0), [Affordance("Leave", 100.0)],
        slots=8, interaction_ticks=1, despawns=True,
    ))

    grid = NavGrid(-12.0, -12.0, 12.0, 12.0, cell=1.0, inflate=cfg.agent.radius)

    agents = [
        Agent(
            f"q{i}", (-8.0, (i - (n_agents - 1) / 2) * 2.0),
            {"Caffeine": 55.0 - i, "Leave": 0.0}, {"Caffeine": 0.0, "Leave": 0.5},
            speed=cfg.agent.speed, radius=cfg.agent.radius,
            think_period_ticks=1, utility_cfg=cfg.utility, with_mood=True,
        )
        for i in range(n_agents)
    ]
    return Simulation(ctx, world, agents, grid, spawner=None, config=cfg)
