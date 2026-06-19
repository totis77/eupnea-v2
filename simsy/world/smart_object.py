"""Smart Objects and their world-side capability components.

A Smart Object pushes interaction intelligence into the world: it *advertises*
how much it can satisfy a need (object-advertised utility) and manages a fixed
number of interaction slots via the Reserve -> Travel -> Occupy -> Release
lifecycle (architecture doc 2C).

In the entity-component model (§6D) a SmartObject is **not** a component — it is
an entity that holds world-side Capability components: `Affordance` (what it
satisfies) and `SlotSet` (how many can interact at once + the lifecycle). The
`SmartObject` class is the thin facade that bundles those onto an entity and
keeps the interaction API the BT leaves and utility scorer call.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..components import NavShape, RenderShape, Transform
from .entity import Entity


@dataclass
class Affordance:
    """A need this object can satisfy, and by how much (per full interaction)."""

    need: str
    amount: float  # e.g. an espresso machine: Affordance("Caffeine", 40)


class SlotSet:
    """Interaction-slot capability + the reservation lifecycle — the world-side
    mirror of an agent's claim on this object.

    Reserve (claim before pathfinding) -> Occupy (begin interacting, needs a
    prior reservation) -> Release (free, safe from OnAbort or on completion)."""

    def __init__(self, count: int) -> None:
        self.count = count
        # agent_id -> True while reserved (claim made before pathfinding).
        self._reserved: dict[str, bool] = {}
        # agent_ids currently occupying a slot.
        self._occupants: set[str] = set()

    @property
    def free(self) -> int:
        return self.count - len(self._reserved)

    def is_reserved_by(self, agent_id: str) -> bool:
        return agent_id in self._reserved

    def reserve(self, agent_id: str) -> bool:
        """Claim a slot before travelling. Idempotent for the same agent."""
        if agent_id in self._reserved:
            return True
        if self.free <= 0:
            return False
        self._reserved[agent_id] = True
        return True

    def occupy(self, agent_id: str) -> bool:
        """Begin interacting. Requires a prior reservation."""
        if agent_id not in self._reserved:
            return False
        self._occupants.add(agent_id)
        return True

    def release(self, agent_id: str) -> None:
        """Free the slot. Safe to call from OnAbort or on normal completion."""
        self._reserved.pop(agent_id, None)
        self._occupants.discard(agent_id)


class Queue:
    """A FIFO waiting line for a contended object (architecture doc §6D).

    Holds agent ids in arrival order and assigns each waiter an indexed standing
    spot trailing from an anchor, so the line is visible and orderly. The BT's
    Reserve leaf joins the queue when slots are full and advances the head into a
    freed slot. Deterministic: order is arrival order, and the engine ticks
    agents in sorted-id order, so joins/leaves replay identically."""

    def __init__(self, anchor: tuple[float, float], step: tuple[float, float]) -> None:
        self.anchor = anchor  # world position of the front (index 0) waiting spot
        self.step = step      # offset between consecutive spots (trails the line)
        self._line: list[str] = []

    def join(self, agent_id: str) -> int:
        """Add to the back if not already queued; return the agent's position."""
        if agent_id not in self._line:
            self._line.append(agent_id)
        return self._line.index(agent_id)

    def leave(self, agent_id: str) -> None:
        if agent_id in self._line:
            self._line.remove(agent_id)

    def head(self) -> str | None:
        return self._line[0] if self._line else None

    def index_of(self, agent_id: str) -> int | None:
        return self._line.index(agent_id) if agent_id in self._line else None

    def wait_slot(self, agent_id: str) -> tuple[float, float] | None:
        """World position of the standing spot for this agent's current index."""
        i = self.index_of(agent_id)
        if i is None:
            return None
        return (self.anchor[0] + self.step[0] * i, self.anchor[1] + self.step[1] * i)

    def __len__(self) -> int:
        return len(self._line)

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._line


