"""Deterministic event bus.

Events are *queued* during a tick and drained at a well-defined point in the
tick order (see Simulation.step). Draining in insertion order keeps replay
deterministic: handlers never fire mid-mutation in nondeterministic order.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class Event:
    """An asynchronous world fact, e.g. a boarding call or a broken machine."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    tick: int = -1  # stamped by the bus when emitted


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[Event], None]]] = {}
        self._queue: deque[Event] = deque()

    def subscribe(self, event_type: str, handler: Callable[[Event], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def emit(self, event: Event, *, tick: int) -> None:
        """Enqueue an event; it is delivered when the bus is drained this tick."""
        self._queue.append(Event(type=event.type, payload=event.payload, tick=tick))

    def drain(self) -> list[Event]:
        """Deliver all queued events in insertion order. Returns what fired."""
        fired: list[Event] = []
        while self._queue:
            event = self._queue.popleft()
            fired.append(event)
            for handler in self._subscribers.get(event.type, ()):
                handler(event)
        return fired
