"""Shared request and result contracts for simulation runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

DISTURBANCE_KINDS = ("construction", "event_demand", "vehicle_failure")


class RunStatus(str, Enum):
    """Stable lifecycle states used by runners, services, APIs, and reports."""

    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ENDED_EARLY = "ended_early"
    DISCONNECTED = "disconnected"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclass(frozen=True)
class DisturbanceSpec:
    """Bounded temporary scene disturbance applied through the variant layer."""

    kind: str
    begin_seconds: float
    end_seconds: float
    target: str
    intensity: float

    def __post_init__(self) -> None:
        if self.kind not in DISTURBANCE_KINDS:
            raise ValueError(
                f"kind must be one of {DISTURBANCE_KINDS}, got {self.kind!r}"
            )
        try:
            begin = float(self.begin_seconds)
            end = float(self.end_seconds)
            intensity = float(self.intensity)
        except (TypeError, ValueError) as exc:
            raise ValueError("disturbance fields must be numeric") from exc
        if not end > begin:
            raise ValueError("end_seconds must be greater than begin_seconds")
        if self.kind == "event_demand":
            # Demand scaling is a multiplier on arrival rates, not a share.
            if not 0.0 < intensity <= 2.0:
                raise ValueError("intensity must be in (0, 2] for event_demand")
        elif not 0.0 < intensity <= 1.0:
            raise ValueError("intensity must be in (0, 1]")
        object.__setattr__(self, "begin_seconds", begin)
        object.__setattr__(self, "end_seconds", end)
        object.__setattr__(self, "intensity", intensity)


@dataclass(frozen=True)
class VariantSpec:
    """Optional, reproducible modifications applied to one source scene."""

    vehicle_type_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    signal_duration_scale: float = 1.0
    closed_lanes: tuple[str, ...] = ()
    closure_begin: float = 0.0
    closure_end: float = 3600.0
    disturbance: DisturbanceSpec | None = None


@dataclass(frozen=True)
class VariantBundle:
    """Generated SUMO additional files and their reproducibility manifest."""

    additional_files: tuple[Path, ...]
    manifest: dict[str, object]


@dataclass(frozen=True)
class RunRequest:
    """Complete input contract for one isolated simulation run."""

    intersection_id: str
    algorithm: str
    steps: int | None = 36000
    flow_multiplier: float = 1.0
    seed: int = 42
    output_root: Path | None = None
    edge_delay_steps: int = 0
    edge_directions: tuple[str, ...] = ()
    variant: VariantSpec = field(default_factory=VariantSpec)
    algorithm_params: dict[str, float] = field(default_factory=dict)
    duration_seconds: float = 3600.0
    warmup_seconds: float = 600.0
    disturbance: DisturbanceSpec | None = None

    def __post_init__(self) -> None:
        # The disturbance participates in the existing variant contract so
        # downstream variant generators see one uniform spec.
        if self.disturbance is not None and not isinstance(self.disturbance, DisturbanceSpec):
            raise ValueError("disturbance must be a DisturbanceSpec")
        object.__setattr__(
            self,
            "variant",
            replace(self.variant, disturbance=self.disturbance),
        )


@dataclass(frozen=True)
class RunResult:
    """Serializable summary returned by RunService and the REST API."""

    run_id: str
    status: RunStatus
    reason: str
    run_dir: Path
    summary: dict[str, Any] | None = None
    algorithm: str = ""


def disturbance_payload(spec: DisturbanceSpec | None) -> dict[str, Any] | None:
    """Serialize a DisturbanceSpec for manifests and matrices."""
    return asdict(spec) if spec is not None else None
