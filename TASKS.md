# Task Plan

Living checklist for the current work stream. Subtasks are filled in
immediately before each task is executed.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Task 1 — Inflate walls for collision avoidance  [x]
**Goal:** an agent's *body* (radius) must never overlap a wall, not just its center.
Pathfinding and collision checks should treat obstacles as expanded by the agent radius,
while rendering still shows the true wall geometry.

- [x] 1.1 Add an `inflate` radius to `NavGrid`; rasterize obstacles expanded by it,
      but keep the raw rect in `self.obstacles` (for rendering).
- [x] 1.2 Pass the agent radius as inflation in `build_coffee_shop`; widen the
      doorway gap to y∈[4,8] so it stays passable after inflation.
- [x] 1.3 Verified: 7 tests pass; alice now crosses at y≈5.0 (doorway center) vs the
      old y≈3.6 corner-clip; no-clip test still holds. Viewer screenshot deferred to
      end of Task 2 (same restart).

## Task 2 — Replace repulsion avoidance with ORCA  [x]
**Goal:** swap the ad-hoc repulsion in Locomotion for proper Optimal Reciprocal
Collision Avoidance (linear-program velocity solve), keeping determinism.

- [x] 2.1 New `simsy/nav/orca.py`: `Vec2`, `Line`, and the RVO2 2D linear-program
      solver (`linear_program1/2/3`).
- [x] 2.2 `orca_velocity(...)`: build a half-plane per neighbor, solve the LP.
- [x] 2.3 Rewired `Locomotion`: pos+vel snapshot, seek = preferred velocity, ORCA
      against in-range neighbors; idle/occupying agents are static neighbours.
- [x] 2.4 Tests (9 pass): head-on agents avoid (min dist ≥ 1.05, no interpenetration);
      ORCA deterministic; walls still no-clip.
- [x] 2.5 Verified in viewer: doorway clear, paths route through, no console errors.

## Task 3 — Spawn/despawn scheduling  [x]
**Goal:** agents arrive over time (seed-driven) and leave when done, so the cast
isn't a fixed three and ORCA faces a real crowd.

- [x] 3.1 `AgentArchetype` (flyweight) — base needs/growth/speed + `spawn()` that
      rng-varies initial drives.
- [x] 3.2 Departure via existing utility machinery: "Leave" drive (only grows) +
      `Exit` SmartObject (`despawns=True`) advertising Leave; agents route to the
      exit when Leave dominates — no special-case AI code.
- [x] 3.3 `Spawner` — seed-driven inter-arrival schedule, capped population.
- [x] 3.4 Wired into `Simulation.step`: `_despawn_arrivals` + `spawner.update`;
      `build_coffee_shop` now starts empty and fills in.
- [x] 3.5 Tests (12 pass): cap respected; agents spawn AND despawn; population
      timeline deterministic; full replay still bit-identical.
- [x] 3.6 Verified in viewer: dynamic crowd (8 guests), Leave→door departures,
      ORCA keeping the cluster apart, exit slot-viz suppressed. No console errors.

---

