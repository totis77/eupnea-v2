"""World-level locomotion: path following + reciprocal local avoidance.

This is the per-tick movement subsystem (architecture doc 2D/2E). The BT's
Travel leaf only sets an agent's goal and polls arrival; actual movement lives
here so it can reason about *all* agents at once for crowd avoidance.

Determinism: every agent's velocity is computed from a single read-only
position snapshot taken at the top of the tick, then positions are integrated
in a second pass. Because all agents steer away from the same snapshot, the
avoidance is reciprocal and order-independent.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..config import LocomotionCfg, OrcaCfg
from .astar import find_path
from .orca import Vec2, orca_velocity

if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..core.context import SimContext
    from .grid import NavGrid


class Locomotion:
    def __init__(
        self,
        grid: "NavGrid",
        orca: OrcaCfg | None = None,
        locomotion: LocomotionCfg | None = None,
    ) -> None:
        self.grid = grid
        orca = orca or OrcaCfg()
        loco = locomotion or LocomotionCfg()
        self.time_horizon = orca.time_horizon
        self.neighbor_dist = orca.neighbor_distance
        self.arrive_eps = loco.arrive_eps
        self.waypoint_eps = loco.waypoint_eps
        self.cohesion = loco.group_cohesion

    def update(self, agents: list["Agent"], ctx: "SimContext") -> None:
        ordered = sorted(agents, key=lambda a: a.id)
        pos = {a.id: a.position for a in ordered}
        vel = {a.id: a.locomotor.vel for a in ordered}  # last tick's velocities
        centroids = self._group_centroids(ordered, pos)

        # Pass 1: ORCA velocity for each moving agent (read-only snapshot).
        for a in ordered:
            lo = a.locomotor
            if lo.goal is None or lo.at_goal:
                lo.vel = (0.0, 0.0)  # idle/occupying agents are static neighbours
                continue
            if lo.path is None:
                lo.path = find_path(self.grid, a.position, lo.goal) or [lo.goal]
                lo.path_idx = 0
            self._advance_waypoint(a)
            pref = self._apply_cohesion(a, self._seek(a), centroids, pos)
            neighbors = self._neighbors(a, ordered, pos, vel)
            v = orca_velocity(
                Vec2(*pos[a.id]), Vec2(*vel[a.id]), a.radius,
                Vec2(*pref), lo.speed, neighbors, self.time_horizon, ctx.dt,
            )
            lo.vel = (v.x, v.y)

        # Pass 2: integrate positions, never letting one enter a blocked cell.
        for a in ordered:
            lo = a.locomotor
            if lo.vel == (0.0, 0.0):
                continue
            target = (
                a.position[0] + lo.vel[0] * ctx.dt,
                a.position[1] + lo.vel[1] * ctx.dt,
            )
            a.position = self._resolve(a.position, target)
            if math.dist(a.position, lo.goal) <= self.arrive_eps:
                a.position = lo.goal     # snap exactly onto the interaction point
                lo.at_goal = True
                lo.vel = (0.0, 0.0)
                lo.path = None

    # --- group cohesion ---------------------------------------------------
    def _group_centroids(self, ordered, pos):
        groups: dict[str, list] = {}
        for a in ordered:
            gm = a.group_member
            if gm is not None:
                groups.setdefault(gm.group_id, []).append(pos[a.id])
        return {
            g: (sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps))
            for g, ps in groups.items()
        }

    def _apply_cohesion(self, a, pref, centroids, pos):
        """Blend a pull toward the group's centroid into the preferred velocity
        so members travel together; clamp the result to the agent's speed."""
        gm = a.group_member
        if gm is None or self.cohesion <= 0.0:
            return pref
        c = centroids.get(gm.group_id)
        if c is None:
            return pref
        ax, ay = pos[a.id]
        vx = pref[0] + (c[0] - ax) * self.cohesion
        vy = pref[1] + (c[1] - ay) * self.cohesion
        m = math.hypot(vx, vy)
        speed = a.locomotor.speed
        if m > speed:
            vx, vy = vx / m * speed, vy / m * speed
        return (vx, vy)

    def _resolve(self, old, new):
        """Block movement into obstacles; slide along the unobstructed axis."""
        if self.grid.walkable(*self.grid.to_cell(*new)):
            return new
        slide_x = (new[0], old[1])
        if self.grid.walkable(*self.grid.to_cell(*slide_x)):
            return slide_x
        slide_y = (old[0], new[1])
        if self.grid.walkable(*self.grid.to_cell(*slide_y)):
            return slide_y
        return old

    # --- steering helpers -------------------------------------------------
    def _advance_waypoint(self, a: "Agent") -> None:
        lo = a.locomotor
        while (
            lo.path_idx < len(lo.path) - 1
            and math.dist(a.position, lo.path[lo.path_idx]) < self.waypoint_eps
        ):
            lo.path_idx += 1

    def _seek(self, a: "Agent") -> tuple[float, float]:
        """Preferred velocity: toward the current waypoint at full speed
        (the arrive_eps snap in pass 2 handles the final landing)."""
        lo = a.locomotor
        wx, wy = lo.path[lo.path_idx]
        dx, dy = wx - a.position[0], wy - a.position[1]
        d = math.hypot(dx, dy)
        if d == 0.0:
            return 0.0, 0.0
        return dx / d * lo.speed, dy / d * lo.speed

    def _neighbors(self, a, ordered, pos, vel):
        ax, ay = pos[a.id]
        out = []
        for b in ordered:
            if b.id == a.id:
                continue
            bx, by = pos[b.id]
            if (bx - ax) ** 2 + (by - ay) ** 2 <= self.neighbor_dist ** 2:
                out.append((Vec2(bx, by), Vec2(*vel[b.id]), b.radius))
        return out
