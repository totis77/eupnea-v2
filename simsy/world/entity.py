"""The Entity: the universal "thing in the world" (architecture doc §6A).

Following the Unity/Unreal/Godot convention, props, fixtures, walls, and agents
are all one kind of thing — an entity with a pose (`Transform`), an engine-facing
nav proxy (`NavShape`), an optional viewer appearance (`RenderShape`), and a bag
of behavioural components (Capability/State + an optional Controller).

This is **lightweight composition, not a data-oriented ECS**: an entity holds its
components; engine *systems* fetch the component types they need via `get()`.
`Agent` and `SmartObject` are composed *from* an entity (they hold one), keeping
composition-over-inheritance — they are not Entity subclasses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from ..components import NavShape, RenderShape, Transform

C = TypeVar("C")


class Entity:
    def __init__(
        self,
        entity_id: str,
        transform: "Transform",
        navshape: "NavShape | None" = None,
        render: "RenderShape | None" = None,
    ) -> None:
        self.id = entity_id
        # Representation tier — named slots (systems read Transform/NavShape).
        self.transform = transform
        self.navshape = navshape
        self.render = render
        # Behavioural components (Capability/State + Controller), queryable by type.
        self._components: dict[type, object] = {}

    def add(self, component: C) -> C:
        """Attach a behavioural component, keyed by its type. Returns it so the
        owner can keep a direct reference: ``self.drives = entity.add(Drives(...))``."""
        self._components[type(component)] = component
        return component

    def get(self, ctype: type[C]) -> "C | None":
        return self._components.get(ctype)  # type: ignore[return-value]

    def has(self, ctype: type) -> bool:
        return ctype in self._components
