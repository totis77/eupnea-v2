"""Micro-scene isolating Portals / multi-venue.

Two rooms separated by a solid, gapless wall — A* cannot route between them. A
portal in room A links to room B, where the coffee is. Guests want Caffeine; the
recipe sends them through the portal first ("the coffee's next door"), then to
the counter. Crossing to x > 0 is therefore only possible via the portal.
"""

from __future__ import annotations

from simsy.agents.agent import Agent
from simsy.ai.plan import Step
from simsy.config import Config
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.sim import Simulation
from simsy.world.registry import WorldRegistry
from simsy.world.smart_object import Affordance, SmartObject

# Coffee is in the other venue: go through the portal, then use the counter.
COFFEE_NEXT_DOOR = [
    Step(tag="portal", action="enter"),
    Step(tag="cafe", action="use"),
]


def build(config: Config | None = None, seed: int = 0, n_agents: int = 2) -> Simulation:
    cfg = config or Config()
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    # Room B (right): the coffee counter and an exit.
    world.add(SmartObject(
        "cafe", "CoffeeCounter", (8.0, 0.0), [Affordance("Caffeine", 40.0)],
        slots=3, interaction_ticks=15, tags={"cafe"},
    ))
    world.add(SmartObject(
        "exitB", "Exit", (8.0, -5.0), [Affordance("Leave", 100.0)],
        slots=8, interaction_ticks=1, despawns=True,
    ))
    # Room A (left): a portal linking across the wall into room B.
    portal = SmartObject("portalA", "Portal", (-3.0, 0.0), [], slots=4, tags={"portal"})
    portal.enable_portal(target=(3.0, 0.0))
    world.add(portal)

    grid = NavGrid(-14.0, -8.0, 14.0, 8.0, cell=1.0, inflate=cfg.agent.radius)
    grid.add_obstacle(-0.6, -8.0, 0.6, 8.0)  # full-height wall, no gap

    agents = [
        Agent(
            f"g{i}", (-10.0, (i - (n_agents - 1) / 2) * 2.0),
            {"Caffeine": 55.0 - i, "Leave": 0.0}, {"Caffeine": 0.0, "Leave": 1.0},
            speed=cfg.agent.speed, radius=cfg.agent.radius,
            think_period_ticks=1, utility_cfg=cfg.utility,
            recipes={"Caffeine": COFFEE_NEXT_DOOR},
        )
        for i in range(n_agents)
    ]
    return Simulation(ctx, world, agents, grid, spawner=None, config=cfg)
