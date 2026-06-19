"""ORCA: reciprocal avoidance keeps agents apart, and stays deterministic."""

import math

from simsy.agents.agent import Agent
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.nav.locomotion import Locomotion


def _open_grid() -> NavGrid:
    return NavGrid(-15.0, -15.0, 15.0, 15.0, cell=1.0)


def _agent(aid: str, pos, goal) -> Agent:
    a = Agent(aid, pos, {"x": 0.0}, {"x": 0.0})
    a.locomotor.set_goal(goal)
    return a


def _run(agents, ticks: int):
    loco = Locomotion(_open_grid())
    ctx = SimContext(seed=0)
    min_dist = float("inf")
    for _ in range(ticks):
        loco.update(agents, ctx)
        ctx.tick += 1
        if len(agents) == 2:
            min_dist = min(min_dist, math.dist(agents[0].position, agents[1].position))
    return min_dist


def test_head_on_agents_avoid_without_interpenetration():
    # Slight y-offset breaks perfect symmetry, as in a real crowd.
    a = _agent("a", (-6.0, 0.0), (6.0, 0.0))
    b = _agent("b", (6.0, 0.4), (-6.0, 0.4))
    min_dist = _run([a, b], 120)
    combined = a.radius + b.radius  # 1.2
    assert min_dist >= combined - 0.15, f"agents interpenetrated: {min_dist:.3f}"
    assert a.locomotor.at_goal and b.locomotor.at_goal, "both should still reach their goals"


def test_orca_is_deterministic():
    def trace():
        a = _agent("a", (-6.0, 0.0), (6.0, 0.0))
        b = _agent("b", (6.0, 0.4), (-6.0, 0.4))
        loco, ctx = Locomotion(_open_grid()), SimContext(seed=0)
        out = []
        for _ in range(60):
            loco.update([a, b], ctx)
            ctx.tick += 1
            out.append((a.position, b.position))
        return out

    assert trace() == trace()
