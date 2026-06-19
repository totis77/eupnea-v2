"""Mood/affect: the Mood component clamps, and queue waiting builds stress that
feeds impatience."""

from simsy.components import Mood
from simsy.project import build_project


def test_mood_clamps_to_0_100():
    m = Mood()
    m.adjust(-5.0)
    assert m.stress == 0.0
    m.adjust(140.0)
    assert m.stress == 100.0


def test_waiting_in_a_queue_builds_stress():
    sim = build_project("micro.mood", n_agents=5)
    peak_stress = 0.0
    for _ in range(300):
        sim.step()
        for a in sim.agents:
            if a.mood is not None:
                peak_stress = max(peak_stress, a.mood.stress)
    assert peak_stress > 25.0, "agents stuck in line should accumulate stress"


def test_mood_scene_is_deterministic():
    def trace():
        sim = build_project("micro.mood", n_agents=5)
        out = []
        for _ in range(200):
            sim.step()
            out.append(tuple(
                round(a.mood.stress, 3) for a in sim.agents if a.mood is not None
            ))
        return out

    assert trace() == trace()
