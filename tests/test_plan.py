"""Multi-step plans: recipe compilation in isolation, and a guest that orders a
coffee then sits and drinks it (a two-object plan with a carried item)."""

from simsy.ai.plan import Step, build_plan_tree
from simsy.project import build_project
from simsy.world.registry import WorldRegistry
from simsy.world.smart_object import Affordance, SmartObject


# --- recipe compilation, standalone ----------------------------------------
def _two_object_world() -> WorldRegistry:
    world = WorldRegistry()
    counter = SmartObject(
        "counter", "Counter", (0.0, 0.0),
        [Affordance("Caffeine", 40.0)], slots=1, tags={"sells:coffee"},
    )
    counter.enable_service()
    world.add(counter)
    world.add(SmartObject("seat", "Chair", (5.0, 0.0), [], slots=2, tags={"seat"}))
    return world


_RECIPE = [
    Step(tag="sells:coffee", action="acquire", item="coffee"),
    Step(tag="seat", action="consume", item="coffee", amount=40.0),
]


def test_build_plan_tree_resolves_each_step_by_tag():
    tree = build_plan_tree(_two_object_world(), _RECIPE, "Caffeine")
    assert tree is not None
    assert tree.name == "plan:Caffeine"
    assert [child.name for child in tree.children] == ["acquire:coffee", "consume:coffee"]


def test_build_plan_tree_is_none_when_a_step_object_is_absent():
    world = WorldRegistry()  # has neither a counter nor a seat
    assert build_plan_tree(world, _RECIPE, "Caffeine") is None


# --- scene: order coffee, then sit and drink it ----------------------------
def test_guest_orders_coffee_then_drinks_it_seated():
    sim = build_project("micro.plan", n_agents=3, with_barista=True)
    carried_coffee: set[str] = set()
    min_caffeine: dict[str, float] = {}
    caffeine_while_holding: dict[str, float] = {}
    for _ in range(1000):
        sim.step()
        for a in sim.agents:
            if not a.id.startswith("q"):
                continue
            c = a.drives.needs["Caffeine"]
            min_caffeine[a.id] = min(min_caffeine.get(a.id, 1e9), c)
            if a.inventory.has("coffee"):
                carried_coffee.add(a.id)
                # While merely *holding* the coffee, Caffeine isn't satisfied yet.
                caffeine_while_holding[a.id] = min(caffeine_while_holding.get(a.id, 1e9), c)

    assert carried_coffee == {"q0", "q1", "q2"}, "each guest acquired a coffee"
    assert all(v >= 45.0 for v in caffeine_while_holding.values()), \
        "holding coffee does not itself satisfy Caffeine (drinking does)"
    assert all(v < 20.0 for v in min_caffeine.values()), "each guest drank it (satisfied)"
    assert [a.id for a in sim.agents] == ["barista"], "served guests left; staff stays"


def test_without_a_barista_the_plan_cannot_complete():
    sim = build_project("micro.plan", n_agents=3, with_barista=False)
    for _ in range(150):
        sim.step()
        for a in sim.agents:
            if a.id.startswith("q"):
                assert not a.inventory.has("coffee"), "no coffee without a barista"
                assert a.drives.needs["Caffeine"] >= 50.0, "Caffeine never satisfied"


def test_plan_scene_is_deterministic():
    def trace():
        sim = build_project("micro.plan", n_agents=3, with_barista=True)
        out = []
        for _ in range(200):
            sim.step()
            out.append(tuple(round(c, 4) for a in sim.agents for c in a.position))
        return out

    assert trace() == trace()
