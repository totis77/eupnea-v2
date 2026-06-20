"""World object lookup.

This is the slice-level stand-in for the two-tier lookup described in the
architecture doc (3C). For now it is a simple global registry indexed by the
affordance a need maps to. The local Uniform Hash Grid (for proximity and
crowd-density queries) is a TODO once locomotion/RVO lands; the public API
(`query`) is shaped so the hash-grid tier can slot in behind it without
changing callers.
"""

from __future__ import annotations

from .smart_object import SmartObject


class WorldRegistry:
    def __init__(self) -> None:
        self._objects: dict[str, SmartObject] = {}

    def add(self, obj: SmartObject) -> SmartObject:
        self._objects[obj.id] = obj
        return obj

    def get(self, obj_id: str) -> SmartObject | None:
        return self._objects[obj_id] if obj_id in self._objects else None

    def all(self) -> list[SmartObject]:
        # Sorted by id for deterministic iteration order.
        return [self._objects[k] for k in sorted(self._objects)]

    def by_tag(self, tag: str) -> list[SmartObject]:
        """All objects carrying `tag`, deterministically ordered by id. Used by
        multi-step plans to locate the object for each step."""
        return [obj for obj in self.all() if tag in obj.tags]

    def query(self, need: str, *, only_available: bool = True) -> list[SmartObject]:
        """All objects advertising `need`, deterministically ordered by id.

        TODO(hash-grid): accept an origin position + radius and resolve local
        contention through the Uniform Hash Grid tier.
        """
        results = [
            obj
            for obj in self.all()
            if obj.advertises(need) and (not only_available or obj.free_slots > 0)
        ]
        return results
