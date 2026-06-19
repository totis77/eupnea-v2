# CLAUDE.md

Guidance for working in this repo. Read [docs/architecture.md](docs/architecture.md)
first — it is the source of truth for design decisions; this file maps that design
onto the code.

## What this is

`simsy` is a **headless, deterministic** engine for multi-character systemic
simulations (coffee shops, airports). Decision-making is a hybrid AI:
**object-advertised Utility** ("what to do") selects a motive/object, a
**Behavior Tree** ("how to do it") executes it, and **Smart Objects** hold the
interaction logic. A separate web viewer renders the engine's state stream.

Pipeline: `Utility → Behavior Tree → Smart Object lifecycle`, with a world-level
`Navigation/Locomotion` subsystem (A* + ORCA) moving the agents.

## Layout

```
docs/architecture.md   # design source of truth (read first)
config.yaml            # tunable subsystem knobs (NOT scene content)
simsy/
  config.py            # typed config + load_config(); defaults live here
  sim.py               # Simulation driver + build_coffee_shop() scene + `python -m simsy.sim`
  server.py            # WebSocket + HTTP bridge for the viewer (`python -m simsy.server`)
  core/
    context.py         # SimContext: seeded RNG + fixed dt + tick  ← determinism choke point
    events.py          # queued EventBus (drained in insertion order)
  components/          # entity components (§6D), grouped by tier
    representation.py  # Transform (pose) + NavShape (engine collision proxy) + RenderShape (viewer-only)
    state.py           # Capability/State tier: Drives, Locomotor, Blackboard (agent-side)
  world/
    entity.py          # Entity: id + Transform/NavShape/RenderShape + typed component bag (§6A)
    smart_object.py    # entity holding Affordance + SlotSet (Reserve→Occupy→Release); `despawns` exits
    registry.py        # object lookup (global tier; local hash-grid tier still a TODO)
  ai/
    utility.py         # object-advertised scorer; pressure curve, hysteresis, idle threshold
    behavior_tree.py   # Status/Sequence + Reserve/Travel/Occupy/Release leaves, OnAbort
    controller.py      # the pluggable brain (§6E): Utility(select) → BT(execute) glue
  agents/
    agent.py           # entity composing Drives+Locomotor+Blackboard+Controller; cognition vs locomotion split
    spawning.py        # AgentArchetype (flyweight) + Spawner (seed-driven arrivals)
  nav/
    grid.py            # NavGrid: walkable grid, obstacle inflation, line-of-sight
    astar.py           # deterministic 8-dir A* + LOS path smoothing
    orca.py            # ORCA (RVO2 linear-program port): Vec2, Line, orca_velocity
    locomotion.py      # world-level movement: path following + ORCA + collision resolution
viewer/index.html      # canvas client: interpolated render + debug overlays (trees, tethers, slots)
tests/                 # pytest suite (see below)
```

## Invariants — do not break these

- **Determinism is the headline feature.** All time and randomness flow through
  `SimContext` ([core/context.py](simsy/core/context.py)): use `ctx.rng` and
  `ctx.dt`, never `random.*`, `time.*`, or `Date.now`. Same seed ⇒ bit-identical
  replay; [tests/test_determinism.py](tests/test_determinism.py) enforces it.
- **Tick model:** fixed-timestep logic in `Simulation.step()`
  ([sim.py](simsy/sim.py)); rendering is decoupled. Step order matters:
  needs → events → think → act → locomotion → despawn → spawn.
- **Locomotion reads a snapshot, then integrates.** ORCA velocities are computed
  from a read-only position+velocity snapshot taken at the top of the tick, then
  positions are integrated — this is what keeps avoidance reciprocal and
  order-independent. Don't mutate positions mid-pass.
- **Cognition vs locomotion split:** the BT `Travel` leaf only sets a goal and
  polls arrival; actual movement lives in [nav/locomotion.py](simsy/nav/locomotion.py).
- **Reservation lifecycle:** reserve a slot *before* pathfinding; always release on
  abort/despawn (`OnAbort` in the BT). See [world/smart_object.py](simsy/world/smart_object.py).
- **Config vs scene boundary:** [config.yaml](config.yaml) holds subsystem *tuning*
  (ORCA, utility, population, ports…). Scene *content* (which objects/walls exist)
  stays in `build_coffee_shop()` — that is the future DSL's responsibility, not config.

## Commands

This project is **uv-managed** — always use `uv`, never bare `python`/`pip`.

```bash
uv run pytest -q                 # run the test suite
uv run python -m simsy.sim       # headless: print per-tick state
uv run python -m simsy.server    # serve viewer at http://localhost:8000
uv add <pkg>                     # add a dependency
```

The preview server is configured in [.claude/launch.json](.claude/launch.json)
as `simsy-viewer`.

## Tests

| File | Covers |
|---|---|
| [test_determinism.py](tests/test_determinism.py) | bit-identical replay; reservation lifecycle |
| [test_nav.py](tests/test_nav.py) | A* detours, no blocked-cell crossings, agents never clip walls |
| [test_orca.py](tests/test_orca.py) | head-on avoidance without interpenetration; ORCA determinism |
| [test_scheduling.py](tests/test_scheduling.py) | population cap, spawn+despawn, deterministic timeline |
| [test_config.py](tests/test_config.py) | defaults when absent, partial override, unknown-key tolerance |
| [test_components.py](tests/test_components.py) | components driven in isolation: SlotSet lifecycle, Drives growth/clamp, Locomotor goal/clear |

## Entity-component model (§6)

`Agent` and `SmartObject` are **entities composed from components**
([world/entity.py](simsy/world/entity.py)), in three tiers: Representation
(`Transform`/`NavShape`/`RenderShape`), Capability/State (`Drives`, `Locomotor`,
`Blackboard`; world-side `Affordance`, `SlotSet`), and a pluggable Controller
(`Utility→BT`, [ai/controller.py](simsy/ai/controller.py)). The engine reads
`Transform`+`NavShape`+components and **never `RenderShape`** (§6B headless
boundary). `Agent`/`SmartObject` expose `id`/`position`/`radius` (and the object
lifecycle) as thin accessors onto their components — see architecture doc §6.

## Known stubs / not-yet-done

- ORCA handles agent-agent only; static walls are handled by the inflated grid +
  collision resolution, not by ORCA obstacle lines.
- BT atomic-node protection (§2B) is not enforced — interrupts can abort mid-interaction.
- `registry.py` is the global lookup tier only; the local Uniform Hash Grid is a TODO.
- Snapshots are full keyframes (delta encoding deferred); the GUI/DSL authoring
  layer does not exist yet.
- Walls are still raw grid obstacles, not `NavShape(static)` entities; Nav build
  doesn't yet query entities (deferred to the scene-as-data phase).

When adding a tunable constant, add it to [config.py](simsy/config.py) (with a
default) and surface it in [config.yaml](config.yaml) rather than hardcoding it.
