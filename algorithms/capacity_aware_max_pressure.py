"""Layered, movement-level capacity-aware MaxPressure ablations."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from math import isfinite
from typing import Iterable

from algorithms.ca_max_pressure import (
    CAMaxPressureAlgorithm,
    LegacyDecisionPlan,
    _LegacyPlanningProfile,
)
from cloud.cloud_policy import CloudPolicy, CloudPolicyPlan, joint_state_fingerprint
from core.movements import MovementState, PhaseMovementState
from core.types import ActionResult, ControlAction, JointState, PhaseTrafficState
from scenes.capacity_preflight import validate_capacity_aware_scene

logger = logging.getLogger(__name__)


def _finite_float(name: str, value: object) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _positive_float(name: str, value: object) -> float:
    numeric = _finite_float(name, value)
    if numeric <= 0:
        raise ValueError(f"{name} must be > 0")
    return numeric


def _nonnegative_float(name: str, value: object) -> float:
    numeric = _finite_float(name, value)
    if numeric < 0:
        raise ValueError(f"{name} must be >= 0")
    return numeric


@dataclass(frozen=True)
class CapacityAwareConfig:
    capacity_normalization: bool
    spillback_gate: bool
    prediction: bool
    min_green: float
    max_green: float
    overflow_threshold: float
    layer: str = "custom"
    safety_boundary: str = "none"

    def __post_init__(self) -> None:
        min_green = _positive_float("min_green", self.min_green)
        max_green = _positive_float("max_green", self.max_green)
        threshold = _finite_float("overflow_threshold", self.overflow_threshold)
        if min_green > max_green:
            raise ValueError("min_green must be <= max_green")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("overflow_threshold must be in [0, 1]")
        object.__setattr__(self, "min_green", min_green)
        object.__setattr__(self, "max_green", max_green)
        object.__setattr__(self, "overflow_threshold", threshold)

    @classmethod
    def m0(cls) -> "CapacityAwareConfig":
        return cls(False, False, False, 10.0, 30.0, 0.9, "M0", "none")

    @classmethod
    def m1(cls) -> "CapacityAwareConfig":
        return cls(True, False, False, 10.0, 30.0, 0.9, "M1", "none")

    @classmethod
    def m2(cls) -> "CapacityAwareConfig":
        return cls(True, True, False, 10.0, 30.0, 0.9, "M2", "spillback_gate")

    @classmethod
    def m3(cls) -> "CapacityAwareConfig":
        return cls(True, True, False, 10.0, 30.0, 0.9, "M3", "shared_action_validation")

    @classmethod
    def m4(cls) -> "CapacityAwareConfig":
        return cls(True, True, True, 10.0, 30.0, 0.9, "M4", "shared_action_validation")

    @classmethod
    def default(cls) -> "CapacityAwareConfig":
        return cls.m3()


@dataclass(frozen=True)
class PhaseScore:
    score: float
    movement_ids: tuple[str, ...]
    blocked_movements: tuple[str, ...]


@dataclass(frozen=True)
class _MovementPressure:
    movement_id: str
    incoming_lane: str
    outgoing_lane: str
    queue_vehicles: float
    downstream_queue_vehicles: float
    incoming_capacity: float
    downstream_capacity: float
    downstream_occupancy: float
    saturation_rate: float
    raw_pressure: float
    normalized_pressure: float
    prediction_pressure: float
    pressure: float
    blocked_reason: str | None


@dataclass(frozen=True)
class _PlannedAction:
    tls_id: str
    action_type: str
    value: int | float
    reason: str

    def control_action(self) -> ControlAction:
        return ControlAction(self.tls_id, self.action_type, self.value, self.reason)


@dataclass(frozen=True)
class _DecisionSnapshot:
    owner_token: object
    reset_epoch: int
    base_revision: int
    state_fingerprint: tuple[object, ...]
    state_step: int
    state_timestamp: float
    profile_fingerprint: tuple[object, ...]
    phase_scores: tuple[tuple[int, PhaseScore], ...]
    movement_pressures: tuple[tuple[int, tuple[_MovementPressure, ...]], ...]
    current_phase: int
    elapsed_phase_time: float
    legal_targets: tuple[int, ...]
    candidate_phases: tuple[int, ...]
    selected_phase: int | None
    selection_reason: str
    decision_reason: str
    actions: tuple[_PlannedAction, ...]
    legacy_plan: LegacyDecisionPlan | None = None
    cloud_plan: CloudPolicyPlan | None = None

    def scores(self) -> dict[int, PhaseScore]:
        return dict(self.phase_scores)

    def pressures(self) -> dict[int, tuple[_MovementPressure, ...]]:
        return dict(self.movement_pressures)


def _movement_id(movement: MovementState) -> str:
    return f"{movement.key.incoming_lane}->{movement.key.outgoing_lane}"


def _movement_pressure(
    movement: MovementState,
    config: CapacityAwareConfig,
    predicted_arrivals: dict[str, float] | None,
    prediction_weight: float,
) -> _MovementPressure:
    movement_id = _movement_id(movement)
    raw_pressure = movement.saturation_rate * (
        movement.queue_vehicles - movement.downstream_queue_vehicles
    )
    normalized_pressure = movement.saturation_rate * (
        movement.queue_vehicles / movement.incoming_capacity
        - movement.downstream_queue_vehicles / movement.downstream_capacity
    )
    arrivals = (
        0.0
        if predicted_arrivals is None
        else predicted_arrivals.get(movement.key.incoming_lane, 0.0)
    )
    prediction_pressure = (
        movement.saturation_rate
        * prediction_weight
        * arrivals
        / movement.incoming_capacity
        if config.prediction
        else 0.0
    )
    blocked_reason = (
        "downstream_occupancy_at_or_above_threshold"
        if config.spillback_gate
        and movement.downstream_occupancy >= config.overflow_threshold
        else None
    )
    base_pressure = normalized_pressure if config.capacity_normalization else raw_pressure
    return _MovementPressure(
        movement_id=movement_id,
        incoming_lane=movement.key.incoming_lane,
        outgoing_lane=movement.key.outgoing_lane,
        queue_vehicles=movement.queue_vehicles,
        downstream_queue_vehicles=movement.downstream_queue_vehicles,
        incoming_capacity=movement.incoming_capacity,
        downstream_capacity=movement.downstream_capacity,
        downstream_occupancy=movement.downstream_occupancy,
        saturation_rate=movement.saturation_rate,
        raw_pressure=raw_pressure,
        normalized_pressure=normalized_pressure,
        prediction_pressure=prediction_pressure,
        pressure=0.0 if blocked_reason else base_pressure + prediction_pressure,
        blocked_reason=blocked_reason,
    )


def _score_phase(
    state: PhaseMovementState,
    config: CapacityAwareConfig,
    predicted_arrivals: dict[str, float] | None = None,
    prediction_weight: float = 0.0,
) -> tuple[PhaseScore, tuple[_MovementPressure, ...]]:
    pressures = tuple(
        _movement_pressure(movement, config, predicted_arrivals, prediction_weight)
        for movement in state.movements
    )
    selected = tuple(
        pressure.movement_id
        for pressure in pressures
        if pressure.blocked_reason is None
    )
    blocked = tuple(
        pressure.movement_id
        for pressure in pressures
        if pressure.blocked_reason is not None
    )
    return PhaseScore(
        float(sum(pressure.pressure for pressure in pressures)), selected, blocked
    ), pressures


def phase_score(
    state: PhaseMovementState,
    config: CapacityAwareConfig,
    predicted_arrivals: dict[str, float] | None = None,
    prediction_weight: float = 0.0,
) -> PhaseScore:
    """Score one phase from raw or capacity-normalized movement pressure."""
    return _score_phase(state, config, predicted_arrivals, prediction_weight)[0]


class CapacityAwareMaxPressureAlgorithm(CAMaxPressureAlgorithm):
    """M0-M4 controller using the immutable movement state contract."""

    def __init__(
        self,
        config: CapacityAwareConfig | None = None,
        cloud_policy: CloudPolicy | None = None,
        overflow_occupancy_threshold: float | None = None,
        prediction_weight: float | None = None,
        base_green: float | None = None,
    ) -> None:
        if overflow_occupancy_threshold is not None:
            threshold = _finite_float(
                "overflow_occupancy_threshold", overflow_occupancy_threshold
            )
            if not 0.0 <= threshold <= 1.0:
                raise ValueError("overflow_occupancy_threshold must be in [0, 1]")
        if prediction_weight is not None:
            _nonnegative_float("prediction_weight", prediction_weight)
        if base_green is not None:
            _positive_float("base_green", base_green)
        super().__init__(
            cloud_policy=cloud_policy,
            overflow_occupancy_threshold=overflow_occupancy_threshold,
            prediction_weight=prediction_weight,
            base_green=base_green,
        )
        missing_policy_configuration = tuple(
            name
            for name in (
                "alpha",
                "horizon",
                "update_interval",
                "configured_prediction_weight",
            )
            if not hasattr(self.cloud_policy, name)
        )
        if missing_policy_configuration:
            raise TypeError(
                "capacity_cloud_policy_contract_missing:"
                + ",".join(missing_policy_configuration)
            )
        self.config = config if config is not None else CapacityAwareConfig.default()
        if overflow_occupancy_threshold is not None:
            self.config = replace(
                self.config, overflow_threshold=float(overflow_occupancy_threshold)
            )
        effective_prediction_weight = (
            prediction_weight
            if prediction_weight is not None
            else self.cloud_policy.configured_prediction_weight
        )
        self.prediction_weight = _nonnegative_float(
            "prediction_weight", effective_prediction_weight
        )
        self.base_green = _positive_float("base_green", self.base_green)
        self.min_green = self.config.min_green
        self.max_green = self.config.max_green
        self.overflow_threshold = self.config.overflow_threshold
        self._capacity_base_green = self.base_green
        self._capacity_prediction_weight = self.prediction_weight
        self._decision_plan_owner = object()
        self._decision_reset_epoch = 0
        self._decision_runtime_revision = 0
        self._pending_decision_plan: _DecisionSnapshot | None = None
        self._committed_decision_plan: _DecisionSnapshot | None = None

    def _duration(self, selected: float, scores: dict[int, PhaseScore]) -> float:
        positive = [
            value.score
            for value in scores.values()
            if isfinite(value.score) and value.score > 0.0
        ]
        average = sum(positive) / len(positive) if positive else 0.0
        duration = (
            self.base_green
            if selected <= 0.0 or average <= 0.0
            else self.base_green * selected / average
        )
        return float(min(self.config.max_green, max(self.config.min_green, duration)))

    def _profile_fingerprint(self) -> tuple[object, ...]:
        return (
            self.config,
            self._capacity_base_green,
            self._capacity_prediction_weight,
            float(self.cloud_policy.alpha),
            int(self.cloud_policy.horizon),
            int(self.cloud_policy.update_interval),
        )

    def _legacy_profile(self) -> _LegacyPlanningProfile:
        return _LegacyPlanningProfile(
            prediction_enabled=self.config.prediction,
            dispatch_enabled=True,
            base_green=self._capacity_base_green,
            min_green=self.config.min_green,
            max_green=self.config.max_green,
            overflow_threshold=self.config.overflow_threshold,
            prediction_weight=self._capacity_prediction_weight,
        )

    def _build_legacy_plan(
        self,
        state: JointState,
        fingerprint: tuple[object, ...],
        profile_fingerprint: tuple[object, ...],
    ) -> _DecisionSnapshot:
        legacy = super().plan_decision(state, profile=self._legacy_profile())
        phase_scores = tuple(
            (index, PhaseScore(score, (), ())) for index, score in legacy.scores
        )
        return _DecisionSnapshot(
            owner_token=self._decision_plan_owner,
            reset_epoch=self._decision_reset_epoch,
            base_revision=self._decision_runtime_revision,
            state_fingerprint=fingerprint,
            state_step=state.step,
            state_timestamp=float(state.timestamp),
            profile_fingerprint=profile_fingerprint,
            phase_scores=phase_scores,
            movement_pressures=tuple((index, ()) for index, _ in phase_scores),
            current_phase=legacy.current_phase,
            elapsed_phase_time=legacy.elapsed_phase_time,
            legal_targets=legacy.legal_targets,
            candidate_phases=legacy.candidate_phases,
            selected_phase=legacy.selected_phase,
            selection_reason=legacy.selection_reason,
            decision_reason=legacy.decision_reason,
            actions=tuple(
                _PlannedAction(
                    action.tls_id,
                    action.action_type,
                    action.value,
                    action.reason,
                )
                for action in legacy.actions
            ),
            legacy_plan=legacy,
        )

    def _build_movement_plan(
        self,
        state: JointState,
        fingerprint: tuple[object, ...],
        profile_fingerprint: tuple[object, ...],
    ) -> _DecisionSnapshot:
        cloud_plan: CloudPolicyPlan | None = None
        predicted: dict[str, float] = {}
        weight = 0.0
        if self.config.prediction:
            cloud_plan = self.cloud_policy.plan(
                state, prediction=True, dispatch=False
            )
            prediction = cloud_plan.prediction_result()
            if prediction is None:
                raise RuntimeError("movement_cloud_prediction_plan_missing_result")
            predicted = prediction.predicted_flows
            weight = self._capacity_prediction_weight
        phase_scores: list[tuple[int, PhaseScore]] = []
        movement_pressures: list[tuple[int, tuple[_MovementPressure, ...]]] = []
        by_index = {phase.phase_index: phase for phase in state.phase_movements}
        for phase in state.phase_movements:
            if not any(signal in phase.signal_state for signal in "Gg"):
                continue
            score, pressures = _score_phase(phase, self.config, predicted, weight)
            phase_scores.append((phase.phase_index, score))
            movement_pressures.append((phase.phase_index, pressures))
            logger.info(
                "capacity_maxpressure phase=%s score=%.6f movements=%s blocked=%s",
                phase.phase_index,
                score.score,
                score.movement_ids,
                score.blocked_movements,
            )
        scores = dict(phase_scores)
        viable = [
            phase
            for phase in state.phase_movements
            if phase.phase_index in scores
            and any(
                movement.queue_vehicles > 0
                and _movement_id(movement) in scores[phase.phase_index].movement_ids
                for movement in phase.movements
            )
        ]
        legal_targets = tuple(
            candidate
            for source, candidate in state.legal_phase_transitions
            if source == state.current_phase
        )
        selected_phase: int | None = None
        actions: tuple[_PlannedAction, ...] = ()
        if not viable:
            selection_reason = "safe_fallback_all_blocked"
            decision_reason = "safe_fallback_all_blocked"
        else:
            highest_score = max(scores[phase.phase_index].score for phase in viable)
            tied = tuple(sorted(
                phase.phase_index
                for phase in viable
                if scores[phase.phase_index].score == highest_score
            ))
            if state.current_phase in tied:
                selected_phase = state.current_phase
                selection_reason = (
                    "equal_score_keep_current"
                    if len(tied) > 1
                    else "current_phase_selected"
                )
            else:
                selected_phase = tied[0]
                selection_reason = (
                    "equal_score_smallest_index"
                    if len(tied) > 1
                    else "highest_viable_pressure"
                )
            if selected_phase == state.current_phase:
                decision_reason = "current_phase_selected"
            elif selected_phase not in legal_targets:
                decision_reason = "safe_fallback_illegal_target"
            elif (
                state.current_phase not in by_index
                or state.elapsed_phase_time < self.config.min_green
            ):
                decision_reason = "minimum_green_not_elapsed"
            else:
                decision_reason = "dispatch_shared_action_validation"
                duration = self._duration(scores[selected_phase].score, scores)
                actions = (
                    _PlannedAction(
                        state.tls_id,
                        "set_phase",
                        selected_phase,
                        f"capacity_maxpressure target={selected_phase}",
                    ),
                    _PlannedAction(
                        state.tls_id,
                        "set_phase_duration",
                        duration,
                        f"dynamic_green target={selected_phase}",
                    ),
                )
        return _DecisionSnapshot(
            owner_token=self._decision_plan_owner,
            reset_epoch=self._decision_reset_epoch,
            base_revision=self._decision_runtime_revision,
            state_fingerprint=fingerprint,
            state_step=state.step,
            state_timestamp=float(state.timestamp),
            profile_fingerprint=profile_fingerprint,
            phase_scores=tuple(phase_scores),
            movement_pressures=tuple(movement_pressures),
            current_phase=state.current_phase,
            elapsed_phase_time=state.elapsed_phase_time,
            legal_targets=legal_targets,
            candidate_phases=tuple(phase.phase_index for phase in viable),
            selected_phase=selected_phase,
            selection_reason=selection_reason,
            decision_reason=decision_reason,
            actions=actions,
            cloud_plan=cloud_plan,
        )

    def plan_decision(self, state: JointState) -> _DecisionSnapshot:
        """Plan/cache a decision without committing controller or policy state."""
        fingerprint = joint_state_fingerprint(state)
        profile_fingerprint = self._profile_fingerprint()
        cache_key = (fingerprint, profile_fingerprint)
        if self._pending_decision_plan is not None:
            pending_key = (
                self._pending_decision_plan.state_fingerprint,
                self._pending_decision_plan.profile_fingerprint,
            )
            if (
                pending_key == cache_key
                and self._pending_decision_plan.reset_epoch
                == self._decision_reset_epoch
                and self._pending_decision_plan.base_revision
                == self._decision_runtime_revision
            ):
                self._validate_nested_decision_plan(self._pending_decision_plan)
                return self._pending_decision_plan
        if self._committed_decision_plan is not None:
            committed_key = (
                self._committed_decision_plan.state_fingerprint,
                self._committed_decision_plan.profile_fingerprint,
            )
            if committed_key == cache_key:
                self._validate_nested_decision_plan(self._committed_decision_plan)
                return self._committed_decision_plan
            current_order = (state.step, float(state.timestamp))
            committed_order = (
                self._committed_decision_plan.state_step,
                self._committed_decision_plan.state_timestamp,
            )
            if current_order <= committed_order:
                raise RuntimeError("decision_history_unavailable")

        if state.phase_movements:
            plan = self._build_movement_plan(
                state, fingerprint, profile_fingerprint
            )
        else:
            plan = self._build_legacy_plan(state, fingerprint, profile_fingerprint)
        self._pending_decision_plan = plan
        return plan

    def _validate_nested_decision_plan(self, plan: _DecisionSnapshot) -> None:
        if plan.legacy_plan is not None:
            super()._validate_legacy_plan(plan.legacy_plan)
        elif plan.cloud_plan is not None:
            self.cloud_policy.validate_plan(plan.cloud_plan)

    def validate_plan(self, plan: _DecisionSnapshot) -> bool:
        """Validate a capacity-aware plan before applying any nested transition."""
        if not isinstance(plan, _DecisionSnapshot):
            raise RuntimeError("decision_plan_invalid_type")
        if plan.owner_token is not self._decision_plan_owner:
            raise RuntimeError("decision_plan_cross_owner")
        if plan.reset_epoch != self._decision_reset_epoch:
            raise RuntimeError("decision_plan_post_reset")
        if plan is self._committed_decision_plan:
            self._validate_nested_decision_plan(plan)
            return False
        if self._pending_decision_plan is not None and plan is not self._pending_decision_plan:
            raise RuntimeError("decision_plan_superseded")
        if plan.base_revision != self._decision_runtime_revision:
            raise RuntimeError("decision_plan_stale_revision")
        if plan is not self._pending_decision_plan:
            raise RuntimeError("decision_plan_not_pending")
        self._validate_nested_decision_plan(plan)
        return True

    def commit_plan(self, plan: _DecisionSnapshot) -> None:
        """Commit the controller/policy transition once; never execute bridge actions."""
        if not self.validate_plan(plan):
            return
        if plan.legacy_plan is not None:
            super().commit_plan(plan.legacy_plan)
        elif plan.cloud_plan is not None:
            self.cloud_policy.commit(plan.cloud_plan)
        self._decision_runtime_revision += 1
        self._committed_decision_plan = plan
        self._pending_decision_plan = None

    def _snapshot_for(self, state: JointState) -> _DecisionSnapshot:
        return self.plan_decision(state)

    def score_breakdown(self, state: JointState) -> dict[int, PhaseScore] | dict[int, float]:
        scores = self._snapshot_for(state).scores()
        if self.config == CapacityAwareConfig.m0():
            return {index: score.score for index, score in scores.items()}
        return scores

    @staticmethod
    def _pressure_record(pressure: _MovementPressure) -> dict[str, object]:
        return {
            "movement_id": pressure.movement_id,
            "incoming_lane": pressure.incoming_lane,
            "outgoing_lane": pressure.outgoing_lane,
            "queue_vehicles": pressure.queue_vehicles,
            "downstream_queue_vehicles": pressure.downstream_queue_vehicles,
            "incoming_capacity": pressure.incoming_capacity,
            "downstream_capacity": pressure.downstream_capacity,
            "downstream_occupancy": pressure.downstream_occupancy,
            "saturation_rate": pressure.saturation_rate,
            "raw_pressure": pressure.raw_pressure,
            "normalized_pressure": pressure.normalized_pressure,
            "prediction_pressure": pressure.prediction_pressure,
            "pressure": pressure.pressure,
            "blocked_reason": pressure.blocked_reason,
        }

    @staticmethod
    def _action_result_record(
        index: int, result: ActionResult
    ) -> dict[str, object]:
        return {
            "action_index": index,
            "action_type": result.action.action_type,
            "value": result.action.value,
            "reason": result.action.reason,
            "accepted": result.accepted,
            "detail": result.detail,
            "reason_code": result.reason_code,
        }

    def audit_record(
        self,
        state: JointState,
        action_results: Iterable[ActionResult] = (),
    ) -> dict[str, object]:
        """Serialize the exact per-tick decision and shared executor outcomes."""
        snapshot = self._snapshot_for(state)
        scores = snapshot.scores()
        pressures = snapshot.pressures()
        phase_scores = {
            str(index): {
                "score": score.score,
                "movement_ids": list(score.movement_ids),
                "blocked_movements": list(score.blocked_movements),
                "movements": [
                    self._pressure_record(pressure)
                    for pressure in pressures[index]
                ],
            }
            for index, score in scores.items()
        }
        actions = [
            {
                "action_type": action.action_type,
                "value": action.value,
                "reason": action.reason,
            }
            for action in snapshot.actions
        ]
        results = [
            self._action_result_record(index, result)
            for index, result in enumerate(action_results)
        ]
        return {
            "layer": self.config.layer,
            "safety_boundary": self.config.safety_boundary,
            "current_phase": snapshot.current_phase,
            "elapsed_phase_time": snapshot.elapsed_phase_time,
            "legal_targets": list(snapshot.legal_targets),
            "candidate_phases": list(snapshot.candidate_phases),
            "phase_scores": phase_scores,
            "selection_reason": snapshot.selection_reason,
            "decision_reason": snapshot.decision_reason,
            "selected_phase": snapshot.selected_phase,
            "final_decision": {
                "action": actions[0]["action_type"] if actions else "no_action",
                "actions": actions,
                "action_results": results,
            },
        }

    def step(self, state: JointState) -> list[ControlAction]:
        snapshot = self._snapshot_for(state)
        logger.info(
            "capacity_maxpressure selection=%s decision=%s target=%s actions=%s",
            snapshot.selection_reason,
            snapshot.decision_reason,
            snapshot.selected_phase,
            [action.action_type for action in snapshot.actions],
        )
        self.commit_plan(snapshot)
        return [action.control_action() for action in snapshot.actions]

    def init(self, scene) -> None:
        validate_capacity_aware_scene(scene.meta.sumo_net)
        self._decision_reset_epoch += 1
        self._decision_runtime_revision = 0
        self._pending_decision_plan = None
        self._committed_decision_plan = None
        self._legacy_reset_epoch += 1
        self._legacy_runtime_revision = 0
        self._pending_legacy_plan = None
        self._committed_legacy_plan = None
        super().init(scene)

    def reset(self) -> None:
        super().reset()
        self.base_green = self._capacity_base_green
        self.min_green = self.config.min_green
        self.max_green = self.config.max_green
        self.overflow_threshold = self.config.overflow_threshold
        self.prediction_weight = self._capacity_prediction_weight
        self._decision_reset_epoch += 1
        self._decision_runtime_revision = 0
        self._pending_decision_plan = None
        self._committed_decision_plan = None

    @property
    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "layer": self.config.layer,
            "safety_boundary": self.config.safety_boundary,
            "capacity_normalization": self.config.capacity_normalization,
            "spillback_gate": self.config.spillback_gate,
            "prediction_enabled": self.config.prediction,
            "horizon_seconds": float(self.cloud_policy.horizon),
            "prediction_weight": self._capacity_prediction_weight,
            "min_green": self.config.min_green,
            "max_green": self.config.max_green,
            "overflow_threshold": self.config.overflow_threshold,
        }
