"""Finite-State-Machine controller — a pluggable brain (architecture doc §6E).

An `FSM` is a drop-in alternative to the default Utility→BT `Controller`: it
exposes the same `think`/`act` interface the engine ticks and the same
`active_motive`/`active_node` introspection, so an entity can swap one for the
other with no engine change. Each tick, the current state's handler runs and may
return the name of the next state.

`serve_fsm` is the staff brain for operating a `ServicePoint` (`idle → brewing`):
a barista picks the next pending order, brews it for a fixed time, marks it ready,
and loops. It reads its assigned station from the agent's blackboard, so the same
controller serves any ServicePoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..core.context import SimContext
    from ..world.registry import WorldRegistry

# A state handler inspects the agent and returns the next state name, or None to stay.
StateFn = Callable[["Agent", "WorldRegistry", "SimContext"], "str | None"]


class FSM:
    def __init__(self, initial: str, states: dict[str, StateFn]) -> None:
        self.state = initial
        self._states = states

    def think(self, agent: "Agent", world: "WorldRegistry", ctx: "SimContext") -> None:
        pass  # FSMs do their work every tick in act(); nothing to re-plan

    def act(self, agent: "Agent", world: "WorldRegistry", ctx: "SimContext") -> None:
        handler = self._states.get(self.state)
        if handler is None:
            return
        nxt = handler(agent, world, ctx)
        if nxt is not None:
            self.state = nxt

    # --- introspection (mirrors Controller, for the snapshot emitter) -----
    @property
    def active_motive(self) -> str | None:
        return self.state

    @property
    def active_node(self) -> str | None:
        return self.state

    def plan_view(self) -> dict:
        """One-node view (the current state) so the viewer renders staff too."""
        return {"name": "fsm", "active_index": 0, "children": [{"name": self.state}]}


def serve_fsm(brew_ticks: int) -> FSM:
    """A server brain: brew the station's orders one at a time. The agent's
    blackboard must carry `station` (a ServicePoint)."""

    def idle(agent: "Agent", world: "WorldRegistry", ctx: "SimContext") -> "str | None":
        station = agent.blackboard.get("station")
        if station is None:
            return None
        guest_id = station.next_order()
        if guest_id is None:
            return None
        station.begin(guest_id)
        agent.blackboard["serving"] = guest_id
        agent.blackboard["brew_left"] = brew_ticks
        return "brewing"

    def brewing(agent: "Agent", world: "WorldRegistry", ctx: "SimContext") -> "str | None":
        agent.blackboard["brew_left"] -= 1
        if agent.blackboard["brew_left"] <= 0:
            station = agent.blackboard["station"]
            station.mark_ready(agent.blackboard.pop("serving"))
            return "idle"
        return None

    return FSM("idle", {"idle": idle, "brewing": brewing})
