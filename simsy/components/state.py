"""Capability / State components — the middle tier (architecture doc §6D).

These hold what an entity *has and knows* (data), as opposed to the
Representation tier (pose + shapes, read by systems and the viewer) and the
Controller tier (the brain that *drives* the entity). Both engine systems and
the controller read these.

This module covers the **agent-side** capability components. World-side
capability components (`Affordance`, `SlotSet`) live with the smart object.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class Blackboard(dict):
    """Scratch memory shared between an entity's controller and its BT leaves
    (e.g. the active interaction target, occupy timers). A plain ``dict``
    subclass so existing ``.get``/``.pop``/``[]`` access is unchanged."""


@dataclass
class Drives:
    """An agent's internal needs (0..100, higher = more pressing) and the rate
    each grows, in units per second. The Utility selector scores these against
    the affordances advertised in the world."""

    needs: dict[str, float]
    growth: dict[str, float]

    def update(self, dt: float) -> None:
        """Grow each need by its rate, clamped to 100."""
        for need, rate in self.growth.items():
            self.needs[need] = min(100.0, self.needs[need] + rate * dt)


@dataclass
class Locomotor:
    """Movement capability plus the live navigation goal/path state that the
    Locomotion system reads and integrates each tick.

    Physical footprint (``radius``) and pose (``position``) are
    Representation-tier (`NavShape`/`Transform`), not here — this component is
    purely the *capability to move* and the *intent* of where to."""

    speed: float = 4.0
    goal: tuple[float, float] | None = None
    path: list[tuple[float, float]] | None = None
    path_idx: int = 0
    vel: tuple[float, float] = (0.0, 0.0)
    at_goal: bool = False

    def set_goal(self, pos: tuple[float, float]) -> None:
        """Request travel to ``pos``; invalidates the path only if it changed."""
        if self.goal != pos:
            self.goal = pos
            self.path = None
            self.path_idx = 0
            self.at_goal = False

    def clear_goal(self) -> None:
        self.goal = None
        self.path = None
        self.path_idx = 0
        self.vel = (0.0, 0.0)
        self.at_goal = False


@dataclass
class Role:
    """What an agent *is* in the scenario — e.g. "guest" or "barista". Staff
    carry a role and a non-Utility controller (an FSM); the role is the marker
    systems/queries use to tell staff from patrons."""

    name: str


@dataclass
class Inventory:
    """What an agent is carrying. Multi-step plans move items between objects —
    e.g. a coffee acquired at the counter and consumed at a seat."""

    items: set[str] = field(default_factory=set)

    def add(self, item: str) -> None:
        self.items.add(item)

    def remove(self, item: str) -> None:
        self.items.discard(item)

    def has(self, item: str) -> bool:
        return item in self.items
