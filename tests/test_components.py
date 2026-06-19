"""Components are testable in isolation — no Agent, no Simulation, no world.

This is the first concrete payoff of the entity-component refactor (architecture
doc §6): each capability can be exercised standalone, which is what makes
features composable and independently verifiable.
"""

from simsy.components import Drives, Locomotor
from simsy.world.smart_object import SlotSet


# --- SlotSet: the reservation lifecycle, with no SmartObject around --------
def test_slotset_reserve_occupy_release():
    slots = SlotSet(count=1)
    assert slots.free == 1
    assert slots.reserve("a") is True
    assert slots.free == 0
    assert slots.reserve("b") is False        # full
    assert slots.reserve("a") is True         # idempotent for the same agent
    assert slots.occupy("a") is True
    assert slots.occupy("b") is False         # cannot occupy without a reservation
    slots.release("a")
    assert slots.free == 1
    assert slots.reserve("b") is True         # slot reclaimed


def test_slotset_tracks_multiple_slots():
    slots = SlotSet(count=2)
    assert slots.reserve("a") and slots.reserve("b")
    assert slots.free == 0
    assert slots.reserve("c") is False
    assert slots.is_reserved_by("a") and not slots.is_reserved_by("c")


# --- Drives: need growth, clamped, driven by an explicit dt ----------------
def test_drives_grow_by_rate_times_dt():
    d = Drives(needs={"Caffeine": 50.0}, growth={"Caffeine": 4.0})
    d.update(0.5)                              # +4 * 0.5 = +2
    assert d.needs["Caffeine"] == 52.0


def test_drives_clamp_at_100():
    d = Drives(needs={"Rest": 99.0}, growth={"Rest": 10.0})
    d.update(1.0)
    assert d.needs["Rest"] == 100.0            # clamped, not 109


# --- Locomotor: goal/path intent, no movement integration -----------------
def test_locomotor_set_goal_invalidates_path_only_on_change():
    lo = Locomotor(speed=4.0)
    lo.set_goal((5.0, 0.0))
    lo.path = [(1.0, 0.0), (5.0, 0.0)]         # pretend a path was planned
    lo.path_idx = 1
    lo.set_goal((5.0, 0.0))                     # same goal -> keep the plan
    assert lo.path is not None and lo.path_idx == 1
    lo.set_goal((9.0, 0.0))                     # new goal -> drop the plan
    assert lo.path is None and lo.path_idx == 0 and lo.at_goal is False


def test_locomotor_clear_goal_resets_state():
    lo = Locomotor(speed=4.0)
    lo.set_goal((5.0, 0.0))
    lo.vel = (4.0, 0.0)
    lo.at_goal = True
    lo.clear_goal()
    assert lo.goal is None and lo.path is None and lo.vel == (0.0, 0.0)
    assert lo.at_goal is False
