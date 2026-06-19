"""Scripted multi-step plans (architecture doc §6E, executor side).

A *recipe* is an ordered list of `Step`s that satisfy a goal across several
objects — e.g. Caffeine = [acquire a coffee at the counter, consume it at a
seat]. It is declarative scene/agent content (authorable, and serializable into
the future DSL), not a search-based planner.

`build_plan_tree` compiles a recipe into a Behavior Tree: each step resolves a
concrete target object (by tag, deterministically) and runs the right leaf
sequence on it. Steps are resolved at adoption time; if the target gets taken by
the time the agent arrives, the step's Reserve fails, the plan fails, and the
controller re-plans.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .behavior_tree import (
    ConsumeItem,
    PlaceOrder,
    ReceiveItem,
    Release,
    Reserve,
    Sequence,
    SetTarget,
    Travel,
)

if TYPE_CHECKING:
    from ..world.registry import WorldRegistry


@dataclass
class Step:
    """One step of a recipe: find an object by `tag` and do `action` with `item`.

    action:
      - "acquire": order at a ServicePoint and carry the produced item away.
      - "consume": sit at the target and consume the item to satisfy `need`,
        by `amount` over the interaction.
    """

    tag: str
    action: str
    item: str
    amount: float = 0.0


def _resolve(world: "WorldRegistry", tag: str, agent) -> object | None:
    """Pick the object for a step: prefer one with a free slot (or a queue),
    nearest to the agent; deterministic id tiebreak. None if the tag is absent."""
    matches = world.by_tag(tag)
    if not matches:
        return None
    pool = [o for o in matches if o.free_slots > 0 or o.queue is not None] or matches
    if agent is not None:
        ax, ay = agent.position
        pool = sorted(
            pool,
            key=lambda o: ((o.position[0] - ax) ** 2 + (o.position[1] - ay) ** 2, o.id),
        )
    return pool[0]


def build_plan_tree(
    world: "WorldRegistry", recipe: list[Step], need: str, agent=None
) -> "Sequence | None":
    """Compile a recipe into a BT, resolving each step's target by tag (an
    available one nearest the agent). None if any step's object is absent (the
    controller then won't adopt)."""
    steps: list[Sequence] = []
    for st in recipe:
        obj = _resolve(world, st.tag, agent)
        if obj is None:
            return None
        if st.action == "acquire":
            steps.append(Sequence(
                f"acquire:{st.item}",
                [SetTarget(obj), Reserve(), Travel(), PlaceOrder(), ReceiveItem(st.item)],
            ))
        elif st.action == "consume":
            steps.append(Sequence(
                f"consume:{st.item}",
                [SetTarget(obj), Reserve(), Travel(), ConsumeItem(st.item, need, st.amount), Release()],
            ))
        else:  # pragma: no cover - guards a malformed recipe
            return None
    return Sequence(f"plan:{need}", steps)
