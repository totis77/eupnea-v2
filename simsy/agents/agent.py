"""Agent: an entity assembled from components.

The agent composes an `Entity` (architecture doc §6) and attaches components:
- Representation: `Transform` (pose) + `NavShape` (footprint) + `RenderShape`
- Capability/State: `Drives` + `Locomotor` + `Blackboard`
- Controller: the pluggable Utility → BT brain (§6E)
`id`/`position`/`radius` are thin accessors onto the entity's Representation —
genuine pose access, the single source of truth lives on the components.

Cognition (Utility re-planning) and locomotion (ticking the active BT) are
deliberately separated so the LOD system can stagger thinking without
stuttering movement (architecture doc 2E): `think()` runs on a staggered
cadence and `act()` runs every tick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..ai.controller import Controller
from ..components import (
    Blackboard,
    Drives,
    Inventory,
    Locomotor,
    NavShape,
    RenderShape,
    Transform,
)
from ..config import UtilityCfg
from ..world.entity import Entity

if TYPE_CHECKING:
    from ..core.context import SimContext
    from ..world.registry import WorldRegistry


class Agent:
    def __init__(
        self,
        agent_id: str,
        position: tuple[float, float],
        needs: dict[str, float],
        need_growth: dict[str, float],
        speed: float = 4.0,
        think_period_ticks: int = 5,
        radius: float = 0.6,
        utility_cfg: UtilityCfg | None = None,
        controller: object | None = None,
        recipes: dict | None = None,
    ) -> None:
        self.entity = Entity(
            agent_id,
            Transform(position),
            NavShape(radius=radius, static=False),  # dynamic: feeds ORCA
            RenderShape(shape="circle"),
        )
        # Capability / State tier.
        self.drives = self.entity.add(Drives(dict(needs), dict(need_growth)))
        self.locomotor = self.entity.add(Locomotor(speed=speed))
        self.blackboard = self.entity.add(Blackboard())
        self.inventory = self.entity.add(Inventory())
        # Multi-step recipes: need -> ordered [Step]. Empty = single-interaction.
        self.recipes = recipes or {}
        # Controller tier (the brain). Defaults to Utility→BT; a different brain
        # (e.g. an FSM for staff) can be supplied — the engine only needs the
        # think/act + active_motive/active_node interface.
        self.think_period_ticks = think_period_ticks
        self.ucfg = utility_cfg or UtilityCfg()
        self.controller = self.entity.add(controller or Controller(self.ucfg))

    # --- pose accessors (single source of truth = the entity) -------------
    @property
    def id(self) -> str:
        return self.entity.id

    @property
    def position(self) -> tuple[float, float]:
        return self.entity.transform.position

    @position.setter
    def position(self, value: tuple[float, float]) -> None:
        self.entity.transform.position = value

    @property
    def radius(self) -> float:
        return self.entity.navshape.radius

    # --- per-tick updates -------------------------------------------------
    def update_needs(self, ctx: "SimContext") -> None:
        self.drives.update(ctx.dt)

    def should_think(self, ctx: "SimContext") -> bool:
        # Stagger by agent id hash so the think-budget spreads across ticks.
        offset = sum(ord(c) for c in self.id) % self.think_period_ticks
        return ctx.tick % self.think_period_ticks == offset

    # --- cognition (staggered) -------------------------------------------
    def think(self, world: "WorldRegistry", ctx: "SimContext") -> None:
        self.controller.think(self, world, ctx)

    # --- locomotion / execution (every tick) ------------------------------
    def act(self, world: "WorldRegistry", ctx: "SimContext") -> None:
        self.controller.act(self, world, ctx)

    # --- introspection (for the snapshot emitter) -------------------------
    @property
    def active_motive(self) -> str | None:
        return self.controller.active_motive

    @property
    def active_node(self) -> str | None:
        return self.controller.active_node

    @property
    def plan_view(self) -> dict | None:
        fn = getattr(self.controller, "plan_view", None)
        return fn() if fn is not None else None
