"""Smart Objects and their world-side capability components.

A Smart Object pushes interaction intelligence into the world: it *advertises*
how much it can satisfy a need (object-advertised utility) and manages a fixed
number of interaction slots via the Reserve -> Travel -> Occupy -> Release
lifecycle (architecture doc 2C).

In the entity-component model (§6D) a SmartObject is **not** a component — it is
an entity that holds world-side Capability components: `Affordance` (what it
satisfies) and `SlotSet` (how many can interact at once + the lifecycle). The
`SmartObject` class is the thin facade that bundles those onto an entity and
keeps the interaction API the BT leaves and utility scorer call.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..components import NavShape, RenderShape, Transform
from .entity import Entity


@dataclass
class Affordance:
    """A need this object can satisfy, and by how much (per full interaction)."""

    need: str
    amount: float  # e.g. an espresso machine: Affordance("Caffeine", 40)


class SlotSet:
    """Interaction-slot capability + the reservation lifecycle — the world-side
    mirror of an agent's claim on this object.

    Reserve (claim before pathfinding) -> Occupy (begin interacting, needs a
    prior reservation) -> Release (free, safe from OnAbort or on completion)."""

    def __init__(self, count: int) -> None:
        self.count = count
        # agent_id -> True while reserved (claim made before pathfinding).
        self._reserved: dict[str, bool] = {}
        # agent_ids currently occupying a slot.
        self._occupants: set[str] = set()

    @property
    def free(self) -> int:
        return self.count - len(self._reserved)

    def is_reserved_by(self, agent_id: str) -> bool:
        return agent_id in self._reserved

    def reserve(self, agent_id: str) -> bool:
        """Claim a slot before travelling. Idempotent for the same agent."""
        if agent_id in self._reserved:
            return True
        if self.free <= 0:
            return False
        self._reserved[agent_id] = True
        return True

    def occupy(self, agent_id: str) -> bool:
        """Begin interacting. Requires a prior reservation."""
        if agent_id not in self._reserved:
            return False
        self._occupants.add(agent_id)
        return True

    def release(self, agent_id: str) -> None:
        """Free the slot. Safe to call from OnAbort or on normal completion."""
        self._reserved.pop(agent_id, None)
        self._occupants.discard(agent_id)


class SmartObject:
    def __init__(
        self,
        obj_id: str,
        kind: str,
        position: tuple[float, float],
        affordances: list[Affordance],
        slots: int = 1,
        interaction_ticks: int = 20,
        despawns: bool = False,
    ) -> None:
        self.entity = Entity(
            obj_id,
            Transform(position),
            NavShape(static=True),  # fixtures are static; footprint TBD
            RenderShape(shape="box"),
        )
        self.kind = kind
        # World-side Capability components.
        self.affordances = {a.need: a for a in affordances}
        self.slot_set = self.entity.add(SlotSet(slots))
        self.interaction_ticks = interaction_ticks
        self.despawns = despawns  # reaching this object removes the agent (an exit)

    # --- pose accessors (single source of truth = the entity) -------------
    @property
    def id(self) -> str:
        return self.entity.id

    @property
    def position(self) -> tuple[float, float]:
        return self.entity.transform.position

    # --- advertising ------------------------------------------------------
    def advertises(self, need: str) -> bool:
        return need in self.affordances

    def advertised_amount(self, need: str) -> float:
        aff = self.affordances.get(need)
        return aff.amount if aff else 0.0

    # --- slots / lifecycle (delegated to the SlotSet component) -----------
    @property
    def slots(self) -> int:
        return self.slot_set.count

    @property
    def free_slots(self) -> int:
        return self.slot_set.free

    def is_reserved_by(self, agent_id: str) -> bool:
        return self.slot_set.is_reserved_by(agent_id)

    def reserve(self, agent_id: str) -> bool:
        return self.slot_set.reserve(agent_id)

    def occupy(self, agent_id: str) -> bool:
        return self.slot_set.occupy(agent_id)

    def release(self, agent_id: str) -> None:
        self.slot_set.release(agent_id)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"SmartObject({self.id!r}, {self.kind!r}, "
            f"free={self.free_slots}/{self.slots})"
        )
