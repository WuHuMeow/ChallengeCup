"""Legacy phase-state CA-MP controller retained for compatibility.

The registered capacity-aware algorithm uses the movement-level layered
ablations in ``capacity_aware_max_pressure``. This module remains only for
older callers that provide ``PhaseTrafficState`` rather than movement state.
"""

from __future__ import annotations

from math import isfinite
from typing import List

from algorithms.base import BaseControlAlgorithm
from cloud.cloud_policy import CloudPolicy
from core.config import get_config
from core.types import ControlAction, JointState, PhaseTrafficState, Scene


class CAMaxPressureAlgorithm(BaseControlAlgorithm):
    """Select safe legal phases using normalized upstream/downstream pressure."""

    def __init__(
        self,
        cloud_policy: CloudPolicy | None = None,
        overflow_occupancy_threshold: float | None = None,
        prediction_weight: float | None = None,
        base_green: float | None = None,
    ) -> None:
        cfg = get_config().get("algorithms.ca_maxpressure", {})
        self.cloud_policy = cloud_policy or CloudPolicy()
        self.scene: Scene | None = None
        self.overflow_threshold = float(
            overflow_occupancy_threshold
            if overflow_occupancy_threshold is not None
            else cfg.get("overflow_occupancy_threshold", 0.9)
        )
        self.prediction_weight = float(
            prediction_weight
            if prediction_weight is not None
            else cfg.get("prediction_weight", 0.15)
        )
        self._frozen_base_green = (
            float(base_green) if base_green is not None else None
        )
        self.base_green = float(
            base_green if base_green is not None else cfg.get("base_green", 30)
        )
        self.min_green = float(cfg.get("min_green", 10))
        self.max_green = float(cfg.get("max_green", 90))
        self.yellow_duration = float(cfg.get("yellow_duration", 3))
        self.all_red_duration = float(cfg.get("all_red_duration", 1))
        self.pending_target_phase: int | None = None
        self._configured_phase: int | None = None

    def init(self, scene: Scene) -> None:
        self.scene = scene

    def phase_pressure(
        self,
        phase: PhaseTrafficState,
        predicted_arrivals: float,
    ) -> float:
        """Return normalized pressure or block a saturated downstream."""
        if phase.outgoing_occupancy >= self.overflow_threshold:
            return float("-inf")
        incoming = phase.incoming_queue / max(phase.incoming_capacity, 1.0)
        outgoing = phase.outgoing_queue / max(phase.outgoing_capacity, 1.0)
        prediction = self.prediction_weight * (
            predicted_arrivals / max(phase.incoming_capacity, 1.0)
        )
        return incoming - outgoing + prediction

    @staticmethod
    def _is_green(phase: PhaseTrafficState | None) -> bool:
        return phase is not None and any(
            value in phase.signal_state for value in "Gg"
        )

    def _transition_duration(self, phase: PhaseTrafficState) -> float:
        if any(value in phase.signal_state for value in "yY"):
            return self.yellow_duration
        return self.all_red_duration

    @staticmethod
    def _transition_after(
        current_phase: int,
        target_phase: int,
        phases: list[PhaseTrafficState],
    ) -> PhaseTrafficState | None:
        ordered = sorted(phases, key=lambda phase: phase.phase_index)
        if not ordered:
            return None
        positions = {phase.phase_index: index for index, phase in enumerate(ordered)}
        if current_phase not in positions:
            return None
        index = positions[current_phase]
        for offset in range(1, len(ordered)):
            candidate = ordered[(index + offset) % len(ordered)]
            if candidate.phase_index == target_phase:
                return None
            if not CAMaxPressureAlgorithm._is_green(candidate):
                return candidate
        return None

    def _dynamic_duration(
        self,
        selected_pressure: float,
        scores: dict[int, float],
    ) -> float:
        finite_positive = [
            max(score, 0.0) for score in scores.values() if isfinite(score)
        ]
        average = (
            sum(finite_positive) / len(finite_positive)
            if finite_positive
            else 0.0
        )
        if selected_pressure <= 0 or average <= 0:
            duration = self.base_green
        else:
            duration = self.base_green * selected_pressure / average
        return float(min(self.max_green, max(self.min_green, duration)))

    def _activate(
        self,
        state: JointState,
        target: int,
        duration: float,
        reason: str,
    ) -> List[ControlAction]:
        self.pending_target_phase = None
        self._configured_phase = target
        return [
            ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=int(target),
                reason=reason,
            ),
            ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase_duration",
                value=float(duration),
                reason=f"dynamic_green target={target}",
            ),
        ]

    def step(self, state: JointState) -> List[ControlAction]:
        if not state.phase_states:
            return []

        prediction = self.cloud_policy.predict(state)
        params = self.cloud_policy.dispatch_params(state)
        self.base_green = (
            self._frozen_base_green
            if self._frozen_base_green is not None
            else float(params.get("base_green", self.base_green))
        )
        self.min_green = float(params.get("min_green", self.min_green))
        self.max_green = float(params.get("max_green", self.max_green))

        phases = list(state.phase_states)
        by_index = {phase.phase_index: phase for phase in phases}
        green_phases = [phase for phase in phases if self._is_green(phase)]
        if not green_phases:
            return []

        scores: dict[int, float] = {}
        for phase in green_phases:
            predicted_arrivals = sum(
                prediction.predicted_flows.get(lane, 0.0)
                for lane in phase.incoming_lanes
            )
            scores[phase.phase_index] = self.phase_pressure(
                phase,
                predicted_arrivals,
            )
        viable = [
            phase
            for phase in green_phases
            if isfinite(scores[phase.phase_index])
        ]
        if not viable:
            return []

        selected = max(
            viable,
            key=lambda phase: (
                scores[phase.phase_index],
                phase.phase_index == state.current_phase,
                -phase.phase_index,
            ),
        )
        current = by_index.get(state.current_phase)

        if (
            self.pending_target_phase is not None
            and state.current_phase == self.pending_target_phase
        ):
            selected = by_index[self.pending_target_phase]
            duration = self._dynamic_duration(
                scores.get(selected.phase_index, 0.0),
                scores,
            )
            return self._activate(
                state,
                selected.phase_index,
                duration,
                f"pending_target_reached target={selected.phase_index}",
            )

        if self.pending_target_phase is not None and not self._is_green(current):
            if (
                current is None
                or state.elapsed_phase_time < self._transition_duration(current)
            ):
                return []
            target = self.pending_target_phase
            return self._activate(
                state,
                target,
                self._dynamic_duration(scores.get(target, 0.0), scores),
                f"transition_complete target={target}",
            )

        if (
            self._is_green(current)
            and state.elapsed_phase_time >= self.max_green
        ):
            alternatives = [
                phase
                for phase in viable
                if phase.phase_index != state.current_phase
            ]
            if alternatives:
                selected = max(
                    alternatives,
                    key=lambda phase: (
                        scores[phase.phase_index],
                        -phase.phase_index,
                    ),
                )

        if selected.phase_index == state.current_phase:
            if self._configured_phase == state.current_phase:
                return []
            return self._activate(
                state,
                selected.phase_index,
                self._dynamic_duration(scores[selected.phase_index], scores),
                f"max_pressure target={selected.phase_index}",
            )

        if self._is_green(current) and state.elapsed_phase_time < self.min_green:
            return []

        transition = self._transition_after(
            state.current_phase,
            selected.phase_index,
            phases,
        )
        if transition is None:
            return self._activate(
                state,
                selected.phase_index,
                self._dynamic_duration(scores[selected.phase_index], scores),
                f"direct_switch target={selected.phase_index}",
            )

        self.pending_target_phase = selected.phase_index
        self._configured_phase = None
        transition_duration = self._transition_duration(transition)
        return [
            ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=int(transition.phase_index),
                reason=(
                    f"safe_transition phase={transition.phase_index} "
                    f"target={selected.phase_index}"
                ),
            ),
            ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase_duration",
                value=float(transition_duration),
                reason=f"transition_duration target={selected.phase_index}",
            ),
        ]

    def reset(self) -> None:
        self.pending_target_phase = None
        self._configured_phase = None
        self.cloud_policy.reset()

    @property
    def name(self) -> str:
        return "capacity_aware_maxpressure"

    @property
    def manifest(self) -> dict[str, object]:
        payload = super().manifest
        payload["enhancements"] = (
            "capacity_normalization",
            "spillback_gating",
            "cloud_prediction",
            "dynamic_green",
        )
        return payload
