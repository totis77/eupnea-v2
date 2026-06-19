"""Project model + loader (the engine ↔ project seam).

A *project* is a self-contained scenario folder (like a game-engine project): it
owns its resources/assets and scene, and *references* the engine's reusable AI
mechanics here in `simsy`. For now a project is a Python package under
`projects/` exposing a `project` module with `build(...) -> Simulation`; Phase 3
will let the scene be pure data loaded by this module instead, and Phase 4 a GUI
that edits that data.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

    from .sim import Simulation


def load_project(name: str) -> "ModuleType":
    """Import a project's `project` module by name (``projects/<name>/project.py``)."""
    return importlib.import_module(f"projects.{name}.project")


def build_project(name: str, **kwargs) -> "Simulation":
    """Load project `name` and build its `Simulation`. Extra kwargs (e.g.
    ``seed``, ``max_population``) are forwarded to the project's ``build()``."""
    return load_project(name).build(**kwargs)
