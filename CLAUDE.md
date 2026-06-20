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
simsy/                 # THE ENGINE — reusable AI mechanics; no scene content
  config.py            # typed config + load_config(); defaults live here
  sim.py               # Simulation driver (tick loop + snapshot emitter)
  project.py           # project loader: build_project(name) → Simulation (prefers scene.yaml, else build())
  scene.py             # scene-as-data loader: YAML scene dict → Simulation (§6G); controller/recipe registries
  run.py               # generic headless runner: `python -m simsy.run [project] [ticks]`
  server.py            # WebSocket + HTTP bridge for the viewer (`python -m simsy.server`)
  core/
    context.py         # SimContext: seeded RNG + fixed dt + tick  ← determinism choke point
    events.py          # queued EventBus (drained in insertion order)
  components/          # entity components (§6D), grouped by tier
    representation.py  # Transform (pose) + NavShape (engine collision proxy) + RenderShape (viewer-only)
    state.py           # Capability/State: Drives, Locomotor, Blackboard, Role, Inventory, GroupMember, Mood
  world/
    entity.py          # Entity: id + Transform/NavShape/RenderShape + typed component bag (§6A)
    smart_object.py    # entity holding Affordance + SlotSet + opt-in Queue / ServicePoint / Portal + tags; `despawns` exits
    registry.py        # object lookup (global tier + by_tag; local hash-grid tier still a TODO)
  ai/
    utility.py         # object-advertised scorer; pressure curve, hysteresis, idle threshold
    behavior_tree.py   # Status/Sequence + Reserve/Travel/Occupy/Release/Order/Receive/Consume/Enter leaves; ATOMIC guard, OnAbort
    controller.py      # default brain (§6E): Utility(select) → BT(execute); per-target tree + recipe plans
    fsm.py             # alternative pluggable brain: FSM controller + serve_fsm (staff/barista)
    plan.py            # scripted multi-step recipes (Step: acquire/consume/use/enter) → build_plan_tree
  agents/
    agent.py           # entity composing Drives+Locomotor+Blackboard+Controller; cognition vs locomotion split
    spawning.py        # AgentArchetype (flyweight) + Spawner (seed-driven arrivals)
  nav/
    grid.py            # NavGrid: walkable grid, obstacle inflation, line-of-sight
    astar.py           # deterministic 8-dir A* + LOS path smoothing
    orca.py            # ORCA (RVO2 linear-program port): Vec2, Line, orca_velocity
    locomotion.py      # world-level movement: path following + ORCA + collision resolution
viewer/index.html      # canvas client: interpolated render + side panel showing each agent's live plan tree (steps→active leaf) + carried items
projects/              # PROJECTS — self-contained scenarios; own their assets+scene, reference simsy
  coffee_shop/
    scene.yaml         # DATA scene (§6G): walls, objects (espresso queue/couch/exit), guest archetype, spawner
  cafe/                # fuller scenario (whiteboard), fully data-driven
    scene.yaml         # staffed counter + 2 FSM baristas, coffee recipe, seating, toilet, mood, spawner
  micro/               # tiny single-feature projects for isolation testing (still Python build())
    queue/             # one contended counter + a line (the Queue feature)
    service/           # a staffed counter + barista (ServicePoint + FSM controller)
    plan/              # order coffee → sit & drink it (multi-step recipe + Inventory)
    group/             # a group that travels together (GroupMember cohesion)
    venue/             # two rooms split by a wall, crossed via a Portal
    mood/              # queue waiting builds stress → impatience (Mood)
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
  Contended objects can opt into a `Queue` (`enable_queue`): when full, the
  `Reserve` leaf joins the line (RUNNING) and advances the head into a freed slot.
  A full object stays a Utility candidate **only if it has a queue**.
- **Engine vs project boundary:** `simsy/` is reusable *mechanics* (components,
  systems, controllers, the `Simulation` driver). A **project** under
  [projects/](projects/) is a self-contained scenario that owns its *content* and
  references the engine. A scene is authored as **data** —
  [projects/coffee_shop/scene.yaml](projects/coffee_shop/scene.yaml), loaded by
  [simsy/scene.py](simsy/scene.py) (§6G); `build_project(name)` prefers a
  `scene.yaml`, else falls back to a Python `build()` (the micro feature scenes
  still use that). Phase 4 adds a GUI that edits the scene data.