class ServicePoint:
    """Marks an object as needing a *server* (staff) to fulfill interactions
    (architecture doc §6D). Holds an order ledger: a guest places an order, a
    server brews it (FIFO), marks it ready, and the guest collects it at the
    pickup spot. This decouples *ordering* (briefly at the register) from
    *receiving* (later, at pickup) — the register slot frees as soon as the
    order is in, so the line keeps moving while the server works the backlog."""

    def __init__(self, pickup: tuple[float, float]) -> None:
        self.pickup = pickup        # where guests wait to collect their order
        self._pending: list[str] = []   # ordered, awaiting a server (FIFO)
        self._in_progress: str | None = None  # the order being brewed now
        self._ready: set[str] = set()       # brewed, awaiting collection

    # --- guest side -------------------------------------------------------
    def place_order(self, guest_id: str) -> None:
        """Enqueue an order. Idempotent; ignores guests already in the system."""
        if (
            guest_id != self._in_progress
            and guest_id not in self._pending
            and guest_id not in self._ready
        ):
            self._pending.append(guest_id)

    def is_ready(self, guest_id: str) -> bool:
        return guest_id in self._ready

    def collect(self, guest_id: str) -> bool:
        """Take a ready order. True if there was one to collect."""
        if guest_id in self._ready:
            self._ready.discard(guest_id)
            return True
        return False

    def cancel(self, guest_id: str) -> None:
        """Drop a guest's order anywhere in the pipeline (OnAbort/despawn)."""
        if guest_id in self._pending:
            self._pending.remove(guest_id)
        if self._in_progress == guest_id:
            self._in_progress = None
        self._ready.discard(guest_id)

    # --- server side ------------------------------------------------------
    def next_order(self) -> str | None:
        """The next order a free server should start (FIFO head), or None."""
        return self._pending[0] if self._pending else None

    def begin(self, guest_id: str) -> None:
        """Server starts brewing this order."""
        if guest_id in self._pending:
            self._pending.remove(guest_id)
            self._in_progress = guest_id

    def mark_ready(self, guest_id: str) -> None:
        """Server finishes; the order moves to the pickup counter."""
        if self._in_progress == guest_id:
            self._in_progress = None
        self._ready.add(guest_id)


class SmartObject:
    def __init__(
        self,
        obj_id: str,
        kind: str,
        position: tuple[float, float],
        affordances: list[Affordance],
        slots: int = 1,
        interaction_ticks: int = 20,
        despawns: bool = False,
    ) -> None:
        self.entity = Entity(
            obj_id,
            Transform(position),
            NavShape(static=True),  # fixtures are static; footprint TBD
            RenderShape(shape="box"),
        )
        self.kind = kind
        # World-side Capability components.
        self.affordances = {a.need: a for a in affordances}
        self.slot_set = self.entity.add(SlotSet(slots))
        self.queue: Queue | None = None  # opt-in via enable_queue() for contended objects
        self.service_point: ServicePoint | None = None  # opt-in via enable_service() for staffed objects
        self.interaction_ticks = interaction_ticks
        self.despawns = despawns  # reaching this object removes the agent (an exit)

    def enable_queue(
        self,
        direction: tuple[float, float] = (-1.0, 0.0),
        spacing: float = 1.5,
        gap: float = 2.0,
    ) -> "Queue":
        """Attach a waiting line trailing from the object in `direction`.

        `gap` is the distance from the object to the front spot; `spacing` the
        distance between waiters. Agents whose Reserve finds the slots full join
        this line instead of failing."""
        dx, dy = direction
        mag = (dx * dx + dy * dy) ** 0.5 or 1.0
        ux, uy = dx / mag, dy / mag
        px, py = self.position
        anchor = (px + ux * gap, py + uy * gap)
        step = (ux * spacing, uy * spacing)
        self.queue = self.entity.add(Queue(anchor, step))
        return self.queue

    def enable_service(self, pickup_offset: tuple[float, float] = (0.0, -3.0)) -> "ServicePoint":
        """Require a server to fulfill interactions. `pickup_offset` is where
        guests wait to collect, relative to the object."""
        px, py = self.position
        pickup = (px + pickup_offset[0], py + pickup_offset[1])
        self.service_point = self.entity.add(ServicePoint(pickup))
        return self.service_point

    # --- pose accessors (single source of truth = the entity) -------------
    @property
    def id(self) -> str:
        return self.entity.id

    @property
    def position(self) -> tuple[float, float]:
        return self.entity.transform.position

    # --- advertising ------------------------------------------------------
    def advertises(self, need: str) -> bool:
        return need in self.affordances

    def advertised_amount(self, need: str) -> float:
        aff = self.affordances.get(need)
        return aff.amount if aff else 0.0

    # --- slots / lifecycle (delegated to the SlotSet component) -----------
    @property
    def slots(self) -> int:
        return self.slot_set.count

    @property
    def free_slots(self) -> int:
        return self.slot_set.free

    def is_reserved_by(self, agent_id: str) -> bool:
        return self.slot_set.is_reserved_by(agent_id)

    def reserve(self, agent_id: str) -> bool:
        return self.slot_set.reserve(agent_id)

    def occupy(self, agent_id: str) -> bool:
        return self.slot_set.occupy(agent_id)

    def release(self, agent_id: str) -> None:
        self.slot_set.release(agent_id)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"SmartObject({self.id!r}, {self.kind!r}, "
            f"free={self.free_slots}/{self.slots})"
        )
