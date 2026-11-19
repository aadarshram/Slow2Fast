"""Step and EpisodeResult: the per-step record every System 2 run builds up (cmc/system2.py)."""

from dataclasses import dataclass, field


@dataclass
class Step:
    source: str
    action: tuple
    s2_reason: str | None = None


@dataclass
class EpisodeResult:
    steps: list = field(default_factory=list)
    goal_reached: bool = False
    s1_ok: int = 0
    s1_bad: int = 0
    s2_steps: int = 0
