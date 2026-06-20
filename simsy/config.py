"""Typed configuration for the engine's tunable subsystems.

`config.yaml` (at the project root) parameterizes *how* the engine behaves --
ORCA horizon, hysteresis, tick rate, population, etc. It deliberately does NOT
describe scene *content* (which smart objects exist, wall geometry): that is the
DSL/authoring layer's job (architecture doc 3E). Every field has a default, so
the engine runs identically whether or not the file is present.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field, fields

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a declared dependency
    yaml = None


@dataclass
class SimulationCfg:
    seed: int = 42
    tick_rate_hz: float = 10.0  # fixed-timestep ticks per second

    @property
    def dt(self) -> float:
        return 1.0 / self.tick_rate_hz


@dataclass
class WorldCfg:
    bounds: tuple[float, float, float, float] = (-26.0, -13.0, 26.0, 13.0)
    cell_size: float = 1.0


@dataclass
class AgentCfg:
    radius: float = 0.6
    speed: float = 4.0
    think_period_ticks: int = 5


@dataclass
class UtilityCfg:
    hysteresis: float = 1.2        # margin a new motive must beat the active one by
    idle_threshold: float = 0.02   # below this score an agent idles
    pressure_exponent: float = 2.0  # response curve: (drive/100) ** exponent


@dataclass
class LocomotionCfg:
    arrive_eps: float = 0.35
    waypoint_eps: float = 0.6
    group_cohesion: float = 0.6  # how strongly group members steer toward their centroid


@dataclass
class OrcaCfg:
    time_horizon: float = 2.0       # seconds of look-ahead for avoidance
    neighbor_distance: float = 10.0  # only consider neighbours within this range


@dataclass
class PopulationCfg:
    initial: int = 3                       # agents present at tick 0
    max: int = 8                           # population cap
    spawn_interval_ticks: tuple[int, int] = (15, 45)  # min/max ticks between arrivals
    need_spread: float = 12.0              # +/- jitter on initial drives


@dataclass
class ArchetypeCfg:
    needs: dict[str, float] = field(
        default_factory=lambda: {"Caffeine": 55.0, "Rest": 55.0, "Leave": 0.0}
    )
    growth: dict[str, float] = field(
        default_factory=lambda: {"Caffeine": 4.0, "Rest": 3.0, "Leave": 2.5}
    )


@dataclass
class ServerCfg:
    http_port: int = 8000
    ws_port: int = 8765
    snapshot_hz: float = 10.0  # broadcast rate; decoupled from the tick rate


@dataclass
class MoodCfg:
    queue_stress_per_sec: float = 15.0  # stress gained per second waiting in a queue
    relief_per_sec: float = 8.0         # stress shed per second when not waiting
    impatience: float = 0.05            # Leave drive added per (stress × second)


@dataclass
class Config:
    simulation: SimulationCfg = field(default_factory=SimulationCfg)
    world: WorldCfg = field(default_factory=WorldCfg)
    agent: AgentCfg = field(default_factory=AgentCfg)
    utility: UtilityCfg = field(default_factory=UtilityCfg)
    locomotion: LocomotionCfg = field(default_factory=LocomotionCfg)
    orca: OrcaCfg = field(default_factory=OrcaCfg)
    population: PopulationCfg = field(default_factory=PopulationCfg)
    archetype: ArchetypeCfg = field(default_factory=ArchetypeCfg)
    server: ServerCfg = field(default_factory=ServerCfg)
    mood: MoodCfg = field(default_factory=MoodCfg)


DEFAULT_PATH = pathlib.Path(__file__).resolve().parent.parent / "config.yaml"


def _section(cls, data: dict | None):
    """Build a sub-config from a YAML mapping, ignoring unknown keys."""
    if not data:
        return cls()
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def load_config(path: str | pathlib.Path | None = None) -> Config:
    """Load config.yaml, falling back to defaults for any missing file/section."""
    p = pathlib.Path(path) if path else DEFAULT_PATH
    if yaml is None or not p.exists():
        return Config()
    data = yaml.safe_load(p.read_text()) or {}
    return Config(
        simulation=_section(SimulationCfg, data.get("simulation")),
        world=_section(WorldCfg, data.get("world")),
        agent=_section(AgentCfg, data.get("agent")),
        utility=_section(UtilityCfg, data.get("utility")),
        locomotion=_section(LocomotionCfg, data.get("locomotion")),
        orca=_section(OrcaCfg, data.get("orca")),
        population=_section(PopulationCfg, data.get("population")),
        archetype=_section(ArchetypeCfg, data.get("archetype")),
        server=_section(ServerCfg, data.get("server")),
        mood=_section(MoodCfg, data.get("mood")),
    )
