"""Entity components (architecture doc §6D), grouped by tier.

- **Representation** (`representation.py`): pose + shapes — `Transform`/`NavShape`
  read by engine systems, `RenderShape` viewer-only.
- **Capability / State** (`state.py`): what an entity *has and knows* — data read
  by both engine systems and the entity's controller.

The Controller tier (the brain) lives in `simsy/ai/controller.py`.
"""

from .representation import NavShape, RenderShape, Transform
from .state import Blackboard, Drives, Locomotor

__all__ = [
    "Transform",
    "NavShape",
    "RenderShape",
    "Blackboard",
    "Drives",
    "Locomotor",
]
