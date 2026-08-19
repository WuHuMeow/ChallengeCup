"""Pydantic adapters for the public REST API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from algorithms.registry import canonicalize_algorithm_key
from core.run_models import RunRequest, RunResult, RunStatus, VariantSpec
from core.types import (
    ControlAction,
    JointState,
    PhaseTrafficState,
    PredictionResult,
    QueueState,
    VehicleState,
)
from core.movements import MovementKey, MovementState, PhaseMovementState


class VariantSpecModel(BaseModel):
    vehicle_type_overrides: dict[str, dict[str, str]] = Field(default_factory=dict)
    signal_duration_scale: float = Field(default=1.0, gt=0)
    closed_lanes: list[str] = Field(default_factory=list)
    closure_begin: float = Field(default=0.0, ge=0)
    closure_end: float = Field(default=3600.0, ge=0)

    def to_domain(self) -> VariantSpec:
        return VariantSpec(
            vehicle_type_overrides=self.vehicle_type_overrides,
            signal_duration_scale=self.signal_duration_scale,
            closed_lanes=tuple(self.closed_lanes),
            closure_begin=self.closure_begin,
            closure_end=self.closure_end,
        )


class RunRequestModel(BaseModel):
    intersection_id: str = Field(pattern=r"^(?:[1-9]|1[0-9]|20)$")
    algorithm: Literal[
        "fixed_time",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
        "actuated",
    ]
    steps: int | None = Field(default=None, gt=0)
    flow_multiplier: float = Field(default=1.0, gt=0)
    seed: int = Field(default=42, ge=0)
    duration_seconds: float = Field(default=3600.0, gt=0)
    warmup_seconds: float = Field(default=600.0, ge=0)
    step_length_override: float | None = Field(default=None, gt=0)
    edge_delay_steps: int = Field(default=0, ge=0)
    edge_directions: list[str] = Field(default_factory=list)
    variant: VariantSpecModel = Field(default_factory=VariantSpecModel)
    algorithm_params: dict[str, float] = Field(default_factory=dict)

    def to_domain(self, output_root: Path | None = None) -> RunRequest:
        return RunRequest(
            intersection_id=self.intersection_id,
            algorithm=self.algorithm,
            steps=self.steps,
            flow_multiplier=self.flow_multiplier,
            seed=self.seed,
            duration_seconds=self.duration_seconds,
            warmup_seconds=self.warmup_seconds,
            step_length_override=self.step_length_override,
            output_root=output_root,
            edge_delay_steps=self.edge_delay_steps,
            edge_directions=tuple(self.edge_directions),
            variant=self.variant.to_domain(),
            algorithm_params=self.algorithm_params,
        )


class LegacyRunRequestModel(RunRequestModel):
    algorithm: str

    @field_validator("algorithm", mode="before")
    @classmethod
    def migrate_algorithm_alias(cls, value: object) -> str:
        try:
            return canonicalize_algorithm_key(str(value))
        except KeyError as exc:
            raise ValueError(str(exc)) from exc


class RunResultModel(BaseModel):
    run_id: str
    status: RunStatus
    reason: str
    run_dir: str
    summary: dict[str, Any] | None = None
    algorithm: str = ""

    @classmethod
    def from_domain(cls, result: RunResult) -> "RunResultModel":
        return cls(
            run_id=result.run_id,
            status=result.status,
            reason=result.reason,
            run_dir=str(result.run_dir),
            summary=result.summary,
            algorithm=result.algorithm,
        )


class QueueStateModel(BaseModel):
    direction: str
    queue_length: float = Field(ge=0)
    waiting_time: float = Field(ge=0)
    vehicle_count: int = Field(ge=0)
    capacity: float = Field(default=0.0, ge=0)

    def to_domain(self) -> QueueState:
        return QueueState(**self.model_dump())


class PhaseTrafficStateModel(BaseModel):
    phase_index: int = Field(ge=0)
    signal_state: str
    nominal_duration: float = Field(gt=0)
    incoming_lanes: list[str] = Field(default_factory=list)
    outgoing_lanes: list[str] = Field(default_factory=list)
    incoming_queue: float = Field(ge=0)
    incoming_capacity: float = Field(ge=0)
    outgoing_queue: float = Field(ge=0)
    outgoing_capacity: float = Field(ge=0)
    outgoing_occupancy: float = Field(ge=0, le=1)

    def to_domain(self) -> PhaseTrafficState:
        return PhaseTrafficState(
            phase_index=self.phase_index,
            signal_state=self.signal_state,
            nominal_duration=self.nominal_duration,
            incoming_lanes=tuple(self.incoming_lanes),
            outgoing_lanes=tuple(self.outgoing_lanes),
            incoming_queue=self.incoming_queue,
            incoming_capacity=self.incoming_capacity,
            outgoing_queue=self.outgoing_queue,
            outgoing_capacity=self.outgoing_capacity,
            outgoing_occupancy=self.outgoing_occupancy,
        )


class MovementStateModel(BaseModel):
    incoming_lane: str
    outgoing_lane: str
    queue_vehicles: float = Field(ge=0, allow_inf_nan=False)
    downstream_queue_vehicles: float = Field(ge=0, allow_inf_nan=False)
    incoming_capacity: float = Field(gt=0, allow_inf_nan=False)
    downstream_capacity: float = Field(gt=0, allow_inf_nan=False)
    downstream_occupancy: float = Field(ge=0, le=1, allow_inf_nan=False)
    saturation_rate: float = Field(ge=0, allow_inf_nan=False)
    turn_ratio: float = Field(ge=0, allow_inf_nan=False)

    def to_domain(self) -> MovementState:
        return MovementState(
            key=MovementKey(
                incoming_lane=self.incoming_lane,
                outgoing_lane=self.outgoing_lane,
            ),
            queue_vehicles=self.queue_vehicles,
            downstream_queue_vehicles=self.downstream_queue_vehicles,
            incoming_capacity=self.incoming_capacity,
            downstream_capacity=self.downstream_capacity,
            downstream_occupancy=self.downstream_occupancy,
            saturation_rate=self.saturation_rate,
            turn_ratio=self.turn_ratio,
        )


class PhaseMovementStateModel(BaseModel):
    phase_index: int = Field(ge=0, strict=True)
    signal_state: str
    movements: list[MovementStateModel] = Field(default_factory=list)
    nominal_duration: float = Field(gt=0, allow_inf_nan=False)

    def to_domain(self) -> PhaseMovementState:
        return PhaseMovementState(
            phase_index=self.phase_index,
            signal_state=self.signal_state,
            movements=tuple(movement.to_domain() for movement in self.movements),
            nominal_duration=self.nominal_duration,
        )


class VehicleStateModel(BaseModel):
    vehicle_id: str
    lane_id: str
    speed: float

    def to_domain(self) -> VehicleState:
        return VehicleState(**self.model_dump())


class JointStateModel(BaseModel):
    step: int = Field(ge=0)
    timestamp: float = Field(ge=0)
    tls_id: str
    current_phase: int = Field(ge=0)
    current_phase_name: str
    elapsed_phase_time: float = Field(ge=0)
    queues: list[QueueStateModel] = Field(default_factory=list)
    flows: dict[str, float] = Field(default_factory=dict)
    detector_values: dict[str, float] = Field(default_factory=dict)
    vehicles: list[VehicleStateModel] = Field(default_factory=list)
    arrival_history: list[int] = Field(default_factory=list)
    phase_states: list[PhaseTrafficStateModel] = Field(default_factory=list)
    phase_movements: list[PhaseMovementStateModel] = Field(default_factory=list)

    def to_domain(self) -> JointState:
        return JointState(
            step=self.step,
            timestamp=self.timestamp,
            tls_id=self.tls_id,
            current_phase=self.current_phase,
            current_phase_name=self.current_phase_name,
            elapsed_phase_time=self.elapsed_phase_time,
            queues=[queue.to_domain() for queue in self.queues],
            flows=self.flows,
            detector_values=self.detector_values,
            vehicles=[vehicle.to_domain() for vehicle in self.vehicles],
            arrival_history=self.arrival_history,
            phase_states=[phase.to_domain() for phase in self.phase_states],
            phase_movements=tuple(phase.to_domain() for phase in self.phase_movements),
        )


class StateRequestModel(BaseModel):
    state: JointStateModel


class PredictionResultModel(BaseModel):
    horizon_steps: int
    horizon_seconds: float
    predicted_flows: dict[str, float]

    @classmethod
    def from_domain(cls, result: PredictionResult) -> "PredictionResultModel":
        return cls(
            horizon_steps=result.horizon_steps,
            horizon_seconds=result.horizon_seconds,
            predicted_flows=result.predicted_flows,
        )


class ControlActionModel(BaseModel):
    tls_id: str
    action_type: str
    value: Any
    reason: str = ""

    @classmethod
    def from_domain(cls, action: ControlAction) -> "ControlActionModel":
        return cls(
            tls_id=action.tls_id,
            action_type=action.action_type,
            value=action.value,
            reason=action.reason,
        )


class ControlActionsModel(BaseModel):
    actions: list[ControlActionModel]
