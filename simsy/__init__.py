"""simsy: headless deterministic multi-character simulation engine.

See docs/architecture.md for the full blueprint. This package currently
implements the deterministic spine (the vertical slice): a fixed-timestep
tick loop, seeded RNG, event bus, object-advertised utility with
motive-level hysteresis, and the smart-object reservation lifecycle.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
