"""Groups: cohesion keeps members traveling together (vs. spreading out)."""

import math

from simsy.agents.agent import Agent
from simsy.config import LocomotionCfg
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.nav.locomotion import Locomotion
from simsy.project import build_project


def _avg_spread(cohesion: float) -> float:
    """Average max-pairwise-distance of a 4-agent group crossing to one goal,
    driven purely by the Locomotion system at the given cohesion."""
    grid = NavGrid(-20.0, -20.0, 20.0, 20.0, cell=1.0)
    loco = Locomotion(grid, locomotion=LocomotionCfg(group_cohesion=cohesion))
    ctx = SimContext(seed=0)
    agents = []
    for i in range(4):
        a = Agent(f"m{i}", (-10.0, (i - 1.5) * 3.0), {"x": 0.0}, {"x": 0.0}, group_id="g")
        a.locomotor.set_goal((12.0, 0.0))
        agents.append(a)

    spreads = []
    for _ in range(60):
        loco.update(agents, ctx)
        ctx.tick += 1
        pts = [a.position for a in agents]
        spreads.append(max(math.dist(p, q) for p in pts for q in pts))
    return sum(spreads) / len(spreads)


def test_cohesion_keeps_a_group_tighter_than_no_cohesion():
    assert _avg_spread(0.6) < _avg_spread(0.0)


def test_group_scene_travels_together_and_is_deterministic():
    def run():
        sim = build_project("micro.group", group_size=4)
        max_spread = 0.0
        traces = []
        for _ in range(80):
            sim.step()
            members = [a for a in sim.agents if a.id.startswith("m")]
            if len(members) >= 2:
                pts = [a.position for a in members]
                max_spread = max(max_spread, max(math.dist(p, q) for p in pts for q in pts))
            traces.append(tuple(round(c, 4) for a in members for c in a.position))
        return max_spread, traces

    spread, traces = run()
    _, traces2 = run()
    assert traces == traces2, "group scene must be deterministic"
    # They start ~7.5 apart vertically; cohesion should keep them clustered.
    assert spread < 11.0, f"group drifted apart: {spread:.1f}"
