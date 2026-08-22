"""Shared request and result contracts for simulation runs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Any, Literal

from algorithms.registry import canonicalize_algorithm_key, get_algorithm_registry
from core.timebase import SimulationWindow, steps_for_seconds

SUPPORTED_ALGORITHMS = frozenset(
    spec.key for spec in get_algorithm_registry().list()
)
CA_MP_PARAMETER_NAMES = frozenset({
    "overflow_occupancy_threshold",
    "prediction_weight",
    "base_green",
})


def _finite_number(name: str, value: object, *, minimum: float | None = None) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric: {value!r}") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite: {value!r}")
    if minimum is not None and numeric < minimum:
        raise ValueError(f"{name} must be >= {minimum}: {value!r}")
    return numeric


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


class RunStatus(str, Enum):
    """Stable lifecycle states used by runners, services, APIs, and reports."""

    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    # Read compatibility for evidence created before interrupted became canonical.
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
    disturbance: DisturbanceSpec | None = None

    def __post_init__(self) -> None:
        scale = _finite_number("signal_duration_scale", self.signal_duration_scale, minimum=0.0)
        if scale <= 0:
            raise ValueError("signal_duration_scale must be > 0")
        begin = _finite_number("closure_begin", self.closure_begin, minimum=0.0)
        end = _finite_number("closure_end", self.closure_end, minimum=0.0)
        if self.closed_lanes and end <= begin:
            raise ValueError("closure_end must be greater than closure_begin")
        if self.disturbance is not None and not isinstance(self.disturbance, DisturbanceSpec):
            raise ValueError("disturbance must be a DisturbanceSpec")
        object.__setattr__(self, "closed_lanes", tuple(self.closed_lanes))


@dataclass(frozen=True)
class DisturbanceSpec:
    """A bounded, auditable temporary disturbance in simulation seconds."""

    kind: Literal["construction", "event_demand", "vehicle_failure"]
    begin_seconds: float
    end_seconds: float
    target: str
    intensity: float

    def __post_init__(self) -> None:
        if self.kind not in {"construction", "event_demand", "vehicle_failure"}:
            raise ValueError(f"unsupported disturbance kind: {self.kind}")
        begin = _finite_number("begin_seconds", self.begin_seconds, minimum=0.0)
        end = _finite_number("end_seconds", self.end_seconds, minimum=0.0)
        intensity = _finite_number("intensity", self.intensity, minimum=0.0)
        if end <= begin:
            raise ValueError("end_seconds must be greater than begin_seconds")
        if intensity <= 0:
            raise ValueError("intensity must be > 0")
        if self.kind in {"construction", "vehicle_failure"} and intensity > 1:
            raise ValueError(
                "intensity must be <= 1 for construction and vehicle_failure"
            )
        if not isinstance(self.target, str) or not self.target.strip():
            raise ValueError("target must be a non-empty string")
        object.__setattr__(self, "begin_seconds", begin)
        object.__setattr__(self, "end_seconds", end)
        object.__setattr__(self, "intensity", intensity)
        object.__setattr__(self, "target", self.target.strip())


@dataclass(frozen=True)
class VariantBundle:
    """Generated SUMO additional files and their reproducibility manifest."""

    additional_files: tuple[Path, ...]
    manifest: dict[str, object]
    flow_file: Path | None = None
    route_file: Path | None = None
    sumo_cfg: Path | None = None
    network_file: Path | None = None


class _CompatibilitySteps(int):
    """Derived legacy step count whose formal window remains authoritative."""


def _disturbance_from_payload(value: object) -> DisturbanceSpec | None:
    if value is None or isinstance(value, DisturbanceSpec):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("disturbance must be a mapping or null")
    return DisturbanceSpec(**dict(value))


@dataclass(frozen=True)
class RunRequest:
    """Complete input contract for one isolated simulation run."""

    intersection_id: str
    algorithm: str
    # Explicit steps are retained for smoke tests and legacy CLI callers. Formal
    # requests use duration_seconds and resolve steps after loading the scene.
    steps: int | None = None
    flow_multiplier: float = 1.0
    seed: int = 42
    duration_seconds: float = 3600.0
    # ``None`` selects the compatibility default: seconds-first requests use
    # the formal 600-second warmup, while explicit-step requests use no
    # warmup unless the caller provides one explicitly.
    warmup_seconds: float | None = None
    step_length_override: float | None = None
    output_root: Path | None = None
    edge_delay_steps: int = 0
    edge_directions: tuple[str, ...] = ()
    variant: VariantSpec = field(default_factory=VariantSpec)
    disturbance: DisturbanceSpec | None = None
    algorithm_params: dict[str, float] = field(default_factory=dict)
    steps_origin: Literal["none", "compatibility", "explicit"] = field(
        init=False
    )

    def __post_init__(self) -> None:
        if isinstance(self.intersection_id, bool):
            raise ValueError("intersection_id must be an integer in 1..20")
        try:
            intersection = int(self.intersection_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("intersection_id must be an integer in 1..20") from exc
        if str(intersection) != str(self.intersection_id).strip() and not isinstance(
            self.intersection_id, int
        ):
            raise ValueError("intersection_id must be an integer in 1..20")
        if not 1 <= intersection <= 20:
            raise ValueError("intersection_id must be in 1..20")
        if self.algorithm not in SUPPORTED_ALGORITHMS:
            raise ValueError(f"unknown algorithm: {self.algorithm}")
        algorithm = self.algorithm
        if self.steps is not None and (
            isinstance(self.steps, bool)
            or not isinstance(self.steps, int)
            or self.steps <= 0
        ):
            raise ValueError("steps must be > 0 when explicitly supplied")
        warmup_seconds = (
            0.0
            if self.warmup_seconds is None and self.steps is not None
            else 600.0
            if self.warmup_seconds is None
            else self.warmup_seconds
        )
        window = SimulationWindow(self.duration_seconds, warmup_seconds)
        step_length = self.step_length_override
        if step_length is not None:
            try:
                numeric_step_length = float(step_length)
            except (TypeError, ValueError) as exc:
                raise ValueError("step_length_override must be numeric") from exc
            if not math.isfinite(numeric_step_length) or numeric_step_length <= 0:
                raise ValueError("step_length_override must be finite and > 0")
            object.__setattr__(self, "step_length_override", numeric_step_length)
            if self.steps is None or isinstance(self.steps, _CompatibilitySteps):
                object.__setattr__(
                    self,
                    "steps",
                    _CompatibilitySteps(
                        steps_for_seconds(window.duration_seconds, numeric_step_length)
                    ),
                )
        elif isinstance(self.steps, _CompatibilitySteps):
            object.__setattr__(self, "steps", None)
        steps_origin = (
            "none"
            if self.steps is None
            else "compatibility"
            if isinstance(self.steps, _CompatibilitySteps)
            else "explicit"
        )
        object.__setattr__(self, "steps_origin", steps_origin)
        object.__setattr__(self, "duration_seconds", window.duration_seconds)
        object.__setattr__(self, "warmup_seconds", window.warmup_seconds)
        flow_multiplier = _finite_number(
            "flow_multiplier",
            self.flow_multiplier,
            minimum=0.0,
        )
        if flow_multiplier <= 0:
            raise ValueError("flow_multiplier must be > 0")
        seed = _non_negative_int("seed", self.seed)
        edge_delay_steps = _non_negative_int("edge_delay_steps", self.edge_delay_steps)
        if self.algorithm_params and algorithm != "capacity_aware_maxpressure":
            raise ValueError(
                "algorithm_params are supported only for capacity_aware_maxpressure"
            )
        unknown_params = set(self.algorithm_params) - CA_MP_PARAMETER_NAMES
        if unknown_params:
            raise ValueError(f"unknown CA-MP parameters: {sorted(unknown_params)}")
        parameters = {
            name: _finite_number(f"algorithm_params[{name!r}]", value)
            for name, value in self.algorithm_params.items()
        }
        object.__setattr__(self, "intersection_id", str(intersection))
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "flow_multiplier", flow_multiplier)
        object.__setattr__(self, "seed", seed)
        object.__setattr__(self, "edge_delay_steps", edge_delay_steps)
        object.__setattr__(self, "edge_directions", tuple(self.edge_directions))
        if self.disturbance is not None and not isinstance(self.disturbance, DisturbanceSpec):
            raise ValueError("disturbance must be a DisturbanceSpec")
        if self.disturbance is not None and self.variant.disturbance is None:
            object.__setattr__(
                self,
                "variant",
                VariantSpec(
                    vehicle_type_overrides=self.variant.vehicle_type_overrides,
                    signal_duration_scale=self.variant.signal_duration_scale,
                    closed_lanes=self.variant.closed_lanes,
                    closure_begin=self.variant.closure_begin,
                    closure_end=self.variant.closure_end,
                    disturbance=self.disturbance,
                ),
            )
        object.__setattr__(self, "algorithm_params", parameters)
        if self.output_root is not None:
            object.__setattr__(self, "output_root", Path(self.output_root))

    @property
    def _steps_explicit(self) -> bool:
        return self.steps_origin == "explicit"

    def to_payload(self) -> dict[str, object]:
        """Return a complete JSON-safe request payload with step provenance."""
        payload = asdict(self)
        payload["schema_version"] = 1
        payload["steps"] = int(self.steps) if self.steps is not None else None
        payload["output_root"] = (
            str(self.output_root) if self.output_root is not None else None
        )
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "RunRequest":
        """Rebuild a request while validating persisted step provenance."""
        if not isinstance(payload, Mapping):
            raise ValueError("RunRequest payload must be a mapping")
        values = dict(payload)
        missing = object()
        schema_version = values.pop("schema_version", missing)
        if schema_version is not missing and (
            type(schema_version) is not int or schema_version != 1
        ):
            raise ValueError(f"unknown schema_version: {schema_version!r}")
        origin = values.pop("steps_origin", missing)
        if schema_version is not missing and origin is missing:
            raise ValueError("schema_version 1 requires steps_origin")
        steps = values.get("steps")
        if origin is missing:
            if steps is not None:
                origin = "explicit"
            elif values.get("step_length_override") is not None:
                origin = "compatibility"
                steps = steps_for_seconds(
                    values.get("duration_seconds", 3600.0),
                    values["step_length_override"],
                )
                values["steps"] = _CompatibilitySteps(steps)
            else:
                origin = "none"
        if origin not in {"none", "compatibility", "explicit"}:
            raise ValueError(f"unknown steps_origin: {origin!r}")
        if origin == "none" and steps is not None:
            raise ValueError("steps_origin 'none' requires steps=None")
        if origin == "none" and values.get("step_length_override") is not None:
            raise ValueError(
                "steps_origin 'none' is inconsistent with step_length_override"
            )
        if origin == "explicit" and steps is None:
            raise ValueError("steps_origin 'explicit' requires steps")
        if origin == "compatibility":
            override = values.get("step_length_override")
            if override is None:
                raise ValueError(
                    "steps_origin 'compatibility' requires step_length_override"
                )
            if isinstance(steps, bool) or not isinstance(steps, int):
                raise ValueError(
                    "steps_origin 'compatibility' requires integer steps"
                )
            try:
                expected_steps = steps_for_seconds(
                    values.get("duration_seconds", 3600.0),
                    override,
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "steps_origin 'compatibility' requires valid duration and override"
                ) from exc
            if steps != expected_steps:
                raise ValueError(
                    "steps_origin 'compatibility' does not match duration and override"
                )
            values["steps"] = _CompatibilitySteps(steps)

        disturbance = _disturbance_from_payload(values.get("disturbance"))
        values["disturbance"] = disturbance
        variant = values.get("variant")
        if isinstance(variant, Mapping):
            variant_values = dict(variant)
            variant_values["disturbance"] = _disturbance_from_payload(
                variant_values.get("disturbance")
            )
            values["variant"] = VariantSpec(**variant_values)
        elif variant is not None and not isinstance(variant, VariantSpec):
            raise ValueError("variant must be a mapping or VariantSpec")
        if "edge_directions" in values:
            values["edge_directions"] = tuple(values["edge_directions"])
        return cls(**values)


@dataclass(frozen=True)
class RunResult:
    """Serializable summary returned by RunService and the REST API."""

    run_id: str
    status: RunStatus
    reason: str
    run_dir: Path
    summary: dict[str, Any] | None = None
    algorithm: str = ""

    def __post_init__(self) -> None:
        if self.algorithm:
            object.__setattr__(
                self,
                "algorithm",
                canonicalize_algorithm_key(self.algorithm),
            )
