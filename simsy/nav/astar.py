"""Deterministic 8-directional A* over a NavGrid, with LOS path smoothing.

Determinism: neighbours are generated in a fixed order and the open-set heap
uses a monotonic insertion counter as the final tie-breaker, so identical
inputs always yield the identical path.
"""

from __future__ import annotations

import heapq

from .grid import NavGrid

# 8-connected moves; diagonals last so straight moves win ties.
_ORTHO = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))
_SQRT2 = 2 ** 0.5


def _heuristic(ax: int, ay: int, bx: int, by: int) -> float:
    # Octile distance: admissible for 8-connected grids.
    dx, dy = abs(ax - bx), abs(ay - by)
    return (dx + dy) + (_SQRT2 - 2) * min(dx, dy)


def find_path(
    grid: NavGrid,
    start: tuple[float, float],
    goal: tuple[float, float],
) -> list[tuple[float, float]]:
    """Return world-space waypoints start->goal, or [] if unreachable."""
    sx, sy = grid.nearest_walkable(*grid.to_cell(*start))
    gx, gy = grid.nearest_walkable(*grid.to_cell(*goal))
    if (sx, sy) == (gx, gy):
        return [goal]

    counter = 0
    open_heap: list[tuple[float, int, tuple[int, int]]] = [(0.0, counter, (sx, sy))]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {(sx, sy): 0.0}

    while open_heap:
        _, _, (cx, cy) = heapq.heappop(open_heap)
        if (cx, cy) == (gx, gy):
            return _build(grid, came_from, (gx, gy), goal)
        base = g_score[(cx, cy)]
        for dx, dy in _ORTHO + _DIAG:
            nx, ny = cx + dx, cy + dy
            if not grid.walkable(nx, ny):
                continue
            if dx and dy:  # no corner cutting through blocked orthogonals
                if not (grid.walkable(cx + dx, cy) and grid.walkable(cx, cy + dy)):
                    continue
                step = _SQRT2
            else:
                step = 1.0
            tentative = base + step
            if tentative < g_score.get((nx, ny), float("inf")):
                came_from[(nx, ny)] = (cx, cy)
                g_score[(nx, ny)] = tentative
                counter += 1
                f = tentative + _heuristic(nx, ny, gx, gy)
                heapq.heappush(open_heap, (f, counter, (nx, ny)))
    return []


def _build(grid, came_from, end, goal_world) -> list[tuple[float, float]]:
    cells = [end]
    while cells[-1] in came_from:
        cells.append(came_from[cells[-1]])
    cells.reverse()
    points = [grid.to_world(cx, cy) for cx, cy in cells]
    points[-1] = goal_world  # land on the true target, not the cell centre
    return _smooth(grid, points)


def _smooth(grid: NavGrid, pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """String-pulling: drop waypoints reachable by straight line-of-sight."""
    if len(pts) <= 2:
        return pts
    out = [pts[0]]
    i = 0
    while i < len(pts) - 1:
        j = len(pts) - 1
        while j > i + 1 and not grid.line_of_sight(*pts[i], *pts[j]):
            j -= 1
        out.append(pts[j])
        i = j
    return out
