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


# Blackboard key marking an in-progress *atomic* interaction (§2B): while set,
# the controller must not switch motives — the agent finishes what it started.
ATOMIC = "_atomic"


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
    """Claim a slot. For an uncontended object this is immediate (SUCCESS/FAILURE).
    For a queue-enabled object that is full, the agent joins the line and returns
    RUNNING — standing in its assigned spot — until it reaches the head and a slot
    frees, then reserves and succeeds (architecture doc §6D queue lifecycle)."""

    name = "Reserve"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None:
            return Status.FAILURE
        if obj.is_reserved_by(agent.id):
            return Status.SUCCESS  # already holding a slot
        q = obj.queue
        if q is None:
            return Status.SUCCESS if obj.reserve(agent.id) else Status.FAILURE
        # Queue-enabled: take a place in line and advance only from the head.
        q.join(agent.id)
        if q.head() == agent.id and obj.free_slots > 0:
            obj.reserve(agent.id)
            q.leave(agent.id)
            return Status.SUCCESS
        agent.locomotor.set_goal(q.wait_slot(agent.id))  # stand in (and shuffle up) the line
        return Status.RUNNING

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        obj = _target(agent)
        if obj is not None and obj.queue is not None:
            obj.queue.leave(agent.id)  # drop out of line (reservation freed by the controller)


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
        agent.locomotor.set_goal(obj.position)
        return Status.SUCCESS if agent.locomotor.at_goal else Status.RUNNING


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
            bb[ATOMIC] = True  # don't let a rising drive interrupt an in-progress use (§2B)
        bb["occupy_ticks_left"] -= 1
        need = bb["occupy_need"]
        needs = agent.drives.needs
        needs[need] = max(0.0, needs[need] - bb["occupy_per_tick"])
        if bb["occupy_ticks_left"] <= 0:
            for key in ("occupy_ticks_left", "occupy_need", "occupy_per_tick", ATOMIC):
                bb.pop(key, None)
            return Status.SUCCESS
        return Status.RUNNING

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        for key in ("occupy_ticks_left", "occupy_need", "occupy_per_tick", ATOMIC):
            agent.blackboard.pop(key, None)


class Release(Node):
    name = "Release"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is not None:
            obj.release(agent.id)
        return Status.SUCCESS


class PlaceOrder(Node):
    """At a ServicePoint: place an order, then free the register slot so the
    line moves while the server works the backlog."""

    name = "Order"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None or obj.service_point is None:
            return Status.FAILURE
        obj.service_point.place_order(agent.id)
        obj.release(agent.id)  # ordering done; release the register for the next guest
        return Status.SUCCESS

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        obj = _target(agent)
        if obj is not None and obj.service_point is not None:
            obj.service_point.cancel(agent.id)


class Receive(Node):
    """Wait at the pickup spot until the server marks the order ready, then
    collect it and satisfy the need."""

    name = "Receive"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None or obj.service_point is None:
            return Status.FAILURE
        sp = obj.service_point
        agent.locomotor.set_goal(sp.pickup)
        if not (agent.locomotor.at_goal and sp.is_ready(agent.id)):
            return Status.RUNNING
        sp.collect(agent.id)
        need = agent.active_motive
        if need is not None:
            needs = agent.drives.needs
            needs[need] = max(0.0, needs[need] - obj.advertised_amount(need))
        return Status.SUCCESS

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        obj = _target(agent)
        if obj is not None and obj.service_point is not None:
            obj.service_point.cancel(agent.id)


class SetTarget(Node):
    """Point the agent at a specific pre-resolved object for the following
    leaves. Used by multi-step plans to switch targets between steps."""

    name = "SetTarget"

    def __init__(self, obj) -> None:
        self.obj = obj

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        agent.blackboard["target"] = self.obj
        return Status.SUCCESS


class ReceiveItem(Node):
    """Like Receive, but the order yields a carried *item* into the agent's
    inventory rather than satisfying a need directly (the need is satisfied
    later, when the item is consumed)."""

    name = "Receive"

    def __init__(self, item: str) -> None:
        self.item = item

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None or obj.service_point is None:
            return Status.FAILURE
        sp = obj.service_point
        agent.locomotor.set_goal(sp.pickup)
        if not (agent.locomotor.at_goal and sp.is_ready(agent.id)):
            return Status.RUNNING
        sp.collect(agent.id)
        agent.inventory.add(self.item)
        return Status.SUCCESS

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        obj = _target(agent)
        if obj is not None and obj.service_point is not None:
            obj.service_point.cancel(agent.id)


class ConsumeItem(Node):
    """Occupy the target (a seat) and consume a carried item over time, draining
    the satisfied need. Fails if the item isn't in hand."""

    name = "Consume"

    def __init__(self, item: str, need: str, amount: float, ticks: int = 15) -> None:
        self.item = item
        self.need = need
        self.amount = amount
        self.ticks = ticks

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None:
            return Status.FAILURE
        bb = agent.blackboard
        if "consume_left" not in bb:
            if not agent.inventory.has(self.item):
                return Status.FAILURE
            if not obj.occupy(agent.id):
                return Status.FAILURE
            agent.inventory.remove(self.item)
            bb["consume_left"] = self.ticks
            bb["consume_per"] = self.amount / self.ticks
            bb[ATOMIC] = True  # finish the drink before reconsidering motives (§2B)
        bb["consume_left"] -= 1
        needs = agent.drives.needs
        needs[self.need] = max(0.0, needs[self.need] - bb["consume_per"])
        if bb["consume_left"] <= 0:
            for key in ("consume_left", "consume_per", ATOMIC):
                bb.pop(key, None)
            return Status.SUCCESS
        return Status.RUNNING

    def abort(self, agent: "Agent", ctx: "SimContext") -> None:
        for key in ("consume_left", "consume_per", ATOMIC):
            agent.blackboard.pop(key, None)


class Enter(Node):
    """Step through a portal: on arrival, teleport to its linked target (the
    connected venue) and clear the goal so the next step plans afresh."""

    name = "Enter"

    def tick(self, agent: "Agent", ctx: "SimContext") -> Status:
        obj = _target(agent)
        if obj is None or obj.portal is None:
            return Status.FAILURE
        agent.position = obj.portal.target
        agent.locomotor.clear_goal()
        return Status.SUCCESS


def interaction_tree() -> Sequence:
    """The standard self-service smart-object sequence."""
    return Sequence(
        "UseSmartObject",
        [Reserve(), Travel(), Occupy(), Release()],
    )


def service_tree() -> Sequence:
    """A staffed-object sequence: queue to the register, order (and free it),
    then wait at pickup for the server to fulfill the order."""
    return Sequence(
        "UseServicePoint",
        [Reserve(), Travel(), PlaceOrder(), Receive()],
    )


def tree_for(obj) -> Sequence:
    """Pick the interaction tree appropriate to the target object."""
    if getattr(obj, "service_point", None) is not None:
        return service_tree()
    return interaction_tree()
