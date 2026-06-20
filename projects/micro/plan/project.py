"""Micro-scene isolating multi-step plans.

The Caffeine goal is no longer satisfied in one stop: a guest must **order a
coffee at the staffed counter** (acquiring a carried item), then **walk to a
seat and drink it** (consuming the item to satisfy Caffeine). This exercises a
scripted recipe across two objects plus an Inventory item carried between them.
"""

from __future__ import annotations

from simsy.agents.agent import Agent
from simsy.ai.fsm import serve_fsm
from simsy.ai.plan import Step
from simsy.components import Role
from simsy.config import Config
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.sim import Simulation
from simsy.world.registry import WorldRegistry
from simsy.world.smart_object import Affordance, SmartObject

# "Have a coffee" = get one at the counter, then drink it seated.
COFFEE_RECIPE = [
    Step(tag="sells:coffee", action="acquire", item="coffee"),
    Step(tag="seat", action="consume", item="coffee", amount=40.0),
]


def build(
    config: Config | None = None,
    seed: int = 0,
    n_agents: int = 3,
    with_barista: bool = True,
) -> Simulation:
    cfg = config or Config()
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    # The counter advertises Caffeine (so the drive routes guests here) but does
    # not satisfy it directly — it *sells* coffee (a staffed ServicePoint).
    counter = SmartObject(
        "counter", "CoffeeCounter", (8.0, 0.0),
        [Affordance("Caffeine", 40.0)], slots=1, tags={"sells:coffee"},
    )
    counter.enable_queue(direction=(-1.0, 0.0), spacing=1.5, gap=2.0)
    counter.enable_service(pickup_offset=(0.0, -3.0))
    world.add(counter)
    # A seat: found by tag, not by need — just a place to sit and consume.
    world.add(SmartObject("seat", "Chair", (0.0, -5.0), [], slots=3, tags={"seat"}))
    world.add(
        SmartObject(
            "exit", "Exit", (-10.0, 0.0),
            [Affordance("Leave", 100.0)], slots=8, interaction_ticks=1, despawns=True,
        )
    )

    grid = NavGrid(-12.0, -12.0, 12.0, 12.0, cell=1.0, inflate=cfg.agent.radius)

    agents: list[Agent] = []
    if with_barista:
        barista = Agent(
            "barista", (10.0, 0.0), {}, {},
            speed=cfg.agent.speed, radius=cfg.agent.radius,
            think_period_ticks=1, controller=serve_fsm(brew_ticks=12),
        )
        barista.entity.add(Role("barista"))
        barista.blackboard["station"] = counter.service_point
        agents.append(barista)

    agents += [
        Agent(
            f"q{i}", (-8.0, (i - (n_agents - 1) / 2) * 2.0),
            # Leave grows slowly so a guest stays patient through the longer
            # two-object plan, then heads out once Caffeine is satisfied.
            {"Caffeine": 55.0 - i, "Leave": 0.0}, {"Caffeine": 0.0, "Leave": 1.0},
            speed=cfg.agent.speed, radius=cfg.agent.radius,
            think_period_ticks=1, utility_cfg=cfg.utility,
            recipes={"Caffeine": COFFEE_RECIPE},
        )
        for i in range(n_agents)
    ]
    return Simulation(ctx, world, agents, grid, spawner=None, config=cfg)
