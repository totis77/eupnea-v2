"""The café scene — a fuller coffee shop modeled on the whiteboard.

Continuous flow: guests arrive at the entrance, queue at the staffed counter to
order a coffee, carry it to an available seat (couch / tables / coworking table)
and drink it, may visit the toilet, and leave when their Leave drive dominates.
Two baristas (FSM staff) brew the counter's orders in parallel.

Open floor plan (no interior walls yet); customer groups and the other venues
from the whiteboard are deferred to later phases (groups, portals).
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

BOUNDS = (-24.0, -14.0, 24.0, 14.0)
ENTRANCE = (-20.0, -10.0)
MAX_POPULATION = 16  # includes the 2 baristas → ~14 guests at once


def build(
    config: "Config | None" = None,
    seed: int | None = None,
    max_population: int | None = None,
) -> Simulation:
    cfg = config or load_config()
    seed = cfg.simulation.seed if seed is None else seed
    max_pop = MAX_POPULATION if max_population is None else max_population
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    counter = assets.coffee_counter("counter", (-10.0, 7.0))
    world.add(counter)
    world.add(assets.exit_door("exit", ENTRANCE))
    world.add(assets.toilet("toilet", (14.0, -9.0), slots=2))
    # Seating, all tagged "seat": guests drink at whichever is free + nearest.
    world.add(assets.seating("couch", "Couch", (16.0, 8.0), slots=5))
    world.add(assets.seating("table1", "Table", (-2.0, 1.0), slots=3))
    world.add(assets.seating("table2", "Table", (5.0, 1.0), slots=3))
    world.add(assets.seating("coworking", "CoworkingTable", (2.0, -8.0), slots=8))

    grid = NavGrid(*BOUNDS, cell=cfg.world.cell_size, inflate=cfg.agent.radius)

    # Staff: two baristas behind the counter, both serving its ServicePoint.
    baristas = [
        assets.barista("barista1", (-12.0, 8.5), counter.service_point, cfg),
        assets.barista("barista2", (-8.0, 8.5), counter.service_point, cfg),
    ]

    # Arrivals paced so the register queue forms but stays bounded (guests get
    # served before their Leave drive makes them give up).
    spawner = Spawner(
        assets.guest_archetype(cfg), ENTRANCE, max_pop, interval_ticks=(20, 50),
    )
    sim = Simulation(ctx, world, list(baristas), grid, spawner, config=cfg)
    spawner.prefill(sim.agents, ctx, cfg.population.initial)
    return sim
