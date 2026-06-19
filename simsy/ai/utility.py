"""Object-advertised utility scoring (the "what to do").

The agent does not hardcode where to go. It evaluates its internal drives
against every affordance advertised in the world and picks the highest-scoring
(need, object) pair. Motive-level hysteresis is applied by the caller
(Agent.think), not here -- this module is a pure scorer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..world.registry import WorldRegistry
    from ..world.smart_object import SmartObject

@dataclass
class Candidate:
    need: str
    obj: "SmartObject"
    score: float


def pressure(value: float, exponent: float = 2.0) -> float:
    """Map a 0..100 drive level to 0..1 pressure via a response curve."""
    v = max(0.0, min(100.0, value)) / 100.0
    return v ** exponent


def score(need_value: float, advertised_amount: float, exponent: float = 2.0) -> float:
    return pressure(need_value, exponent) * (advertised_amount / 100.0)


def best_candidate(
    agent: "Agent", world: "WorldRegistry", exponent: float = 2.0
) -> Candidate | None:
    """Highest-scoring (need, object) pair across all of the agent's drives.

    Deterministic: needs are evaluated in sorted order and `world.query`
    returns objects ordered by id, so ties resolve identically every run.
    """
    best: Candidate | None = None
    needs = agent.drives.needs
    for need in sorted(needs):
        for obj in world.query(need, only_available=False):
            # A full object is only a candidate if you can wait for it (has a
            # queue); otherwise it is unusable, exactly as only_available=True.
            if obj.free_slots <= 0 and obj.queue is None:
                continue
            s = score(needs[need], obj.advertised_amount(need), exponent)
            if best is None or s > best.score:
                best = Candidate(need=need, obj=obj, score=s)
    return best
