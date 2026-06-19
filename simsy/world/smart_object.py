"""Smart Objects, affordances, and the reservation lifecycle.

A Smart Object pushes interaction intelligence into the world: it *advertises*
how much it can satisfy a given need (object-advertised utility) and manages a
fixed number of interaction slots via the Reserve -> Travel -> Occupy -> Release
lifecycle (architecture doc 2C).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Affordance:
    """A need this object can satisfy, and by how much (per full interaction)."""

    need: str
    amount: float  # e.g. an espresso machine: Affordance("Caffeine", 40)


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
        self.id = obj_id
        self.kind = kind
        self.position = position
        self.affordances = {a.need: a for a in affordances}
        self.slots = slots
        self.interaction_ticks = interaction_ticks
        self.despawns = despawns  # reaching this object removes the agent (an exit)
        # agent_id -> True while reserved (claim made before pathfinding).
        self._reserved: dict[str, bool] = {}
        # agent_ids currently occupying a slot.
        self._occupants: set[str] = set()

    # --- advertising ------------------------------------------------------
    def advertises(self, need: str) -> bool:
        return need in self.affordances

    def advertised_amount(self, need: str) -> float:
        aff = self.affordances.get(need)
        return aff.amount if aff else 0.0

    @property
    def free_slots(self) -> int:
        return self.slots - len(self._reserved)

    def is_reserved_by(self, agent_id: str) -> bool:
        return agent_id in self._reserved

    # --- lifecycle --------------------------------------------------------
    def reserve(self, agent_id: str) -> bool:
        """Claim a slot before travelling. Idempotent for the same agent."""
        if agent_id in self._reserved:
            return True
        if self.free_slots <= 0:
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

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"SmartObject({self.id!r}, {self.kind!r}, "
            f"free={self.free_slots}/{self.slots})"
        )