- **Config vs scene boundary:** [config.yaml](config.yaml) holds subsystem *tuning*
  (ORCA, utility, population, ports…). Scene *content* (objects/walls/agents/
  archetypes/spawner) lives in a project's `scene.yaml`, not config.

## Commands

This project is **uv-managed** — always use `uv`, never bare `python`/`pip`.

```bash
uv run pytest -q                      # run the test suite
uv run python -m simsy.run            # headless: step a project, print per-tick state
uv run python -m simsy.run coffee_shop 200   # …a named project for N ticks
uv run python -m simsy.server         # serve viewer at http://localhost:8000 (coffee_shop)
uv run python -m simsy.server micro.plan     # …stream a specific project (or SIMSY_PROJECT=)
uv add <pkg>                          # add a dependency
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
| [test_queue.py](tests/test_queue.py) | Queue FIFO/wait-slots standalone; one-slot counter serializes a crowd (micro-scene) |
| [test_service.py](tests/test_service.py) | FSM + ServicePoint standalone; barista serves a line; no server ⇒ nobody served |
| [test_plan.py](tests/test_plan.py) | recipe compilation standalone; order-coffee→sit&drink across two objects with a carried item |
| [test_cafe.py](tests/test_cafe.py) | full café scene runs, serves a steady stream, keeps staff; deterministic |
| [test_group.py](tests/test_group.py) | group cohesion keeps members tighter than no cohesion; deterministic |
| [test_venue.py](tests/test_venue.py) | Portal links target; guests cross a gapless wall via the portal and get served |
| [test_mood.py](tests/test_mood.py) | Mood clamps; queue waiting builds stress; deterministic |

## Entity-component model (§6)

`Agent` and `SmartObject` are **entities composed from components**
([world/entity.py](simsy/world/entity.py)), in three tiers: Representation
(`Transform`/`NavShape`/`RenderShape`), Capability/State (`Drives`, `Locomotor`,
`Blackboard`, `Role`, `Inventory`, `GroupMember`, `Mood`; world-side `Affordance`,
`SlotSet`, `Queue`, `ServicePoint`, `Portal`), and a pluggable Controller
(`Utility→BT`, [ai/controller.py](simsy/ai/controller.py)) — or any brain with
the same `think/act` + `active_motive/active_node` interface, e.g. the
[ai/fsm.py](simsy/ai/fsm.py) `FSM` that drives staff (a barista's
`idle→brewing`). Swapping a brain is one `Agent(..., controller=…)` arg; the
engine ticks staff and patrons identically. A goal can also span several objects
via a **scripted recipe** (`agent.recipes[need]` = ordered `Step`s, [ai/plan.py](simsy/ai/plan.py)):
the controller compiles it to a BT that carries an `Inventory` item between steps
(e.g. order coffee → sit & drink). The engine reads
`Transform`+`NavShape`+components and **never `RenderShape`** (§6B headless
boundary). `Agent`/`SmartObject` expose `id`/`position`/`radius` (and the object
lifecycle) as thin accessors onto their components — see architecture doc §6.

## Known stubs / not-yet-done

- ORCA handles agent-agent only; static walls are handled by the inflated grid +
  collision resolution, not by ORCA obstacle lines.
- BT atomic-node protection (§2B): in-progress `Occupy`/`Consume` set an `ATOMIC`
  blackboard flag the controller honors (no motive switch mid-interaction); other
  nodes (Travel, queue waits) remain interruptible.
- `registry.py` is the global lookup tier only; the local Uniform Hash Grid is a TODO.
- Snapshots are full keyframes (delta encoding deferred); the GUI/DSL authoring
  layer does not exist yet.
- Walls are still raw grid obstacles, not `NavShape(static)` entities; Nav build
  doesn't yet query entities (deferred to the scene-as-data phase).
- Queue-aware utility is partial: full queue-objects stay candidates, but score
  isn't yet discounted by line length (so agents don't prefer shorter queues).
  Deferred until there are ≥2 objects serving one need to choose between.
- Portals are recipe-driven (an `enter` step), not autonomous: A* doesn't route
  across portals on its own, so a cross-venue journey must be authored as a recipe.
- Groups travel together via locomotion cohesion only; no shared group
  decision-making (members still pick their own motives independently).

When adding a tunable constant, add it to [config.py](simsy/config.py) (with a
default) and surface it in [config.yaml](config.yaml) rather than hardcoding it.
