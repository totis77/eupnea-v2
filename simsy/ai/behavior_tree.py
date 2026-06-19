"""Minimal Behavior Tree runner (the "how to do it").

This slice implements just enough of a BT to execute the smart-object
interaction sequence with cross-tick RUNNING state and a guaranteed clean-up
path on abort (architecture doc 2B/2C):

    Sequence[ Reserve -> Travel -> Occupy -> Release ]

Leaf nodes read their target from the agent blackboard under "target", so the
same tree definition works for any object satisfying the active motive.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..core.context import SimContext


class Status(enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class Node:
    """Base node. `name` is what the web debugger will highlight."""

    name: str = "node"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:  # pragma: no cover
        raise NotImplementedError

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        """OnAbort clean-up. Default: nothing to undo."""


class Sequence(Node):
    """Run children in order; fail fast; remember position across ticks."""

    def __init__(self, name: str, children: list[Node]) -> None:
        self.name = name
        self.children = children
        self._index = 0

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        while self._index < len(self.children):
            status = self.children[self._index].tick(agent, ctx)
            if status is Status.RUNNING:
                return Status.RUNNING
            if status is Status.FAILURE:
                self._index = 0
                return Status.FAILURE
            self._index += 1
        self._index = 0
        return Status.SUCCESS

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        if self._index < len(self.children):
            self.children[self._index].abort(agent, ctx)
        self._index = 0


# --- leaves ---------------------------------------------------------------
def _target(agent: "Agent"):
    return agent.blackboard.get("target")


class Reserve(Node):
    name = "Reserve"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None:
            return Status.FAILURE
        return Status.SUCCESS if obj.reserve(agent.id) else Status.FAILURE


class Travel(Node):
    """Request travel to the target; movement is done by the Locomotion system.

    This leaf only sets the navigation goal and polls arrival, keeping the BT
    free of pathfinding/avoidance concerns (architecture doc 2D/2E).
    """

    name = "Travel"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None:
            return Status.FAILURE
        agent.set_goal(obj.position)
        return Status.SUCCESS if agent.at_goal else Status.RUNNING


class Occupy(Node):
    """Interact for the object's duration, draining the satisfied need."""

    name = "Occupy"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None:
            return Status.FAILURE
        bb = agent.blackboard
        if "occupy_ticks_left" not in bb:
            if not obj.occupy(agent.id):
                return Status.FAILURE
            bb["occupy_ticks_left"] = obj.interaction_ticks
            need = agent.active_motive
            bb["occupy_need"] = need
            bb["occupy_per_tick"] = obj.advertised_amount(need) / obj.interaction_ticks
        bb["occupy_ticks_left"] -= 1
        need = bb["occupy_need"]
        agent.needs[need] = max(0.0, agent.needs[need] - bb["occupy_per_tick"])
        if bb["occupy_ticks_left"] <= 0:
            for key in ("occupy_ticks_left", "occupy_need", "occupy_per_tick"):
                bb.pop(key, None)
            return Status.SUCCESS
        return Status.RUNNING

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        for key in ("occupy_ticks_left", "occupy_need", "occupy_per_tick"):
            agent.blackboard.pop(key, None)


class Release(Node):
    name = "Release"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is not None:
            obj.release(agent.id)
        return Status.SUCCESS


def interaction_tree() -> Sequence:
    """The standard smart-object interaction sequence."""
    return Sequence(
        "UseSmartObject",
        [Reserve(), Travel(), Occupy(), Release()],
    )
