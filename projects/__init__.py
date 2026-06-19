"""Projects: self-contained scenario folders.

Each subpackage is one project (like a game-engine project): it owns its
resources/assets and scene, and references the engine's reusable AI mechanics in
`simsy`. A project exposes a `project` module with `build(...) -> Simulation`;
load it via `simsy.project.build_project(name)`.
"""
