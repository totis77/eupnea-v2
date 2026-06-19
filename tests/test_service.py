"""Staffed service: the FSM controller and ServicePoint in isolation, plus a
barista serving a line of guests — and the dependency that without a server,
nobody is served."""

from types import SimpleNamespace

from simsy.ai.fsm import FSM, serve_fsm
from simsy.project import build_project
from simsy.world.smart_object import ServicePoint


# --- FSM controller, standalone --------------------------------------------
def test_fsm_runs_states_and_transitions():
    seen = []

    def a(agent, world, ctx):
        seen.append("a")
        return "b"

    def b(agent, world, ctx):
        seen.append("b")
        return None  # stay in b

    fsm = FSM("a", {"a": a, "b": b})
    agent = SimpleNamespace(blackboard={})
    assert fsm.active_motive == "a" and fsm.active_node == "a"
    fsm.act(agent, None, None)
    assert fsm.state == "b"
    fsm.act(agent, None, None)
    assert fsm.state == "b"            # stayed
    assert seen == ["a", "b"]


def test_serve_fsm_brews_orders_one_at_a_time():
    sp = ServicePoint(pickup=(0.0, 0.0))
    sp.place_order("g1")
    sp.place_order("g2")
    fsm = serve_fsm(brew_ticks=2)
    barista = SimpleNamespace(blackboard={"station": sp})

    fsm.act(barista, None, None)                 # idle -> begins g1
    assert fsm.state == "brewing"
    fsm.act(barista, None, None)                 # brewing (1 left)
    fsm.act(barista, None, None)                 # brewing done -> g1 ready, idle
    assert sp.is_ready("g1") and fsm.state == "idle"
    fsm.act(barista, None, None)                 # idle -> begins g2
    assert fsm.state == "brewing" and not sp.is_ready("g2")


# --- ServicePoint order pipeline, standalone -------------------------------
def test_servicepoint_pipeline_is_fifo_and_cancelable():
    sp = ServicePoint(pickup=(1.0, 2.0))
    sp.place_order("a")
    sp.place_order("b")
    sp.place_order("a")                 # idempotent
    assert sp.next_order() == "a"
    sp.begin("a")
    assert sp.next_order() == "b" and sp._in_progress == "a"
    sp.mark_ready("a")
    assert sp.is_ready("a") and sp._in_progress is None
    assert sp.collect("a") is True and sp.collect("a") is False
    sp.cancel("b")
    assert sp.next_order() is None


# --- scene: a barista serves the line --------------------------------------
def test_barista_serves_the_whole_line():
    sim = build_project("micro.service", n_agents=3, with_barista=True)
    min_caffeine: dict[str, float] = {}
    for _ in range(600):
        sim.step()
        for a in sim.agents:
            if a.id.startswith("q"):
                c = a.drives.needs["Caffeine"]
                min_caffeine[a.id] = min(min_caffeine.get(a.id, 1e9), c)

    assert set(min_caffeine) == {"q0", "q1", "q2"}
    assert all(v < 20.0 for v in min_caffeine.values()), "every guest got served"
    assert [a.id for a in sim.agents] == ["barista"], "served guests left; staff stays"


def test_without_a_barista_nobody_is_served():
    sim = build_project("micro.service", n_agents=3, with_barista=False)
    sp = sim.world.get("counter").service_point
    orders_placed = False
    for _ in range(150):
        sim.step()
        assert len(sp._ready) == 0, "no order can be fulfilled without a server"
        assert all(
            a.drives.needs["Caffeine"] >= 50.0
            for a in sim.agents if a.id.startswith("q")
        ), "no Caffeine drained: no one was served"
        if sp._pending or sp._in_progress is not None:
            orders_placed = True
    assert orders_placed, "guests should have ordered (orders just go unfulfilled)"


def test_service_scene_is_deterministic():
    def trace():
        sim = build_project("micro.service", n_agents=3, with_barista=True)
        out = []
        for _ in range(200):
            sim.step()
            out.append(tuple(round(c, 4) for a in sim.agents for c in a.position))
        return out

    assert trace() == trace()
