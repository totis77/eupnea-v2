"""Café resources: object kinds, the guest archetype, and the barista factory.

Composes engine mechanics into the café's building blocks. The guest's "have a
coffee" goal is a two-step recipe (order at the counter → drink it at a seat);
baristas are FSM-driven staff that brew the counter's orders.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from simsy.agents.agent import Agent
from simsy.agents.spawning import AgentArchetype
from simsy.ai.fsm import serve_fsm
from simsy.ai.plan import Step
from simsy.components import Role
from simsy.world.smart_object import Affordance, SmartObject

if TYPE_CHECKING:
    from simsy.config import Config
    from simsy.world.smart_object import ServicePoint

# Have a coffee = order one at the counter (carry it), then drink it at a seat.
COFFEE_RECIPE = [
    Step(tag="sells:coffee", action="acquire", item="coffee"),
    Step(tag="seat", action="consume", item="coffee", amount=45.0),
]


def coffee_counter(obj_id: str, position: tuple[float, float]) -> SmartObject:
    """A staffed register: advertises Caffeine (so the drive routes here), holds
    an order queue and a ServicePoint a barista fulfills."""
    so = SmartObject(
        obj_id, "CoffeeCounter", position,
        [Affordance("Caffeine", 45.0)], slots=3, tags={"sells:coffee"},
    )
    so.enable_queue(direction=(-1.0, 0.0), spacing=1.5, gap=2.0)
    so.enable_service(pickup_offset=(0.0, -4.0))
    return so


def seating(obj_id: str, kind: str, position: tuple[float, float], slots: int) -> SmartObject:
    """A place to sit and consume a carried item — located by the `seat` tag."""
    return SmartObject(obj_id, kind, position, [], slots=slots, tags={"seat"})


def toilet(obj_id: str, position: tuple[float, float], slots: int = 2) -> SmartObject:
    """Self-service: satisfies the Bladder need over a short interaction."""
    return SmartObject(
        obj_id, "Toilet", position, [Affordance("Bladder", 100.0)],
        slots=slots, interaction_ticks=15,
    )


def exit_door(obj_id: str, position: tuple[float, float]) -> SmartObject:
    return SmartObject(
        obj_id, "Exit", position, [Affordance("Leave", 100.0)],
        slots=12, interaction_ticks=1, despawns=True,
    )


def guest_archetype(cfg: "Config") -> AgentArchetype:
    """A café guest: wants coffee (via the recipe), occasionally the toilet, and
    eventually to leave."""
    return AgentArchetype(
        name="guest",
        needs={"Caffeine": 60.0, "Bladder": 0.0, "Leave": 0.0},
        growth={"Caffeine": 1.0, "Bladder": 1.2, "Leave": 0.6},
        speed=cfg.agent.speed,
        radius=cfg.agent.radius,
        think_period_ticks=cfg.agent.think_period_ticks,
        spread=cfg.population.need_spread,
        utility_cfg=cfg.utility,
        recipes={"Caffeine": COFFEE_RECIPE},
    )


def barista(agent_id: str, position: tuple[float, float], station: "ServicePoint", cfg: "Config") -> Agent:
    """Staff: an FSM-driven server (no Drives/Utility) working `station`."""
    b = Agent(
        agent_id, position, {}, {},
        speed=cfg.agent.speed, radius=cfg.agent.radius,
        think_period_ticks=1, controller=serve_fsm(brew_ticks=12),
    )
    b.entity.add(Role("barista"))
    b.blackboard["station"] = station
    return b
