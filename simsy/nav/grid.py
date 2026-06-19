"""Walkable occupancy grid for global pathfinding.

A uniform grid over the world bounds. Cells overlapping an obstacle rectangle
(walls, counters) are marked blocked. The grid is the macro-navigation
representation referenced in the architecture doc (2D); the NavMesh upgrade
would swap in behind the same `walkable` / `find_path` surface.
"""

from __future__ import annotations

from collections import deque


class NavGrid:
    def __init__(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        cell: float = 1.0,
        inflate: float = 0.0,
    ) -> None:
        self.min_x = min_x
        self.min_y = min_y
        self.cell = cell
        self.inflate = inflate  # obstacles are grown by this (the agent radius)
        self.cols = int(round((max_x - min_x) / cell))
        self.rows = int(round((max_y - min_y) / cell))
        self.blocked = [[False] * self.cols for _ in range(self.rows)]
        self.obstacles: list[tuple[float, float, float, float]] = []

    # --- construction -----------------------------------------------------
    def add_obstacle(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.obstacles.append((x0, y0, x1, y1))  # raw rect kept for rendering
        # Block cells overlapping the obstacle grown by `inflate`, so an agent
        # *centre* kept out of blocked cells keeps its whole body off the wall.
        ix0, iy0 = x0 - self.inflate, y0 - self.inflate
        ix1, iy1 = x1 + self.inflate, y1 + self.inflate
        for cy in range(self.rows):
            for cx in range(self.cols):
                bx0, by0 = self.min_x + cx * self.cell, self.min_y + cy * self.cell
                bx1, by1 = bx0 + self.cell, by0 + self.cell
                if bx0 < ix1 and bx1 > ix0 and by0 < iy1 and by1 > iy0:
                    self.blocked[cy][cx] = True

    # --- coordinate mapping ----------------------------------------------
    def to_cell(self, x: float, y: float) -> tuple[int, int]:
        cx = int((x - self.min_x) // self.cell)
        cy = int((y - self.min_y) // self.cell)
        cx = max(0, min(self.cols - 1, cx))
        cy = max(0, min(self.rows - 1, cy))
        return cx, cy

    def to_world(self, cx: int, cy: int) -> tuple[float, float]:
        return (
            self.min_x + (cx + 0.5) * self.cell,
            self.min_y + (cy + 0.5) * self.cell,
        )

    def in_bounds(self, cx: int, cy: int) -> bool:
        return 0 <= cx < self.cols and 0 <= cy < self.rows

    def walkable(self, cx: int, cy: int) -> bool:
        return self.in_bounds(cx, cy) and not self.blocked[cy][cx]

    def nearest_walkable(self, cx: int, cy: int) -> tuple[int, int]:
        """BFS outward (deterministic ring order) to a walkable cell."""
        if self.walkable(cx, cy):
            return cx, cy
        seen = {(cx, cy)}
        q: deque[tuple[int, int]] = deque([(cx, cy)])
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in seen or not self.in_bounds(nx, ny):
                    continue
                if self.walkable(nx, ny):
                    return nx, ny
                seen.add((nx, ny))
                q.append((nx, ny))
        return cx, cy  # fully boxed in; caller falls back to direct line

    def line_of_sight(self, ax: float, ay: float, bx: float, by: float) -> bool:
        """True if the straight segment a->b crosses only walkable cells."""
        dist = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        steps = max(1, int(dist / (self.cell * 0.5)))
        for i in range(steps + 1):
            t = i / steps
            cx, cy = self.to_cell(ax + (bx - ax) * t, ay + (by - ay) * t)
            if not self.walkable(cx, cy):
                return False
        return True
