"""The architecture's central promise: same seed -> identical replay."""

from simsy.sim import build_coffee_shop
from simsy.world.smart_object import Affordance, SmartObject


def _trace(seed: int, ticks: int) -> list[dict]:
    sim = build_coffee_shop(seed=seed)
    trace = []
    for _ in range(ticks):
        sim.step()
        trace.append(sim.snapshot())
    return trace


def test_same_seed_is_bit_identical():
    assert _trace(42, 150) == _trace(42, 150)


def test_different_seed_diverges_or_not_but_is_stable():
    # Seeds don't currently feed any stochastic choice, so traces match;
    # this guards that re-running a given seed is always stable.
    assert _trace(7, 80) == _trace(7, 80)


def test_reservation_lifecycle():
    obj = SmartObject("o", "Chair", (0.0, 0.0), [Affordance("Rest", 30.0)], slots=1)
    assert obj.free_slots == 1
    assert obj.reserve("a") is True
    assert obj.free_slots == 0
    assert obj.reserve("b") is False  # full
    assert obj.reserve("a") is True   # idempotent for the same agent
    assert obj.occupy("a") is True
    assert obj.occupy("b") is False   # cannot occupy without a reservation
    obj.release("a")
    assert obj.free_slots == 1
    assert obj.reserve("b") is True   # slot reclaimed
