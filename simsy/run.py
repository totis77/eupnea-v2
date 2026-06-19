"""Generic headless runner: step any project and print per-tick state.

    uv run python -m simsy.run [project] [ticks]

Defaults to the coffee-shop project for 120 ticks. The runner is engine-side and
scene-agnostic — it loads whichever project you name and prints its snapshots.
"""

from __future__ import annotations

import sys

from .project import build_project


def _print_snapshot(snap: dict) -> None:
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


def run(project: str = "coffee_shop", ticks: int = 120) -> None:
    sim = build_project(project)
    print(f"{project} | seed={sim.ctx.seed} dt={sim.ctx.dt}s\n")
    for _ in range(ticks):
        sim.step()
        if sim.ctx.tick % 20 == 0:
            _print_snapshot(sim.snapshot())


def main() -> None:
    project = sys.argv[1] if len(sys.argv) > 1 else "coffee_shop"
    ticks = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    run(project, ticks)


if __name__ == "__main__":
    main()