## Phase 1 — Parity refactor to the Entity-Component model  [~]
**Goal:** re-express today's `SmartObject`/`Agent` as `Entity = Transform +
RenderShape + NavShape + [components]` in three tiers (architecture doc §6),
with **zero new features**. All 14 existing tests must stay green after every
slice — they are the parity pins. Each slice is independently committable.

Decisions:
- **Where things live:** `simsy/components/` (new) holds the Capability/State +
  Representation component dataclasses; the brain stays in `simsy/ai/` as
  `controller.py` (it wraps `utility.py` + `behavior_tree.py`). `Entity` base in
  `simsy/world/entity.py`.
- **Parity, not redesign:** keep public surfaces (`Agent.position`,
  `agent.needs`, `agent.active_motive/active_node`, `agent.set_goal`,
  `SmartObject.reserve/occupy/release/free_slots`, `sim.snapshot()`) working via
  delegation so the engine/systems/tests are untouched until the very end.

- [x] P1.1 **Controller component (keystone).** Extracted the think/adopt/abort/
      clear/score glue from `Agent` into `simsy/ai/controller.py::Controller`
      (Utility=select → BT=execute, §6E). `Agent` holds `self.controller` and
      delegates `think()/act()`; `active_motive/active_node` are now properties
      reading the controller. 14/14 tests green — replay bit-identical.
- [x] P1.2 **Agent Capability/State tier.** New `simsy/components/` package:
      `Drives` (needs+growth+update), `Locomotor` (speed/goal/path/vel/at_goal +
      set/clear goal), `Blackboard` (dict subclass). `Agent` now holds these;
      retargeted every reader (controller, BT leaves, utility, locomotion, sim)
      and the orca test — no shims left. `radius`/`position` stay inline (they're
      Representation-tier, P1.3). 14/14 green; replay bit-identical.
- [x] P1.3 **Entity + Representation tier.** New `components/representation.py`
      (`Transform` pos+facing, `NavShape` radius+static, `RenderShape` viewer-only)
      and `world/entity.py` (`Entity`: id + 3 representation slots + a typed
      component bag via `add/get/has`). `Agent` and `SmartObject` now *compose* an
      `Entity` (not subclass); `id`/`position`/`radius` are thin pose accessors
      onto it — so locomotion/sim/BT/tests needed no call-site changes. Agents are
      dynamic NavShapes (ORCA), objects static. 14/14 green; headless run identical.
- [x] P1.4 **SmartObject → entity with data components.** New `SlotSet`
      component (slot count + `_reserved`/`_occupants` + reserve/occupy/release)
      registered on the object's entity; `Affordance` stays the advertised-need
      component. `SmartObject` keeps its full method surface delegating one line
      each (per chosen API) — so utility, BT leaves, and `test_reservation_lifecycle`
      are untouched. World-side mirror of the agent split. 14/14 green.
- [—] P1.5 **Systems read by component type** — *folded/deferred.* The kept
      `SmartObject` facade + sanctioned pose accessors made "remove facades"
      moot, and the only remaining §6F item (Nav build querying `NavShape(static)`)
      needs walls-as-entities, which is a feature (scene-as-data), not parity.
- [x] P1.6 **Close-out.** Added `tests/test_components.py` (SlotSet/Drives/
      Locomotor in isolation); updated CLAUDE.md layout + new EC-model section +
      test table, and architecture.md §6 status → "implemented (Phase 1 complete)".
      20/20 green; viewer re-verified (no console errors); committed on branch
      `phase-1-entity-components` (3690526).

---

## Phase 2 — Features as components (each behind a micro-scene + test)
**Goal:** grow the whiteboard scenario (queues, baristas, groups, venues) one
capability at a time. Each feature = new component(s) + a micro-scene project +
isolation tests, with all existing tests green. Mode: slice-by-slice review;
scenes expressed as Python `build()` for now (data-driven deferred to Phase 3).

- [x] 2A **Project structure (engine ↔ project boundary).** `simsy/` is now
      engine-only mechanics; scenarios live under `projects/` as self-contained
      folders that own assets+scene and reference the engine. Added
      `simsy/project.py` (`build_project(name)` loader) and `simsy/run.py`
      (generic headless runner); relocated the coffee shop to
      `projects/coffee_shop/` (`assets.py` = object kinds + archetype;
      `project.py` = scene placement). Removed `build_coffee_shop`/`main` from
      `sim.py`; retargeted `server.py` + 3 test files. 20/20 green; runner output
      byte-identical; server boots clean. Per-project `config.yaml` deferred.
- [x] 2B **Queue.** `Queue` capability component (FIFO line + indexed wait-slots
      trailing from the object) added to `world/smart_object.py`; `SmartObject.
      enable_queue()` opts in. The `Reserve` BT leaf is now queue-aware: when full
      it joins the line (RUNNING, standing in its assigned spot) and advances the
      head into a freed slot; `OnAbort` leaves the line. Utility now keeps a full
      object as a candidate **iff it has a queue** (the mandatory half of
      queue-aware utility; the shorter-line *discount* is deferred to when ≥2
      counters exist). Espresso enables a queue; new `projects/micro/queue/`
      isolates it. Surfaced + fixed a real issue: a served agent with no next
      motive squats on the slot and blocks the line — the scene needs a reason to
      leave (Leave drive + exit), which the micro-scene now has. 24/24 green;
      coffee-shop line forms/shuffles/drains; determinism holds.
- [x] 2C **ServicePoint + staff (FSM controller).** New `ai/fsm.py` (generic
      `FSM` controller + `serve_fsm` staff brain), `Role` component, and world-side
      `ServicePoint` (order ledger: pending→in-progress→ready + pickup spot).
      Guest interaction with a staffed object is now Reserve→Travel→**Order**→
      **Receive** (new BT leaves; `tree_for(obj)` selects self-service vs staffed).
      `Agent(..., controller=…)` lets a barista run an FSM instead of Utility→BT —
      ticked identically by the engine, proving the Controller slot is pluggable
      (§6E). Isolated in `projects/micro/service/`; `with_barista=False` shows
      orders pile up unserved. 30/30 green; headless run shows the full
      queue→order→brew→pickup→leave loop; determinism holds. Coffee-shop espresso
      left self-serve for now (optional follow-up to staff it).
- [x] 2D **Multi-step interaction plans.** Scripted recipes: `agent.recipes[need]`
      = ordered `Step`s ([ai/plan.py](simsy/ai/plan.py)); `build_plan_tree`
      compiles a recipe into a BT, resolving each step's object by `tag`
      (`registry.by_tag`). New `Inventory` component carries an item between
      steps; new BT leaves `SetTarget`/`ReceiveItem`/`ConsumeItem`; controller
      adopts a plan when the need has a recipe and anchors hysteresis to the
      motive source (not the per-step target). Demonstrator
      `projects/micro/plan/`: order coffee at the counter (carry it) → sit & drink
      it at a seat (Caffeine satisfied only on consume). Surfaced + fixed the §2B
      gap: a rising drive interrupted drinking mid-sip → added an `ATOMIC` guard
      so `Occupy`/`Consume` can't be interrupted. 35/35 green; determinism holds.
- [x] 2E **Groups** (`GroupMember`): Locomotion steers members toward their
      group centroid (config `group_cohesion`), so they travel as a cluster.
      `projects/micro/group/`; cohesion reduces group spread vs none.
- [x] 2F **Portals / multi-venue** (`Portal`): a `Portal` component + `Enter` BT
      leaf teleport an agent to the linked venue; recipe gains `enter`/`use`
      actions. `projects/micro/venue/` = two rooms split by a gapless wall,
      crossed only via the portal. (Recipe-driven, not autonomous A* routing.)
- [x] 2G **Mood/affect** (`Mood`): stress rises while queue-waiting, eases
      otherwise, and feeds the Leave drive (impatience). `MoodCfg` knobs; surfaced
      in the snapshot + viewer (stress bar); wired into the café guests.
      `projects/micro/mood/`.

## Phase 3 — Scene as data
**Goal:** a scene is a YAML data file loaded by a generic loader into a
`Simulation`, replacing per-project Python `build()`. Fully data-driven incl.
controllers + recipes. This file is the DSL/AST the Phase 4 GUI will edit.

- [x] 3A–3C **Loader + schema** ([simsy/scene.py](simsy/scene.py)): `load_scene`
      / `load_scene_file` build a Simulation from a scene dict — world bounds,
      walls, objects (affordances/slots/tags + opt-in queue/service/portal),
      fixed agents/staff with controllers via a named `CONTROLLERS` registry
      (`serve_fsm` + station wiring), archetypes (needs/growth/recipes/mood),
      spawner. Recipes are `Step` lists in data.
- [x] 3D **Convert projects:** `projects/coffee_shop/scene.yaml` and
      `projects/cafe/scene.yaml` author the scenes as data; `build_project`
      prefers `scene.yaml` (else falls back to `build()` for the micro scenes).
      Deleted the now-dead `coffee_shop`/`cafe` `project.py`+`assets.py`. Café is
      fully data-driven (baristas, recipes, mood). 45/45 green; both scenes load
      and run live in the viewer.
- [ ] 3E **Save/serialize** (scene dict → YAML) — deferred to Phase 4: the GUI
      edits the data dict and writes it back (`yaml.dump`); reconstructing the
      authoring params from runtime state would be lossy, so save operates on the
      data, not the live Simulation.

## Phase 4 — GUI authoring tool
**Goal:** a browser editor that loads `scene.yaml`, edits entities/components
visually, saves it back, and runs it — driving the same engine. Separate
`editor.html`; Save overwrites `scene.yaml` (keeps one `.bak`).

- [x] 4A **Load + render + save round-trip (keystone).** Server gained a scene
      API on the existing HTTP bridge: `GET /scenes`, `GET /scene/<name>`,
      `POST /scene/<name>` ([server.py](simsy/server.py)), backed by
      `scene.read_scene/write_scene/list_scenes` ([scene.py](simsy/scene.py),
      `.bak` on save). New [viewer/editor.html](viewer/editor.html) loads a scene,
      renders it statically (objects/walls/staff/entrance), supports **drag-move,
      add, and delete objects**, and Save persists to YAML. Verified end-to-end
      (moved an object → saved ✓ → re-fetched the change). 48/48 green.
- [x] 4C **Property panel.** The inspector is editable: id / kind / pos / slots /
      tags / affordances, and toggles for queue · service · portal (+ target) ·
      despawns. Edits update the scene dict live and re-render (focus preserved).
- [x] 4D **Walls + spawner/entrance** editing. Unified selection model
      (object · wall · entrance). "+ wall" mode draws a rect by dragging; a
      selected wall can be moved, corner-resized (handle), deleted, or edited via
      a coords inspector; the entrance is a draggable marker with an x,y inspector.
- [x] 4E **Run from the editor.** Server `POST /run` builds a Simulation from the
      posted scene into a swappable `_sim`; the editor's "Run" button posts the
      current (unsaved) scene and opens the live viewer streaming it; viewer HUD
      has an "✎ edit" link back. Verified slots=4 edit streamed without saving.
- [x] 4F **Archetypes / recipes / spawner editing.** A "⚙ population" panel edits
      scene-level config: spawner (archetype, max pop, initial, interval), the
      selected archetype's needs / growth / with-mood, and recipes — per-need
      ordered step rows (tag · action · item · amount) with add/remove step and
      add/remove recipe. Writes into the scene dict, so Save/Run include it.

**Phase 4 complete.** The editor can author a whole scenario from scratch —
geometry (walls, entrance), objects + their components, and the population
(archetypes/recipes/spawner) — then Save to `scene.yaml` or Run it live.

## Status log
- _(start)_ — plan created; beginning Task 1.
- Task 1 done — `NavGrid(inflate=)`; doorway widened to y∈[4,8]; agents cross at
  doorway center, bodies clear the wall.
- Task 2 done — `simsy/nav/orca.py` (RVO2 LP port); Locomotion rewired to ORCA;
  head-on avoidance + determinism tested.
- Task 3 done — `AgentArchetype` + `Spawner`; Leave-drive/Exit departures; dynamic
  capped population, deterministic timeline.
- **All 12 tests green. All three tasks verified in the live viewer.**
- Phase 1 started — P1.1 (Controller component) done: brain extracted from
  `Agent` into `ai/controller.py`; 14/14 tests still bit-identical.
- P1.2 (agent Capability/State tier) done — `Drives`/`Locomotor`/`Blackboard` in
  new `simsy/components/`; all readers retargeted (no shims); 14/14 green.
- P1.3 (Entity + Representation tier) done — `Transform`/`NavShape`/`RenderShape`
  + `Entity` substrate; `Agent`/`SmartObject` compose an entity, pose via thin
  accessors; 14/14 green, headless run identical.
- P1.4 (SmartObject data components) done — `SlotSet` component owns the
  reservation lifecycle; `SmartObject` delegates; 14/14 green.
- **Phase 1 complete.** P1.5 folded (its intent was moot / Phase-2 scope); P1.6
  closed out: isolation tests added (20/20 green), docs updated, viewer verified,
  committed on branch `phase-1-entity-components` (3690526). `Agent`/`SmartObject`
  are now entities composed from Representation + Capability/State + Controller
  components — the §6 substrate the future scene-as-data/GUI layers will author.
- **Phase 2 started.** 2A (project structure) done — engine↔project boundary:
  `simsy/` = mechanics, `projects/coffee_shop/` = self-contained scenario
  (assets + scene) loaded via `simsy.project.build_project`; generic
  `python -m simsy.run` runner. 20/20 green, output byte-identical.
- 2B (Queue) done — `Queue` component + queue-aware `Reserve` leaf + utility
  keeping full queue-objects as candidates; `projects/micro/queue/` isolation
  scene. Found/fixed the "served agent squats on the slot" deadlock (scene needs
  a Leave drive). 24/24 green; coffee-shop line forms and drains.
- 2C (ServicePoint + staff) done — generic `FSM` controller proves the Controller
  slot is pluggable (barista runs idle→brewing, ticked like patrons); world-side
  `ServicePoint` order ledger + `Role`; guest flow Reserve→Travel→Order→Receive.
  `projects/micro/service/` isolates it (toggle `with_barista`). 30/30 green;
  full order→brew→pickup→leave loop verified headless.
- 2D (multi-step plans) done — scripted recipes compiled to BTs (`ai/plan.py`),
  `Inventory` carries items between objects, tags + `by_tag` locate step targets;
  `projects/micro/plan/` = order coffee → sit & drink. Fixed §2B mid-interaction
  interruption with an `ATOMIC` guard. 35/35 green.
- Viewer: side panel now renders each agent's live plan tree (steps→active leaf)
  + carried items, data-driven from a new `plan_view` in the snapshot. Server
  takes a project arg (`python -m simsy.server <project>`); launch configs added.
- **`projects/cafe/`** (whiteboard scenario) assembled from 2A–2D: entry/exit,
  staffed counter (queue + ServicePoint, slots=3) with 2 FSM baristas, varied
  seating (couch/tables/coworking) drunk via the coffee recipe, a toilet (new
  Bladder need), continuous spawner. Plan step-resolution now picks the nearest
  *available* object (so guests spread across seats); fixed a ServicePoint orphan-
  ready leak (drinks for guests who left are discarded). ~80% of guests served;
  37/37 green; live via `simsy-cafe-viewer`. Deferred per roadmap: groups (2E),
  other venues/portals (2F), literal cashier↔pickup-bar split.
- **Phase 2 complete.** 2E groups (locomotion cohesion), 2F portals/multi-venue
  (`Portal` + `Enter` + recipe `enter`/`use`), 2G mood (stress→impatience, in the
  café + viewer stress bar). Each behind a micro-scene + tests. 45/45 green.
  Remaining as future work (noted in CLAUDE stubs): autonomous portal routing in
  A*, shared group decision-making, café cashier↔pickup split, scene-as-data
  (Phase 3) and the GUI (Phase 4).
