"""Navigation: A* routing, determinism, and no-clip guarantees."""

from simsy.nav.astar import find_path
from simsy.nav.grid import NavGrid
from simsy.project import build_project


def _walled() -> NavGrid:
    g = NavGrid(-10.0, -10.0, 10.0, 10.0, cell=1.0)
    g.add_obstacle(-0.5, -10.0, 0.5, 5.0)  # vertical wall, gap above y=5
    return g


def test_direct_line_is_blocked_but_path_exists():
    g = _walled()
    assert g.line_of_sight(-5.0, 0.0, 5.0, 0.0) is False  # must detour
    path = find_path(g, (-5.0, 0.0), (5.0, 0.0))
    assert path, "expected a route around the wall"
    assert path[-1] == (5.0, 0.0)


def test_path_never_crosses_a_blocked_cell():
    g = _walled()
    path = find_path(g, (-5.0, 0.0), (5.0, 0.0))
    pts = [(-5.0, 0.0), *path]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        assert g.line_of_sight(ax, ay, bx, by), "segment clips an obstacle"


def test_find_path_is_deterministic():
    g = _walled()
    assert find_path(g, (-5.0, 0.0), (5.0, 0.0)) == find_path(g, (-5.0, 0.0), (5.0, 0.0))


def test_agents_never_end_a_tick_inside_a_wall():
    sim = build_project("coffee_shop")
    for _ in range(150):
        sim.step()
        for a in sim.agents:
            assert sim.grid.walkable(*sim.grid.to_cell(*a.position)), (
                a.id, a.position, sim.ctx.tick
            )
