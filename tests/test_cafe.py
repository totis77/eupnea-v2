"""The café scene: a fuller scenario combining queue + staffed ServicePoint +
FSM baristas + multi-step coffee recipe + seating + toilet + spawner. Smoke +
determinism level — the individual mechanics are covered by their own tests."""

from simsy.project import build_project


def test_cafe_runs_serves_guests_and_keeps_staff():
    sim = build_project("cafe", seed=42)
    drank: set[str] = set()
    prev: dict[str, float] = {}
    peak_pop = 0
    for _ in range(2000):
        sim.step()
        peak_pop = max(peak_pop, len(sim.agents))
        for a in sim.agents:
            if not a.id.startswith("guest"):
                continue
            c = a.drives.needs["Caffeine"]
            if a.id in prev and c < prev[a.id] - 1:  # Caffeine dropped => drank
                drank.add(a.id)
            prev[a.id] = c

    assert peak_pop <= 16, "population stays within the cap (incl. 2 baristas)"
    assert len(drank) >= 10, "the staffed counter should serve a steady stream"
    ids = {a.id for a in sim.agents}
    assert {"barista1", "barista2"} <= ids, "staff don't leave"


def test_cafe_is_deterministic():
    def timeline(seed: int):
        sim = build_project("cafe", seed=seed)
        out = []
        for _ in range(300):
            sim.step()
            out.append(tuple(sorted(a.id for a in sim.agents)))
        return out

    assert timeline(7) == timeline(7)
