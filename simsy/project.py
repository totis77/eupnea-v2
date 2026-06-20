"""Project model + loader (the engine ↔ project seam).

A *project* is a self-contained scenario folder (like a game-engine project): it
owns its resources/assets and scene, and *references* the engine's reusable AI
mechanics here in `simsy`. A scene is authored as **data** — `projects/<name>/
scene.yaml` loaded by `simsy.scene` (Phase 3); projects without a scene file fall
back to a Python `build(...)` (the micro feature scenes still use this). Phase 4
adds a GUI that edits the scene data.
"""

from __future__ import annotations

import importlib
import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    from .sim import Simulation

PROJECTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "projects"


def load_project(name: str) -> "ModuleType":
    """Import a project's `project` module by name (``projects/<name>/project.py``)."""
    return importlib.import_module(f"projects.{name}.project")


def scene_path(name: str) -> pathlib.Path:
    """Path to a project's data scene (``projects/<name>/scene.yaml``).
    A dotted name like ``micro.queue`` maps to ``projects/micro/queue``."""
    return PROJECTS_DIR.joinpath(*name.split(".")) / "scene.yaml"


def build_project(name: str, **kwargs) -> "Simulation":
    """Build project `name`'s `Simulation`. Prefers a data `scene.yaml`; falls
    back to the project's Python `build()`. Extra kwargs (``config``, ``seed``,
    ``max_population``) are forwarded to whichever path is used."""
    path = scene_path(name)
    if path.exists():
        from .scene import load_scene_file
        return load_scene_file(path, **kwargs)
    return load_project(name).build(**kwargs)
