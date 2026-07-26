"""Shared request and result contracts for simulation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RunStatus(str, Enum):
    """Stable lifecycle states used by runners, services, APIs, and reports."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ENDED_EARLY = "ended_early"
    DISCONNECTED = "disconnected"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


@dataclass(frozen=True)
class VariantSpec:
    """Optional, reproducible modifications applied to one source scene."""

    vehicle_type_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    signal_duration_scale: float = 1.0
    closed_lanes: tuple[str, ...] = ()
    closure_begin: float = 0.0
    closure_end: float = 3600.0


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
    steps: int = 36000
    flow_multiplier: float = 1.0
    seed: int = 42
    output_root: Path | None = None
    edge_delay_steps: int = 0
    edge_directions: tuple[str, ...] = ()
    variant: VariantSpec = field(default_factory=VariantSpec)


@dataclass(frozen=True)
class RunResult:
    """Serializable summary returned by RunService and the REST API."""

    run_id: str
    status: RunStatus
    reason: str
    run_dir: Path
    summary: dict[str, Any] | None = None
