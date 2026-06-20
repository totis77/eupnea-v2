"""Scene-as-data: load a YAML scene into a `Simulation` (architecture doc §6G).

A scene file is the serialized form of what a project's `build()` used to do by
hand — the DSL/AST the GUI (Phase 4) will edit. It describes *content* (world
bounds, walls, smart objects, fixed agents/staff, archetypes, spawner); the
engine's reusable mechanics are referenced by name (object kinds, recipe step
actions, controller types). Subsystem *tuning* still comes from `config.yaml`.

    sim = load_scene_file("projects/coffee_shop/scene.yaml")
"""

from __future__ import annotations

import pathlib
import shutil
from typing import TYPE_CHECKING

import yaml

from .agents.agent import Agent
from .agents.spawning import AgentArchetype, Spawner
from .ai.fsm import serve_fsm
from .ai.plan import Step
from .components import Role
from .config import load_config
from .core.context import SimContext
from .nav.grid import NavGrid
from .project import PROJECTS_DIR, scene_path
from .sim import Simulation
from .world.registry import WorldRegistry
from .world.smart_object import Affordance, SmartObject

if TYPE_CHECKING:
    from .config import Config

# Named controller factories a scene can reference for staff (the pluggable-brain
# registry). Each maps a spec dict -> a controller instance.
CONTROLLERS = {
    "serve_fsm": lambda spec: serve_fsm(brew_ticks=spec.get("brew_ticks", 15)),
}


def _recipes(spec: dict) -> dict | None:
    recipes = {
        need: [Step(**step) for step in steps]
        for need, steps in (spec.get("recipes") or {}).items()
    }
    return recipes or None


def _object(spec: dict) -> SmartObject:
    affordances = [Affordance(n, a) for n, a in (spec.get("affordances") or {}).items()]
    so = SmartObject(
        spec["id"], spec["kind"], tuple(spec["pos"]), affordances,
        slots=spec.get("slots", 1),
        interaction_ticks=spec.get("interaction_ticks", 20),
        despawns=spec.get("despawns", False),
        tags=set(spec.get("tags", [])) or None,
    )
    q = spec.get("queue")
    if q is not None:
        so.enable_queue(
            direction=tuple(q.get("direction", [-1.0, 0.0])),
            spacing=q.get("spacing", 1.5), gap=q.get("gap", 2.0),
        )
    sv = spec.get("service")
    if sv is not None:
        so.enable_service(pickup_offset=tuple(sv.get("pickup_offset", [0.0, -3.0])))
    p = spec.get("portal")
    if p is not None:
        so.enable_portal(target=tuple(p["target"]))
    return so


def _archetype(name: str, spec: dict, cfg: "Config") -> AgentArchetype:
    return AgentArchetype(
        name=name,
        needs=dict(spec["needs"]),
        growth=dict(spec["growth"]),
        speed=cfg.agent.speed,
        radius=cfg.agent.radius,
        think_period_ticks=cfg.agent.think_period_ticks,
        spread=spec.get("spread", cfg.population.need_spread),
        utility_cfg=cfg.utility,
        recipes=_recipes(spec),
        with_mood=spec.get("with_mood", False),
    )


def _agent(spec: dict, world: WorldRegistry, cfg: "Config") -> Agent:
    cspec = spec.get("controller")
    controller = CONTROLLERS[cspec["type"]](cspec) if cspec else None
    ag = Agent(
        spec["id"], tuple(spec["pos"]),
        spec.get("needs", {}), spec.get("growth", {}),
        speed=cfg.agent.speed, radius=cfg.agent.radius,
        think_period_ticks=spec.get("think_period_ticks", 1),
        utility_cfg=cfg.utility, controller=controller,
        recipes=_recipes(spec), group_id=spec.get("group"),
        with_mood=spec.get("with_mood", False),
    )
    if spec.get("role"):
        ag.entity.add(Role(spec["role"]))
    if cspec and cspec.get("station"):  # wire a server to the object it staffs
        ag.blackboard["station"] = world.get(cspec["station"]).service_point
    return ag


def load_scene(
    data: dict,
    config: "Config | None" = None,
    seed: int | None = None,
    max_population: int | None = None,
) -> Simulation:
    cfg = config or load_config()
    seed = data.get("seed", cfg.simulation.seed) if seed is None else seed
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    for ospec in data.get("objects", []):
        world.add(_object(ospec))

    w = data["world"]
    grid = NavGrid(*w["bounds"], cell=w.get("cell_size", cfg.world.cell_size), inflate=cfg.agent.radius)
    for wall in data.get("walls", []):
        grid.add_obstacle(*wall)

    agents = [_agent(a, world, cfg) for a in data.get("agents", [])]

    archetypes = {n: _archetype(n, s, cfg) for n, s in (data.get("archetypes") or {}).items()}
    spawner = None
    sp = data.get("spawner")
    if sp is not None:
        max_pop = sp.get("max_population", cfg.population.max) if max_population is None else max_population
        spawner = Spawner(
            archetypes[sp["archetype"]], tuple(sp["entrance"]), max_pop,
            interval_ticks=tuple(sp.get("interval_ticks", cfg.population.spawn_interval_ticks)),
        )

    sim = Simulation(ctx, world, agents, grid, spawner, config=cfg)
    if spawner is not None and sp.get("initial"):
        spawner.prefill(sim.agents, ctx, sp["initial"])
    return sim


def load_scene_file(
    path: str | pathlib.Path,
    config: "Config | None" = None,
    seed: int | None = None,
    max_population: int | None = None,
) -> Simulation:
    data = yaml.safe_load(pathlib.Path(path).read_text())
    return load_scene(data, config, seed=seed, max_population=max_population)


# --- scene file I/O (the authoring tool's read/write/list, Phase 4) --------
def read_scene(name: str) -> dict:
    """The raw scene dict for a project (for the editor to load)."""
    return yaml.safe_load(scene_path(name).read_text())


def write_scene(name: str, data: dict) -> None:
    """Persist an edited scene back to `projects/<name>/scene.yaml`, keeping a
    single `.bak` of the previous version."""
    p = scene_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        shutil.copyfile(p, p.with_suffix(".yaml.bak"))
    p.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))


def list_scenes() -> list[str]:
    """Dotted names of all projects that have a data scene, sorted."""
    names = []
    for sp in PROJECTS_DIR.rglob("scene.yaml"):
        rel = sp.parent.relative_to(PROJECTS_DIR)
        names.append(".".join(rel.parts))
    return sorted(names)
