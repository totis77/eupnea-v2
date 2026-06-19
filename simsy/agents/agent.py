"""Agent instances: drives, blackboard, and the Utility <-> BT glue.

Cognition (Utility re-planning) and locomotion (ticking the active BT) are
deliberately separated so the LOD system can stagger thinking without
stuttering movement (architecture doc 2E). In this slice `think()` runs on a
staggered cadence and `act()` runs every tick.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..ai import utility
from ..ai.behavior_tree import Sequence, Status, interaction_tree
from ..config import UtilityCfg

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
    ) -> None:
        self.id = agent_id
        self.position = position
        self.needs = dict(needs)  # 0..100, higher = more pressing
        self.need_growth = dict(need_growth)  # units per second
        self.speed = speed
        self.think_period_ticks = think_period_ticks
        self.ucfg = utility_cfg or UtilityCfg()
        self.blackboard: dict = {}
        self.active_motive: str | None = None
        self._tree: Sequence | None = None
        # --- locomotion state (driven by the Locomotion subsystem) --------
        self.radius = radius
        self.goal: tuple[float, float] | None = None
        self.path: list[tuple[float, float]] | None = None
        self.path_idx = 0
        self.vel: tuple[float, float] = (0.0, 0.0)
        self.at_goal = False

    def set_goal(self, pos: tuple[float, float]) -> None:
        """Request travel to `pos`; recomputes the path only if it changed."""
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

    # --- per-tick updates -------------------------------------------------
    def update_needs(self, ctx: "SimContext") -> None:
        for need, rate in self.need_growth.items():
            self.needs[need] = min(100.0, self.needs[need] + rate * ctx.dt)

    def should_think(self, ctx: "SimContext") -> bool:
        # Stagger by agent id hash so the think-budget spreads across ticks.
        offset = sum(ord(c) for c in self.id) % self.think_period_ticks
        return ctx.tick % self.think_period_ticks == offset

    # --- cognition (staggered) -------------------------------------------
    def think(self, world: "WorldRegistry", ctx: "SimContext") -> None:
        cand = utility.best_candidate(self, world, self.ucfg.pressure_exponent)
        if cand is None or cand.score < self.ucfg.idle_threshold:
            return  # nothing worth doing -> stay idle
        if self.active_motive is None:
            self._adopt(cand)
            return
        if cand.need == self.active_motive:
            return  # stay committed; intra-motive object choice is free
        current = self._current_motive_score(world)
        if cand.score > current * self.ucfg.hysteresis:
            self._abort_current(ctx)
            self._adopt(cand)

    def _current_motive_score(self, world: "WorldRegistry") -> float:
        target = self.blackboard.get("target")
        if self.active_motive is None or target is None:
            return 0.0
        return utility.score(
            self.needs[self.active_motive],
            target.advertised_amount(self.active_motive),
            self.ucfg.pressure_exponent,
        )

    def _adopt(self, cand: utility.Candidate) -> None:
        self.active_motive = cand.need
        self.blackboard["target"] = cand.obj
        self._tree = interaction_tree()

    def _abort_current(self, ctx: "SimContext") -> None:
        if self._tree is not None:
            self._tree.abort(self, ctx)
        target = self.blackboard.get("target")
        if target is not None:
            target.release(self.id)  # guaranteed clean-up of the reservation
        self._clear()

    def _clear(self) -> None:
        self.active_motive = None
        self._tree = None
        self.blackboard.pop("target", None)
        self.clear_goal()

    # --- locomotion / execution (every tick) ------------------------------
    def act(self, world: "WorldRegistry", ctx: "SimContext") -> None:
        if self._tree is None:
            return
        status = self._tree.tick(self, ctx)
        if status in (Status.SUCCESS, Status.FAILURE):
            self._clear()

    # --- introspection (for the future snapshot emitter) ------------------
    @property
    def active_node(self) -> str | None:
        if self._tree is None:
            return None
        idx = min(self._tree._index, len(self._tree.children) - 1)
        return self._tree.children[idx].name
