"""Simulation driver: the fixed-timestep tick loop and snapshot emitter.

This is engine-only — scene *content* lives in a project (see `simsy.project`
and `projects/`). Run a project headless with `uv run python -m simsy.run`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ai import utility
from .config import load_config
from .nav.locomotion import Locomotion

if TYPE_CHECKING:
    from .agents.agent import Agent
    from .agents.spawning import Spawner
    from .config import Config
    from .core.context import SimContext
    from .nav.grid import NavGrid
    from .world.registry import WorldRegistry


class Simulation:
    def __init__(
        self,
        ctx: SimContext,
        world: WorldRegistry,
        agents: list[Agent],
        grid: NavGrid,
        spawner: Spawner | None = None,
        config: Config | None = None,
    ):
        self.ctx = ctx
        self.world = world
        self.agents = agents
        self.grid = grid
        self.config = config or load_config()
        self.loco = Locomotion(grid, self.config.orca, self.config.locomotion)
        self.spawner = spawner

    def step(self) -> None:
        ctx = self.ctx
        ordered = sorted(self.agents, key=lambda a: a.id)  # deterministic order
        for agent in ordered:
            agent.update_needs(ctx)
        self._update_moods(ordered)
        self.ctx.events.drain()
        for agent in ordered:
            if agent.should_think(ctx):
                agent.think(self.world, ctx)
        for agent in ordered:
            agent.act(self.world, ctx)
        self.loco.update(self.agents, ctx)  # movement: paths + crowd avoidance
        self._despawn_arrivals()
        if self.spawner is not None:
            self.spawner.update(self.agents, ctx)
        ctx.tick += 1

    def _update_moods(self, ordered: list[Agent]) -> None:
        """Affect system: waiting in a queue builds stress (eases otherwise), and
        stress makes an agent impatient — its Leave drive grows faster."""
        cfg = self.config.mood
        dt = self.ctx.dt
        for a in ordered:
            mood = a.mood
            if mood is None:
                continue
            target = a.blackboard.get("target")
            waiting = (
                target is not None
                and getattr(target, "queue", None) is not None
                and a.id in target.queue
            )
            mood.adjust(cfg.queue_stress_per_sec * dt if waiting else -cfg.relief_per_sec * dt)
            needs = a.drives.needs
            if "Leave" in needs:
                needs["Leave"] = min(100.0, needs["Leave"] + cfg.impatience * mood.stress * dt)

    def _despawn_arrivals(self) -> None:
        """Remove agents that have reached an exit object (releasing its slot)."""
        for a in list(self.agents):
            target = a.blackboard.get("target")
            if target is not None and target.despawns and a.locomotor.at_goal:
                target.release(a.id)
                self.agents.remove(a)

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            self.step()

    def _agent_view(self, a: Agent) -> dict:
        target = a.blackboard.get("target")
        motive_score = 0.0
        if a.active_motive is not None and target is not None:
            motive_score = utility.score(
                a.drives.needs[a.active_motive],
                target.advertised_amount(a.active_motive),
                self.config.utility.pressure_exponent,
            )
        return {
            "id": a.id,
            "pos": (round(a.position[0], 3), round(a.position[1], 3)),
            "motive": a.active_motive,
            "node": a.active_node,
            "target": target.id if target is not None else None,
            "score": round(motive_score, 3),
            "needs": {k: round(v, 2) for k, v in sorted(a.drives.needs.items())},
            "path": [(round(x, 2), round(y, 2)) for x, y in (a.locomotor.path or [])],
            "carrying": sorted(a.inventory.items),
            "plan": a.plan_view,
            "stress": round(a.mood.stress, 1) if a.mood is not None else None,
        }

    def snapshot(self) -> dict:
        """Serializable state -- the seam the WebSocket emitter consumes."""
        return {
            "tick": self.ctx.tick,
            "time": round(self.ctx.time, 3),
            "agents": [
                self._agent_view(a)
                for a in sorted(self.agents, key=lambda a: a.id)
            ],
            "objects": [
                {
                    "id": o.id,
                    "kind": o.kind,
                    "pos": (round(o.position[0], 3), round(o.position[1], 3)),
                    "free": o.free_slots,
                    "slots": o.slots,
                    "affordances": sorted(o.affordances),
                }
                for o in self.world.all()
            ],
            "obstacles": list(self.grid.obstacles),
        }
