"""Layered, movement-level capacity-aware MaxPressure ablations."""

from __future__ import annotations

from dataclasses import dataclass, replace
import logging
from math import isfinite

from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from cloud.cloud_policy import CloudPolicy
from core.movements import MovementState, PhaseMovementState
from core.types import ControlAction, JointState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapacityAwareConfig:
    capacity_normalization: bool
    spillback_gate: bool
    prediction: bool
    min_green: float
    max_green: float
    overflow_threshold: float

    @classmethod
    def m0(cls) -> "CapacityAwareConfig":
        return cls(False, False, False, 10.0, 30.0, 0.9)

    @classmethod
    def m1(cls) -> "CapacityAwareConfig":
        return cls(True, False, False, 10.0, 30.0, 0.9)

    @classmethod
    def m2(cls) -> "CapacityAwareConfig":
        return cls(True, True, False, 10.0, 30.0, 0.9)

    @classmethod
    def m3(cls) -> "CapacityAwareConfig":
        return cls(True, True, False, 10.0, 30.0, 0.9)

    @classmethod
    def m4(cls) -> "CapacityAwareConfig":
        return cls(True, True, True, 10.0, 30.0, 0.9)

    @classmethod
    def default(cls) -> "CapacityAwareConfig":
        return cls.m3()


@dataclass(frozen=True)
class PhaseScore:
    score: float
    movement_ids: tuple[str, ...]
    blocked_movements: tuple[str, ...]


def _movement_id(movement: MovementState) -> str:
    return f"{movement.key.incoming_lane}->{movement.key.outgoing_lane}"


def phase_score(
    state: PhaseMovementState,
    config: CapacityAwareConfig,
    predicted_arrivals: dict[str, float] | None = None,
    prediction_weight: float = 0.0,
) -> PhaseScore:
    """Score one phase from raw or capacity-normalized movement pressure."""
    total = 0.0
    selected: list[str] = []
    blocked: list[str] = []
    for movement in state.movements:
        movement_id = _movement_id(movement)
        if (
            config.spillback_gate
            and movement.downstream_occupancy >= config.overflow_threshold
        ):
            blocked.append(movement_id)
            continue
        if config.capacity_normalization:
            pressure = movement.saturation_rate * (
                movement.queue_vehicles / movement.incoming_capacity
                - movement.downstream_queue_vehicles / movement.downstream_capacity
            )
        else:
            pressure = movement.saturation_rate * (
                movement.queue_vehicles - movement.downstream_queue_vehicles
            )
        if config.prediction and predicted_arrivals is not None:
            arrivals = predicted_arrivals.get(movement.key.incoming_lane, 0.0)
            pressure += (
                movement.saturation_rate
                * prediction_weight
                * arrivals
                / movement.incoming_capacity
            )
        total += pressure
        selected.append(movement_id)
    return PhaseScore(float(total), tuple(selected), tuple(blocked))


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
        super().__init__(
            cloud_policy=cloud_policy,
            overflow_occupancy_threshold=overflow_occupancy_threshold,
            prediction_weight=prediction_weight,
            base_green=base_green,
        )
        self.config = config or CapacityAwareConfig.default()
        if overflow_occupancy_threshold is not None:
            self.config = replace(
                self.config, overflow_threshold=float(overflow_occupancy_threshold)
            )
        self.cloud_policy = cloud_policy or CloudPolicy()
        if prediction_weight is not None:
            self.cloud_policy.configured_prediction_weight = float(prediction_weight)
        self.min_green = self.config.min_green
        self.max_green = self.config.max_green
        self.overflow_threshold = self.config.overflow_threshold

    def _predicted_arrivals(self, state: JointState) -> tuple[dict[str, float], float]:
        if not self.config.prediction:
            return {}, 0.0
        prediction = self.cloud_policy.predict(state)
        return prediction.predicted_flows, float(
            self.cloud_policy.configured_prediction_weight
        )

    def _scores(self, state: JointState) -> dict[int, PhaseScore]:
        predicted, weight = self._predicted_arrivals(state)
        scores: dict[int, PhaseScore] = {}
        for phase in state.phase_movements:
            if not any(signal in phase.signal_state for signal in "Gg"):
                continue
            score = phase_score(phase, self.config, predicted, weight)
            scores[phase.phase_index] = score
            logger.info(
                "capacity_maxpressure phase=%s score=%.6f movements=%s blocked=%s",
                phase.phase_index,
                score.score,
                score.movement_ids,
                score.blocked_movements,
            )
        return scores

    def score_breakdown(self, state: JointState) -> dict[int, PhaseScore] | dict[int, float]:
        scores = self._scores(state)
        if self.config == CapacityAwareConfig.m0():
            return {index: score.score for index, score in scores.items()}
        return scores

    def _duration(self, selected: float, scores: dict[int, PhaseScore]) -> float:
        positive = [max(value.score, 0.0) for value in scores.values()]
        average = sum(positive) / len(positive) if positive else 0.0
        base = self.base_green
        duration = base if selected <= 0.0 or average <= 0.0 else base * selected / average
        return float(min(self.config.max_green, max(self.config.min_green, duration)))

    def step(self, state: JointState) -> list[ControlAction]:
        if not state.phase_movements:
            return super().step(state)
        scores = self._scores(state)
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
        if not viable:
            logger.info("capacity_maxpressure safe_fallback current=%s all_blocked", state.current_phase)
            return []
        target = max(
            viable,
            key=lambda phase: (
                scores[phase.phase_index].score,
                phase.phase_index == state.current_phase,
                -phase.phase_index,
            ),
        )
        if target.phase_index == state.current_phase:
            return []
        legal_targets = {
            candidate for source, candidate in state.legal_phase_transitions if source == state.current_phase
        }
        if target.phase_index not in legal_targets:
            logger.info("capacity_maxpressure safe_fallback current=%s target=%s illegal", state.current_phase, target.phase_index)
            return []
        current = next(
            (phase for phase in state.phase_movements if phase.phase_index == state.current_phase),
            None,
        )
        if current is None or state.elapsed_phase_time < self.config.min_green:
            return []
        duration = self._duration(scores[target.phase_index].score, scores)
        return [
            ControlAction(state.tls_id, "set_phase", target.phase_index, f"capacity_maxpressure target={target.phase_index}"),
            ControlAction(state.tls_id, "set_phase_duration", duration, f"dynamic_green target={target.phase_index}"),
        ]

    @property
    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "capacity_normalization": self.config.capacity_normalization,
            "spillback_gate": self.config.spillback_gate,
            "prediction_enabled": self.config.prediction,
            "horizon_seconds": float(self.cloud_policy.horizon),
            "prediction_weight": self.cloud_policy.configured_prediction_weight,
            "min_green": self.config.min_green,
            "max_green": self.config.max_green,
            "overflow_threshold": self.config.overflow_threshold,
        }
