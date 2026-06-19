"""Spawn/despawn scheduling: capped, dynamic, and deterministic."""

from simsy.project import build_project


def test_population_never_exceeds_cap():
    sim = build_project("coffee_shop", max_population=6)
    peak = 0
    for _ in range(800):
        sim.step()
        peak = max(peak, len(sim.agents))
    assert peak <= 6
    assert peak >= 2, "spawner should have populated the scene"


def test_agents_both_spawn_and_despawn():
    sim = build_project("coffee_shop")
    ever_seen, despawned = set(), 0
    for _ in range(900):
        before = {a.id for a in sim.agents}
        sim.step()
        after = {a.id for a in sim.agents}
        ever_seen |= after
        despawned += len(before - after)
    assert len(ever_seen) > 8, "more agents should pass through than the cap"
    assert despawned > 0, "agents should reach the exit and despawn"


def test_population_timeline_is_deterministic():
    def ids_over_time(seed):
        sim = build_project("coffee_shop", seed=seed)
        trace = []
        for _ in range(400):
            sim.step()
            trace.append(tuple(sorted(a.id for a in sim.agents)))
        return trace

    assert ids_over_time(42) == ids_over_time(42)
