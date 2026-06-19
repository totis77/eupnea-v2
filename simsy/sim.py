"""Simulation driver + a runnable coffee-shop vertical slice.

Run headless:  uv run python -m simsy.sim
"""

from __future__ import annotations

from .agents.agent import Agent
from .agents.spawning import AgentArchetype, Spawner
from .ai import utility
from .config import Config, load_config
from .core.context import SimContext
from .nav.grid import NavGrid
from .nav.locomotion import Locomotion
from .world.registry import WorldRegistry
from .world.smart_object import Affordance, SmartObject


class Simulation:
    def __init__(
        self,
        ctx: SimContext,
        world: WorldRegistry,
        agents: list[Agent],
        grid: NavGrid,
        spawner: Spawner | None = None,
        config: Config | None = None,
    ):
        self.ctx = ctx
        self.world = world
        self.agents = agents
        self.grid = grid
        self.config = config or load_config()
        self.loco = Locomotion(grid, self.config.orca, self.config.locomotion)
        self.spawner = spawner

    def step(self) -> None:
        ctx = self.ctx
        ordered = sorted(self.agents, key=lambda a: a.id)  # deterministic order
        for agent in ordered:
            agent.update_needs(ctx)
        self.ctx.events.drain()
        for agent in ordered:
            if agent.should_think(ctx):
                agent.think(self.world, ctx)
        for agent in ordered:
            agent.act(self.world, ctx)
        self.loco.update(self.agents, ctx)  # movement: paths + crowd avoidance
        self._despawn_arrivals()
        if self.spawner is not None:
            self.spawner.update(self.agents, ctx)
        ctx.tick += 1

    def _despawn_arrivals(self) -> None:
        """Remove agents that have reached an exit object (releasing its slot)."""
        for a in list(self.agents):
            target = a.blackboard.get("target")
            if target is not None and target.despawns and a.at_goal:
                target.release(a.id)
                self.agents.remove(a)

    def run(self, ticks: int) -> None:
        for _ in range(ticks):
            self.step()

    def _agent_view(self, a: Agent) -> dict:
        target = a.blackboard.get("target")
        motive_score = 0.0
        if a.active_motive is not None and target is not None:
            motive_score = utility.score(
                a.needs[a.active_motive],
                target.advertised_amount(a.active_motive),
                self.config.utility.pressure_exponent,
            )
        return {
            "id": a.id,
            "pos": (round(a.position[0], 3), round(a.position[1], 3)),
            "motive": a.active_motive,
            "node": a.active_node,
            "target": target.id if target is not None else None,
            "score": round(motive_score, 3),
            "needs": {k: round(v, 2) for k, v in sorted(a.needs.items())},
            "path": [(round(x, 2), round(y, 2)) for x, y in (a.path or [])],
        }

    def snapshot(self) -> dict:
        """Serializable state -- the seam the WebSocket emitter consumes."""
        return {
            "tick": self.ctx.tick,
            "time": round(self.ctx.time, 3),
            "agents": [
                self._agent_view(a)
                for a in sorted(self.agents, key=lambda a: a.id)
            ],
            "objects": [
                {
                    "id": o.id,
                    "kind": o.kind,
                    "pos": (round(o.position[0], 3), round(o.position[1], 3)),
                    "free": o.free_slots,
                    "slots": o.slots,
                    "affordances": sorted(o.affordances),
                }
                for o in self.world.all()
            ],
            "obstacles": list(self.grid.obstacles),
        }


def build_coffee_shop(
    config: Config | None = None,
    seed: int | None = None,
    max_population: int | None = None,
) -> Simulation:
    """Build the coffee-shop scene. Subsystem knobs come from `config`
    (config.yaml or defaults); the scene *structure* stays in code (that is
    the DSL's job). Explicit `seed`/`max_population` args override config."""
    cfg = config or load_config()
    seed = cfg.simulation.seed if seed is None else seed
    max_pop = cfg.population.max if max_population is None else max_population
    ctx = SimContext(seed=seed, dt=cfg.simulation.dt)

    world = WorldRegistry()
    world.add(
        SmartObject(
            "espresso", "CoffeeCounter", (20.0, 0.0),
            [Affordance("Caffeine", 40.0)], slots=1, interaction_ticks=20,
        )
    )
    world.add(
        SmartObject(
            "couch", "Chair", (-20.0, 0.0),
            [Affordance("Rest", 30.0)], slots=2, interaction_ticks=15,
        )
    )
    # The exit: reaching it satisfies "Leave" and despawns the agent. Plenty of
    # slots so departure never blocks. Lives at the entrance.
    entrance = (-24.0, 0.0)
    world.add(
        SmartObject(
            "door", "Exit", entrance,
            [Affordance("Leave", 100.0)], slots=12, interaction_ticks=1,
            despawns=True,
        )
    )

    # A dividing wall at x=0 with a doorway gap at y in [4, 8]. Caffeine seekers
    # on the left must detour up to the doorway to reach the espresso -- this is
    # what exercises A* (global path) and ORCA (queueing at the doorway).
    # The grid is inflated by the agent radius so bodies never clip the wall.
    grid = NavGrid(*cfg.world.bounds, cell=cfg.world.cell_size, inflate=cfg.agent.radius)
    grid.add_obstacle(-0.6, -13.0, 0.6, 4.0)
    grid.add_obstacle(-0.6, 8.0, 0.6, 13.0)

    # Guests arrive at the door, satisfy Caffeine/Rest, then "Leave" grows until
    # it dominates and they head back to the exit.
    archetype = AgentArchetype(
        name="guest",
        needs=dict(cfg.archetype.needs),
        growth=dict(cfg.archetype.growth),
        speed=cfg.agent.speed,
        radius=cfg.agent.radius,
        think_period_ticks=cfg.agent.think_period_ticks,
        spread=cfg.population.need_spread,
        utility_cfg=cfg.utility,
    )
    spawner = Spawner(
        archetype, entrance, max_pop,
        interval_ticks=tuple(cfg.population.spawn_interval_ticks),
    )
    sim = Simulation(ctx, world, [], grid, spawner, config=cfg)
    spawner.prefill(sim.agents, ctx, cfg.population.initial)  # population at tick 0
    return sim


def main() -> None:
    sim = build_coffee_shop()
    print(f"coffee-shop slice | seed={sim.ctx.seed} dt={sim.ctx.dt}s\n")
    for _ in range(120):
        sim.step()
        if sim.ctx.tick % 20 == 0:
            snap = sim.snapshot()
            print(f"t={snap['time']:>5}s tick={snap['tick']:>3}")
            for a in snap["agents"]:
                motive = a["motive"] or "-"
                node = a["node"] or "-"
                needs = " ".join(f"{k}={v:>5.1f}" for k, v in a["needs"].items())
                print(
                    f"  {a['id']:<6} {needs}  motive={motive:<8} "
                    f"node={node:<10} @({a['pos'][0]:>6.1f},{a['pos'][1]:>5.1f})"
                )
            occ = " ".join(f"{o['id']}={o['free']}/{o['slots']}" for o in snap["objects"])
            print(f"  slots: {occ}\n")


if __name__ == "__main__":
    main()
