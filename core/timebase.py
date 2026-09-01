"""Seconds-first simulation window and step conversion contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import math


def _finite_positive(name: str, value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"{name} must be finite and > 0")
    return numeric


def _finite_non_negative(name: str, value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return numeric


@dataclass(frozen=True)
class SimulationWindow:
    """Requested simulation and warmup windows, both expressed in seconds."""

    duration_seconds: float
    warmup_seconds: float
    explicit_steps: int | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        duration = _finite_positive("duration_seconds", self.duration_seconds)
        warmup = _finite_non_negative("warmup_seconds", self.warmup_seconds)
        if warmup >= duration:
            raise ValueError("warmup_seconds must be less than duration_seconds")
        explicit_steps = self.explicit_steps
        if explicit_steps is not None and (
            isinstance(explicit_steps, bool)
            or not isinstance(explicit_steps, int)
            or explicit_steps <= 0
        ):
            raise ValueError("explicit_steps must be an integer > 0")
        object.__setattr__(self, "duration_seconds", duration)
        object.__setattr__(self, "warmup_seconds", warmup)


def steps_for_seconds(duration_seconds: float, step_length: float) -> int:
    """Return the smallest whole-step count covering ``duration_seconds``."""

    duration = _finite_non_negative("duration_seconds", duration_seconds)
    length = _finite_positive("step_length", step_length)
    return math.ceil(duration / length)


def seconds_for_steps(steps: int, step_length: float) -> float:
    """Return the simulated seconds represented by a whole-step count."""

    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
        raise ValueError("steps must be an integer >= 0")
    return steps * _finite_positive("step_length", step_length)
