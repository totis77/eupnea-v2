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

## Status log
- _(start)_ — plan created; beginning Task 1.
- Task 1 done — `NavGrid(inflate=)`; doorway widened to y∈[4,8]; agents cross at
  doorway center, bodies clear the wall.
- Task 2 done — `simsy/nav/orca.py` (RVO2 LP port); Locomotion rewired to ORCA;
  head-on avoidance + determinism tested.
- Task 3 done — `AgentArchetype` + `Spawner`; Leave-drive/Exit departures; dynamic
  capped population, deterministic timeline.
- **All 12 tests green. All three tasks verified in the live viewer.**
