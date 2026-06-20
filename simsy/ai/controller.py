"""The Controller component: the pluggable brain (architecture doc §6E).

FSM, Behavior Tree, Utility, and GOAP are decision *architectures*, not flat
peers — they compose as **selector → executor**. The engine's default brain is
**Utility (select "what to do") → BT (execute "how to do it")**, glued by the
§2B interruption/hysteresis contract. Keeping both halves inside one component
is what makes "who interrupts whom" well-defined; swapping the executor (e.g.
GOAP for BT) is then a one-component change that touches neither the world nor
other entities.

This is exactly the glue that used to live inline in `Agent` — extracted here
unchanged so replay stays bit-identical. The controller drives an `agent`
(reads its drives/blackboard, sets its nav goal); it owns only the decision
state (`active_motive` + the running tree).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import utility
from .behavior_tree import ATOMIC, Sequence, Status, tree_for
from .plan import build_plan_tree

if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..config import UtilityCfg
    from ..core.context import SimContext
    from ..world.registry import WorldRegistry


class Controller:
    """Utility (selector) → Behavior Tree (executor) brain for one entity."""

    def __init__(self, utility_cfg: "UtilityCfg") -> None:
        self.ucfg = utility_cfg
        self.active_motive: str | None = None
        self._tree: Sequence | None = None
        # The object that anchors the active motive's score (for hysteresis).
        # Distinct from blackboard["target"], which a multi-step plan reassigns
        # per step — scoring must stay anchored to where the motive came from.
        self._motive_obj = None

    # --- cognition (staggered): pick / re-pick a motive -------------------
    def think(self, agent: "Agent", world: "WorldRegistry", ctx: "SimContext") -> None:
        cand = utility.best_candidate(agent, world, self.ucfg.pressure_exponent)
        if cand is None or cand.score < self.ucfg.idle_threshold:
            return  # nothing worth doing -> stay idle
        if self.active_motive is None:
            self._adopt(agent, world, cand)
            return
        if agent.blackboard.get(ATOMIC):
            return  # mid atomic interaction (§2B): finish before reconsidering
        if cand.need == self.active_motive:
            return  # stay committed; intra-motive object choice is free
        current = self._current_motive_score(agent)
        if cand.score > current * self.ucfg.hysteresis:
            self._abort_current(agent, ctx)
            self._adopt(agent, world, cand)

    def _current_motive_score(self, agent: "Agent") -> float:
        if self.active_motive is None or self._motive_obj is None:
            return 0.0
        return utility.score(
            agent.drives.needs[self.active_motive],
            self._motive_obj.advertised_amount(self.active_motive),
            self.ucfg.pressure_exponent,
        )

    def _adopt(self, agent: "Agent", world: "WorldRegistry", cand: utility.Candidate) -> None:
        self.active_motive = cand.need
        self._motive_obj = cand.obj
        recipe = agent.recipes.get(cand.need)
        if recipe is not None:
            tree = build_plan_tree(world, recipe, cand.need, agent)
            if tree is not None:
                self._tree = tree  # SetTarget leaves manage blackboard["target"]
                return
        agent.blackboard["target"] = cand.obj
        self._tree = tree_for(cand.obj)

    def _abort_current(self, agent: "Agent", ctx: "SimContext") -> None:
        if self._tree is not None:
            self._tree.abort(agent, ctx)
        target = agent.blackboard.get("target")
        if target is not None:
            target.release(agent.id)  # guaranteed clean-up of the reservation
        self._clear(agent)

    def _clear(self, agent: "Agent") -> None:
        self.active_motive = None
        self._motive_obj = None
        self._tree = None
        agent.blackboard.pop("target", None)
        agent.locomotor.clear_goal()

    # --- execution (every tick): tick the active tree ---------------------
    def act(self, agent: "Agent", world: "WorldRegistry", ctx: "SimContext") -> None:
        if self._tree is None:
            return
        status = self._tree.tick(agent, ctx)
        if status in (Status.SUCCESS, Status.FAILURE):
            self._clear(agent)

    # --- introspection (for the snapshot emitter) -------------------------
    @property
    def active_node(self) -> str | None:
        if self._tree is None:
            return None
        idx = min(self._tree._index, len(self._tree.children) - 1)
        return self._tree.children[idx].name

    def plan_view(self) -> dict | None:
        """A nested view of the active tree for the viewer: each node's name,
        its children, and which child is currently executing (`active_index`).
        Following `active_index` down marks the running path."""
        if self._tree is None:
            return None
        return _tree_view(self._tree)


def _tree_view(node) -> dict:
    view: dict = {"name": node.name}
    children = getattr(node, "children", None)
    if children:
        view["active_index"] = min(getattr(node, "_index", 0), len(children) - 1)
        view["children"] = [_tree_view(c) for c in children]
    return view
