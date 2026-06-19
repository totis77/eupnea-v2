"""The coffee-shop scene.

`build()` places instances of the project's assets into a `Simulation` and wires
up the spawner. Subsystem knobs come from `config` (config.yaml or defaults);
the scene *structure* (which objects exist, wall geometry) lives here — that is
the project's content, distinct from engine mechanics. When the authoring layer
arrives (Phase 3) this function becomes serialized scene *data* loaded generically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from simsy.agents.spawning import Spawner
from simsy.config import load_config
from simsy.core.context import SimContext
from simsy.nav.grid import NavGrid
from simsy.sim import Simulation
from simsy.world.registry import WorldRegistry

from . import assets

if TYPE_CHECKING:
    from simsy.config import Config


def build(
    config: "Config | None" = None,
    seed: int | None = None,
    max_population: int | None = None,
) -> Simulation:
    cfg = config or load_config()
    seed = cfg.simulation.seed if seed is None else seed
    max_pop = cfg.population.max if max_population is None else max_population
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    world.add(assets.espresso_counter("espresso", (20.0, 0.0)))
    world.add(assets.couch("couch", (-20.0, 0.0)))
    entrance = (-24.0, 0.0)
    world.add(assets.exit_door("door", entrance))

    # A dividing wall at x=0 with a doorway gap at y in [4, 8]. Caffeine seekers
    # on the left must detour up to the doorway to reach the espresso -- this is
    # what exercises A* (global path) and ORCA (queueing at the doorway). The
    # grid is inflated by the agent radius so bodies never clip the wall.
    grid = NavGrid(*cfg.world.bounds, cell=cfg.world.cell_size, inflate=cfg.agent.radius)
    grid.add_obstacle(-0.6, -13.0, 0.6, 4.0)
    grid.add_obstacle(-0.6, 8.0, 0.6, 13.0)

    # Guests arrive at the door, satisfy Caffeine/Rest, then "Leave" grows until
    # it dominates and they head back to the exit.
    archetype = assets.guest_archetype(cfg)
    spawner = Spawner(
        archetype, entrance, max_pop,
        interval_ticks=tuple(cfg.population.spawn_interval_ticks),
    )
    sim = Simulation(ctx, world, [], grid, spawner, config=cfg)
    spawner.prefill(sim.agents, ctx, cfg.population.initial)  # population at tick 0
    return sim
