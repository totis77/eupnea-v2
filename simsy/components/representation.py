"""Representation components — the top tier (architecture doc §6D).

An entity's pose and shapes. Two of these are read by engine *systems*
(`Transform`, `NavShape`); `RenderShape` is **viewer-only** and the engine never
reads it — that is the headless boundary invariant (§6B), and what keeps the
2D→3D upgrade localized to this tier (§6C).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Transform:
    """Pose: position now, gains z / full rotation in the 3D upgrade.

    `position` is the single source of truth for where an entity is; systems
    read and (for movable entities) write it via the locomotion pass."""

    position: tuple[float, float]
    facing: float = 0.0  # radians; unused until agents need orientation


@dataclass
class NavShape:
    """The simplified collision/nav proxy the *engine* consumes (≈ a collider).

    Stays 2D even when rendering goes 3D. `static` entities (walls, fixtures)
    bake into the nav grid; dynamic entities (agents) feed ORCA as a radius."""

    radius: float = 0.0
    static: bool = False


@dataclass
class RenderShape:
    """Appearance, **for the viewer only** (≈ a MeshRenderer). Pass-through
    metadata streamed in snapshots; the engine must never branch on it."""

    shape: str = "circle"
    color: str | None = None
