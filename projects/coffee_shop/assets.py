"""Coffee-shop resources: reusable object *kinds* and the guest archetype.

These are the project's "assets" — templates that compose engine mechanics
(`SmartObject` + `Affordance`, `AgentArchetype`) into the things this scene is
built from. The scene (`project.py`) places *instances* of them. Keeping kinds
here, separate from placement, is the seam the future authoring tool edits:
an asset library on one side, a scene graph on the other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from simsy.agents.spawning import AgentArchetype
from simsy.world.smart_object import Affordance, SmartObject

if TYPE_CHECKING:
    from simsy.config import Config


def espresso_counter(obj_id: str, position: tuple[float, float]) -> SmartObject:
    """A 1-slot counter that satisfies Caffeine over a 20-tick interaction.
    Contended, so it has a waiting line trailing toward the room (-x)."""
    so = SmartObject(
        obj_id, "CoffeeCounter", position,
        [Affordance("Caffeine", 40.0)], slots=1, interaction_ticks=20,
    )
    so.enable_queue(direction=(-1.0, 0.0), spacing=1.5, gap=2.0)
    return so


def couch(obj_id: str, position: tuple[float, float]) -> SmartObject:
    """A 2-slot seat that satisfies Rest over a 15-tick interaction."""
    return SmartObject(
        obj_id, "Chair", position,
        [Affordance("Rest", 30.0)], slots=2, interaction_ticks=15,
    )


def exit_door(obj_id: str, position: tuple[float, float]) -> SmartObject:
    """The exit: reaching it satisfies Leave and despawns the agent. Plenty of
    slots so departure never blocks."""
    return SmartObject(
        obj_id, "Exit", position,
        [Affordance("Leave", 100.0)], slots=12, interaction_ticks=1, despawns=True,
    )


def guest_archetype(cfg: "Config") -> AgentArchetype:
    """The default guest template, parameterized from subsystem config."""
    return AgentArchetype(
        name="guest",
        needs=dict(cfg.archetype.needs),
        growth=dict(cfg.archetype.growth),
        speed=cfg.agent.speed,
        radius=cfg.agent.radius,
        think_period_ticks=cfg.agent.think_period_ticks,
        spread=cfg.population.need_spread,
        utility_cfg=cfg.utility,
    )
