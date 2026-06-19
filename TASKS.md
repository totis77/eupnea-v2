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
- [ ] 2C **ServicePoint + staff (FSM controller).** A barista entity serves the
      counter, driven by an FSM controller — proves the Controller is pluggable
      beyond Utility→BT (§6E).
- [ ] 2D **Multi-step interaction plans** (queue → order → wait → receive).
- [ ] 2E **Groups** (`GroupMember`): arrive and move together.
- [ ] 2F **Portals / multi-venue** (`Portal`): multiple venues, cross-venue nav.
- [ ] 2G *(stretch)* mood/affect modulating utility.

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
  a Leave drive). 24/24 green; coffee-shop line forms and drains. Next: 2C
  ServicePoint + staff (FSM controller).
