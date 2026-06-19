"""Micro-scene isolating the ServicePoint + staff feature.

One staffed espresso counter (a register line that feeds a ServicePoint), an
optional barista driven by an FSM, a pickup spot, and a few guests that order
then collect, then leave. Toggling `with_barista` shows the dependency: with no
server, orders pile up and nobody is served.
"""

from __future__ import annotations

from simsy.agents.agent import Agent
from simsy.ai.fsm import serve_fsm
from simsy.components import Role
from simsy.config import Config
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.sim import Simulation
from simsy.world.registry import WorldRegistry
from simsy.world.smart_object import Affordance, SmartObject


def build(
    config: Config | None = None,
    seed: int = 0,
    n_agents: int = 3,
    with_barista: bool = True,
) -> Simulation:
    cfg = config or Config()
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    counter = SmartObject(
        "counter", "CoffeeCounter", (8.0, 0.0),
        [Affordance("Caffeine", 40.0)], slots=1,
    )
    counter.enable_queue(direction=(-1.0, 0.0), spacing=1.5, gap=2.0)  # register line
    counter.enable_service(pickup_offset=(0.0, -3.0))                  # needs a barista
    world.add(counter)
    world.add(
        SmartObject(
            "exit", "Exit", (-10.0, 0.0),
            [Affordance("Leave", 100.0)], slots=8, interaction_ticks=1, despawns=True,
        )
    )

    grid = NavGrid(-12.0, -12.0, 12.0, 12.0, cell=1.0, inflate=cfg.agent.radius)

    agents: list[Agent] = []
    if with_barista:
        # A staff agent with NO Drives/Utility — driven purely by an FSM. This is
        # the proof that the Controller slot is pluggable: same Agent, different brain.
        barista = Agent(
            "barista", (10.0, 0.0), {}, {},
            speed=cfg.agent.speed, radius=cfg.agent.radius,
            think_period_ticks=1, controller=serve_fsm(brew_ticks=15),
        )
        barista.entity.add(Role("barista"))
        barista.blackboard["station"] = counter.service_point
        agents.append(barista)

    # Guests want Caffeine first, with a growing Leave so they depart after pickup.
    agents += [
        Agent(
            f"q{i}", (-8.0, (i - (n_agents - 1) / 2) * 2.0),
            {"Caffeine": 55.0 - i, "Leave": 0.0}, {"Caffeine": 0.0, "Leave": 2.5},
            speed=cfg.agent.speed, radius=cfg.agent.radius,
            think_period_ticks=1, utility_cfg=cfg.utility,
        )
        for i in range(n_agents)
    ]
    return Simulation(ctx, world, agents, grid, spawner=None, config=cfg)
