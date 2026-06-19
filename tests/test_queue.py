"""Queueing: the Queue component in isolation, and a one-slot counter that
serializes a crowd through a single slot via a waiting line."""

from simsy.project import build_project
from simsy.world.smart_object import Queue


# --- Queue component, standalone (no SmartObject, no agents) ---------------
def test_queue_is_fifo_and_assigns_trailing_slots():
    q = Queue(anchor=(6.0, 0.0), step=(-1.5, 0.0))
    assert q.join("a") == 0
    assert q.join("b") == 1
    assert q.join("c") == 2
    assert q.join("b") == 1                 # idempotent: already in line
    assert q.head() == "a"
    assert q.wait_slot("a") == (6.0, 0.0)
    assert q.wait_slot("c") == (3.0, 0.0)   # anchor + 2*step
    assert len(q) == 3


def test_queue_leave_shuffles_everyone_forward():
    q = Queue(anchor=(0.0, 0.0), step=(0.0, -1.0))
    for aid in ("a", "b", "c"):
        q.join(aid)
    q.leave("a")
    assert q.head() == "b"
    assert q.index_of("b") == 0 and q.index_of("c") == 1
    assert q.wait_slot("c") == (0.0, -1.0)  # c moved from index 2 to 1
    assert "a" not in q


# --- micro-scene: a crowd through one slot ---------------------------------
def test_one_slot_counter_serializes_the_crowd():
    sim = build_project("micro.queue", n_agents=4)
    counter = sim.world.get("counter")

    line_ever_formed = False
    for _ in range(600):
        sim.step()
        # The single slot is never double-booked, no matter how many wait.
        assert counter.free_slots >= 0
        assert len(counter.slot_set._occupants) <= 1
        if len(counter.queue) >= 1:
            line_ever_formed = True

    assert line_ever_formed, "agents should have had to wait in line"
    # Liveness: everyone got through the single slot and then departed. If anyone
    # had been stuck behind a blocker, they'd never reach the exit to despawn.
    assert len(sim.agents) == 0
    assert len(counter.queue) == 0 and counter.free_slots == 1


def test_queue_scene_is_deterministic():
    def trace():
        sim = build_project("micro.queue", n_agents=4)
        out = []
        for _ in range(200):
            sim.step()
            out.append(tuple(round(c, 4) for a in sim.agents for c in a.position))
        return out

    assert trace() == trace()
