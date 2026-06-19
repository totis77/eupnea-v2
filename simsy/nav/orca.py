"""ORCA — Optimal Reciprocal Collision Avoidance (agent-agent).

A faithful port of the 2D linear-program solver from the RVO2 reference
implementation (van den Berg et al.). Each neighbour contributes a half-plane
constraint (the ORCA line) on the agent's admissible velocity; we then solve a
small linear program for the velocity closest to the preferred velocity,
bounded by max speed. Reciprocity (each agent taking half the avoidance
responsibility) is what keeps the result smooth and oscillation-free.

Static walls are handled separately by the inflated NavGrid + collision
resolution in Locomotion, so no obstacle ORCA lines are generated here.

Determinism: pure float arithmetic over deterministically-ordered inputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

RVO_EPSILON = 1e-5


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float

    def __add__(self, o: "Vec2") -> "Vec2":
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: "Vec2") -> "Vec2":
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, s: float) -> "Vec2":
        return Vec2(self.x * s, self.y * s)

    def dot(self, o: "Vec2") -> float:
        return self.x * o.x + self.y * o.y

    def det(self, o: "Vec2") -> float:
        return self.x * o.y - self.y * o.x

    def abs_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        return math.sqrt(self.abs_sq())

    def normalized(self) -> "Vec2":
        n = self.length()
        return Vec2(self.x / n, self.y / n)


@dataclass(frozen=True)
class Line:
    point: Vec2
    direction: Vec2


def _linear_program1(lines, i, radius, opt_velocity, direction_opt):
    """Solve the 1D LP on the constraint line `i`. Returns (ok, result)."""
    line = lines[i]
    dot = line.point.dot(line.direction)
    discriminant = dot * dot + radius * radius - line.point.abs_sq()
    if discriminant < 0.0:
        return False, None  # max-speed circle entirely outside constraint
    sqrt_disc = math.sqrt(discriminant)
    t_left = -dot - sqrt_disc
    t_right = -dot + sqrt_disc
    for j in range(i):
        denominator = line.direction.det(lines[j].direction)
        numerator = lines[j].direction.det(line.point - lines[j].point)
        if abs(denominator) <= RVO_EPSILON:
            if numerator < 0.0:
                return False, None
            continue
        t = numerator / denominator
        if denominator >= 0.0:
            t_right = min(t_right, t)
        else:
            t_left = max(t_left, t)
        if t_left > t_right:
            return False, None
    if direction_opt:
        if opt_velocity.dot(line.direction) > 0.0:
            result = line.point + line.direction * t_right
        else:
            result = line.point + line.direction * t_left
    else:
        t = line.direction.dot(opt_velocity - line.point)
        if t < t_left:
            result = line.point + line.direction * t_left
        elif t > t_right:
            result = line.point + line.direction * t_right
        else:
            result = line.point + line.direction * t
    return True, result


def _linear_program2(lines, radius, opt_velocity, direction_opt):
    """Solve the 2D LP. Returns (num_satisfied, result)."""
    if direction_opt:
        result = opt_velocity * radius
    elif opt_velocity.abs_sq() > radius * radius:
        result = opt_velocity.normalized() * radius
    else:
        result = opt_velocity
    for i in range(len(lines)):
        if lines[i].direction.det(lines[i].point - result) > 0.0:
            temp = result
            ok, result = _linear_program1(lines, i, radius, opt_velocity, direction_opt)
            if not ok:
                return i, temp
    return len(lines), result


def _linear_program3(lines, begin, radius, result):
    """Fallback when the 2D LP is infeasible: minimise constraint penetration."""
    distance = 0.0
    for i in range(begin, len(lines)):
        if lines[i].direction.det(lines[i].point - result) > distance:
            proj_lines: list[Line] = []  # no obstacle lines in this engine
            for j in range(i):
                determinant = lines[i].direction.det(lines[j].direction)
                if abs(determinant) <= RVO_EPSILON:
                    if lines[i].direction.dot(lines[j].direction) > 0.0:
                        continue
                    point = (lines[i].point + lines[j].point) * 0.5
                else:
                    point = lines[i].point + lines[i].direction * (
                        lines[j].direction.det(lines[i].point - lines[j].point)
                        / determinant
                    )
                direction = (lines[j].direction - lines[i].direction).normalized()
                proj_lines.append(Line(point, direction))
            temp = result
            opt = Vec2(-lines[i].direction.y, lines[i].direction.x)
            count, result = _linear_program2(proj_lines, radius, opt, True)
            if count < len(proj_lines):
                result = temp
            distance = lines[i].direction.det(lines[i].point - result)
    return result


def orca_velocity(
    pos: Vec2,
    vel: Vec2,
    radius: float,
    pref_vel: Vec2,
    max_speed: float,
    neighbors: list[tuple[Vec2, Vec2, float]],
    time_horizon: float,
    dt: float,
) -> Vec2:
    """New velocity for one agent given its neighbours (pos, vel, radius)."""
    inv_tau = 1.0 / time_horizon
    lines: list[Line] = []
    for npos, nvel, nrad in neighbors:
        rel_pos = npos - pos
        rel_vel = vel - nvel
        dist_sq = rel_pos.abs_sq()
        if dist_sq < RVO_EPSILON:
            continue  # coincident agents: no meaningful constraint
        comb_r = radius + nrad
        comb_r_sq = comb_r * comb_r

        if dist_sq > comb_r_sq:
            # No collision: project onto the cutoff circle or the legs.
            w = rel_vel - rel_pos * inv_tau
            w_len_sq = w.abs_sq()
            dot1 = w.dot(rel_pos)
            if dot1 < 0.0 and dot1 * dot1 > comb_r_sq * w_len_sq:
                w_len = math.sqrt(w_len_sq)
                unit_w = w * (1.0 / w_len)
                direction = Vec2(unit_w.y, -unit_w.x)
                u = unit_w * (comb_r * inv_tau - w_len)
            else:
                leg = math.sqrt(dist_sq - comb_r_sq)
                if rel_pos.det(w) > 0.0:  # left leg
                    direction = Vec2(
                        rel_pos.x * leg - rel_pos.y * comb_r,
                        rel_pos.x * comb_r + rel_pos.y * leg,
                    ) * (1.0 / dist_sq)
                else:  # right leg
                    direction = Vec2(
                        rel_pos.x * leg + rel_pos.y * comb_r,
                        -rel_pos.x * comb_r + rel_pos.y * leg,
                    ) * (-1.0 / dist_sq)
                u = direction * rel_vel.dot(direction) - rel_vel
        else:
            # Already overlapping: resolve over a single time step.
            inv_dt = 1.0 / dt
            w = rel_vel - rel_pos * inv_dt
            w_len = w.length()
            if w_len < RVO_EPSILON:
                continue
            unit_w = w * (1.0 / w_len)
            direction = Vec2(unit_w.y, -unit_w.x)
            u = unit_w * (comb_r * inv_dt - w_len)

        lines.append(Line(vel + u * 0.5, direction))

    count, result = _linear_program2(lines, max_speed, pref_vel, False)
    if count < len(lines):
        result = _linear_program3(lines, count, max_speed, result)
    return result
