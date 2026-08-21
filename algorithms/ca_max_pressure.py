"""Legacy phase-state CA-MP controller retained for compatibility.

The registered capacity-aware algorithm uses the movement-level layered
ablations in ``capacity_aware_max_pressure``. This module remains only for
older callers that provide ``PhaseTrafficState`` rather than movement state.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import List

from algorithms.base import BaseControlAlgorithm
from cloud.cloud_policy import CloudPolicy, CloudPolicyPlan, joint_state_fingerprint
from core.config import get_config
from core.types import ControlAction, JointState, PhaseTrafficState, Scene


@dataclass(frozen=True)
class _LegacyPlanningProfile:
    prediction_enabled: bool
    dispatch_enabled: bool
    base_green: float
    min_green: float
    max_green: float
    overflow_threshold: float
    prediction_weight: float


@dataclass(frozen=True)
class _LegacyPlannedAction:
    tls_id: str
    action_type: str
    value: int | float
    reason: str

    def control_action(self) -> ControlAction:
        return ControlAction(self.tls_id, self.action_type, self.value, self.reason)


@dataclass(frozen=True)
class LegacyDecisionPlan:
    owner_token: object
    reset_epoch: int
    base_revision: int
    state_fingerprint: tuple[object, ...]
    state_step: int
    state_timestamp: float
    profile: _LegacyPlanningProfile
    cloud_plan: CloudPolicyPlan | None
    scores: tuple[tuple[int, float], ...]
    current_phase: int
    elapsed_phase_time: float
    legal_targets: tuple[int, ...]
    candidate_phases: tuple[int, ...]
    selected_phase: int | None
    selection_reason: str
    decision_reason: str
    actions: tuple[_LegacyPlannedAction, ...]
    next_pending_target_phase: int | None
    next_configured_phase: int | None
    next_base_green: float
    next_min_green: float
    next_max_green: float

    def control_actions(self) -> list[ControlAction]:
        return [action.control_action() for action in self.actions]


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
        self.cloud_policy = cloud_policy if cloud_policy is not None else CloudPolicy()
        missing_transaction_methods = tuple(
            name
            for name in ("plan", "validate_plan", "commit", "reset")
            if not callable(getattr(self.cloud_policy, name, None))
        )
        if missing_transaction_methods:
            raise TypeError(
                "cloud_policy_transactional_contract_missing:"
                + ",".join(missing_transaction_methods)
            )
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
        self._initial_base_green = self.base_green
        self._initial_min_green = self.min_green
        self._initial_max_green = self.max_green
        self._initial_overflow_threshold = self.overflow_threshold
        self._initial_prediction_weight = self.prediction_weight
        self._initial_yellow_duration = self.yellow_duration
        self._initial_all_red_duration = self.all_red_duration
        self._legacy_plan_owner = object()
        self._legacy_reset_epoch = 0
        self._legacy_runtime_revision = 0
        self._pending_legacy_plan: LegacyDecisionPlan | None = None
        self._committed_legacy_plan: LegacyDecisionPlan | None = None

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

    @staticmethod
    def _phase_pressure_for(
        phase: PhaseTrafficState,
        predicted_arrivals: float,
        profile: _LegacyPlanningProfile,
    ) -> float:
        if phase.outgoing_occupancy >= profile.overflow_threshold:
            return float("-inf")
        incoming = phase.incoming_queue / max(phase.incoming_capacity, 1.0)
        outgoing = phase.outgoing_queue / max(phase.outgoing_capacity, 1.0)
        prediction = profile.prediction_weight * (
            predicted_arrivals / max(phase.incoming_capacity, 1.0)
        )
        return incoming - outgoing + prediction

    @staticmethod
    def _planned_duration(
        selected_pressure: float,
        scores: dict[int, float],
        profile: _LegacyPlanningProfile,
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
            duration = profile.base_green
        else:
            duration = profile.base_green * selected_pressure / average
        return float(min(profile.max_green, max(profile.min_green, duration)))

    @staticmethod
    def _activation_actions(
        state: JointState,
        target: int,
        duration: float,
        reason: str,
    ) -> tuple[_LegacyPlannedAction, ...]:
        return (
            _LegacyPlannedAction(
                state.tls_id,
                "set_phase",
                int(target),
                reason,
            ),
            _LegacyPlannedAction(
                state.tls_id,
                "set_phase_duration",
                float(duration),
                f"dynamic_green target={target}",
            ),
        )

    def _profile_and_cloud_plan(
        self,
        state: JointState,
        profile: _LegacyPlanningProfile | None,
    ) -> tuple[_LegacyPlanningProfile, CloudPolicyPlan | None, dict[str, float]]:
        if not state.phase_states:
            effective = profile or _LegacyPlanningProfile(
                True,
                True,
                self.base_green,
                self.min_green,
                self.max_green,
                self.overflow_threshold,
                self.prediction_weight,
            )
            return effective, None, {}

        if profile is None:
            cloud_plan = self.cloud_policy.plan(
                state, prediction=True, dispatch=True
            )
            params = cloud_plan.params()
            if params is None:
                raise RuntimeError("legacy_cloud_dispatch_plan_missing_params")
            effective = _LegacyPlanningProfile(
                True,
                True,
                (
                    self._frozen_base_green
                    if self._frozen_base_green is not None
                    else float(params.get("base_green", self.base_green))
                ),
                float(params.get("min_green", self.min_green)),
                float(params.get("max_green", self.max_green)),
                self.overflow_threshold,
                self.prediction_weight,
            )
        else:
            effective = profile
            cloud_plan = self.cloud_policy.plan(
                state,
                prediction=profile.prediction_enabled,
                dispatch=profile.dispatch_enabled,
            )

        predicted: dict[str, float] = {}
        if effective.prediction_enabled:
            prediction_result = cloud_plan.prediction_result()
            if prediction_result is None:
                raise RuntimeError("legacy_cloud_prediction_plan_missing_result")
            predicted = prediction_result.predicted_flows
        return effective, cloud_plan, predicted

    def plan_decision(
        self,
        state: JointState,
        *,
        profile: _LegacyPlanningProfile | None = None,
    ) -> LegacyDecisionPlan:
        """Build one immutable legacy decision without committing runtime state."""
        effective, cloud_plan, predicted = self._profile_and_cloud_plan(state, profile)
        fingerprint = joint_state_fingerprint(state)
        cache_key = (fingerprint, effective)
        if self._pending_legacy_plan is not None:
            pending_key = (
                self._pending_legacy_plan.state_fingerprint,
                self._pending_legacy_plan.profile,
            )
            if (
                pending_key == cache_key
                and self._pending_legacy_plan.reset_epoch == self._legacy_reset_epoch
                and self._pending_legacy_plan.base_revision
                == self._legacy_runtime_revision
            ):
                return self._pending_legacy_plan
        if self._committed_legacy_plan is not None:
            committed_key = (
                self._committed_legacy_plan.state_fingerprint,
                self._committed_legacy_plan.profile,
            )
            if committed_key == cache_key:
                return self._committed_legacy_plan

        phases = list(state.phase_states)
        by_index = {phase.phase_index: phase for phase in phases}
        green_phases = [phase for phase in phases if self._is_green(phase)]
        scores: dict[int, float] = {}
        viable: list[PhaseTrafficState] = []
        selected_phase: int | None = None
        actions: tuple[_LegacyPlannedAction, ...] = ()
        next_pending = self.pending_target_phase
        next_configured = self._configured_phase

        if not phases:
            selection_reason = "no_phase_states"
            decision_reason = "no_phase_states"
        elif not green_phases:
            selection_reason = "no_green_phase"
            decision_reason = "no_green_phase"
        else:
            for phase in green_phases:
                predicted_arrivals = sum(
                    predicted.get(lane, 0.0) for lane in phase.incoming_lanes
                )
                scores[phase.phase_index] = self._phase_pressure_for(
                    phase, predicted_arrivals, effective
                )
            viable = [
                phase
                for phase in green_phases
                if isfinite(scores[phase.phase_index])
            ]
            if not viable:
                selection_reason = "safe_fallback_all_blocked"
                decision_reason = "safe_fallback_all_blocked"
            else:
                selected = max(
                    viable,
                    key=lambda phase: (
                        scores[phase.phase_index],
                        phase.phase_index == state.current_phase,
                        -phase.phase_index,
                    ),
                )
                selected_phase = selected.phase_index
                highest_score = scores[selected_phase]
                tied = tuple(
                    sorted(
                        phase.phase_index
                        for phase in viable
                        if scores[phase.phase_index] == highest_score
                    )
                )
                if state.current_phase in tied:
                    selection_reason = (
                        "equal_score_keep_current"
                        if len(tied) > 1
                        else "current_phase_selected"
                    )
                else:
                    selection_reason = (
                        "equal_score_smallest_index"
                        if len(tied) > 1
                        else "highest_viable_pressure"
                    )
                current = by_index.get(state.current_phase)

                if (
                    self.pending_target_phase is not None
                    and state.current_phase == self.pending_target_phase
                ):
                    selected_phase = self.pending_target_phase
                    selection_reason = "pending_target_reached"
                    decision_reason = "pending_target_reached"
                    actions = self._activation_actions(
                        state,
                        selected_phase,
                        self._planned_duration(
                            scores.get(selected_phase, 0.0), scores, effective
                        ),
                        f"pending_target_reached target={selected_phase}",
                    )
                    next_pending = None
                    next_configured = selected_phase
                elif self.pending_target_phase is not None and not self._is_green(current):
                    selected_phase = self.pending_target_phase
                    selection_reason = "pending_target_in_progress"
                    if (
                        current is None
                        or state.elapsed_phase_time < self._transition_duration(current)
                    ):
                        decision_reason = "pending_transition_wait"
                    else:
                        decision_reason = "pending_transition_complete"
                        actions = self._activation_actions(
                            state,
                            selected_phase,
                            self._planned_duration(
                                scores.get(selected_phase, 0.0), scores, effective
                            ),
                            f"transition_complete target={selected_phase}",
                        )
                        next_pending = None
                        next_configured = selected_phase
                else:
                    if (
                        self._is_green(current)
                        and state.elapsed_phase_time >= effective.max_green
                        and selected_phase == state.current_phase
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
                            selected_phase = selected.phase_index
                            highest_alternative = scores[selected_phase]
                            tied_alternatives = tuple(
                                sorted(
                                    phase.phase_index
                                    for phase in alternatives
                                    if scores[phase.phase_index]
                                    == highest_alternative
                                )
                            )
                            selection_reason = (
                                "max_green_forced_equal_score_smallest_index"
                                if len(tied_alternatives) > 1
                                else "max_green_forced_alternative"
                            )

                    if selected_phase == state.current_phase:
                        if self._configured_phase == state.current_phase:
                            decision_reason = "already_configured"
                        else:
                            decision_reason = "dispatch_legacy_phase_state"
                            actions = self._activation_actions(
                                state,
                                selected_phase,
                                self._planned_duration(
                                    scores[selected_phase], scores, effective
                                ),
                                f"max_pressure target={selected_phase}",
                            )
                            next_pending = None
                            next_configured = selected_phase
                    elif (
                        self._is_green(current)
                        and state.elapsed_phase_time < effective.min_green
                    ):
                        decision_reason = "minimum_green_not_elapsed"
                    else:
                        transition = self._transition_after(
                            state.current_phase,
                            selected_phase,
                            phases,
                        )
                        if transition is None:
                            decision_reason = "direct_switch"
                            actions = self._activation_actions(
                                state,
                                selected_phase,
                                self._planned_duration(
                                    scores[selected_phase], scores, effective
                                ),
                                f"direct_switch target={selected_phase}",
                            )
                            next_pending = None
                            next_configured = selected_phase
                        else:
                            decision_reason = "safe_transition"
                            next_pending = selected_phase
                            next_configured = None
                            transition_duration = self._transition_duration(transition)
                            actions = (
                                _LegacyPlannedAction(
                                    state.tls_id,
                                    "set_phase",
                                    int(transition.phase_index),
                                    (
                                        f"safe_transition phase={transition.phase_index} "
                                        f"target={selected_phase}"
                                    ),
                                ),
                                _LegacyPlannedAction(
                                    state.tls_id,
                                    "set_phase_duration",
                                    float(transition_duration),
                                    f"transition_duration target={selected_phase}",
                                ),
                            )

        plan = LegacyDecisionPlan(
            owner_token=self._legacy_plan_owner,
            reset_epoch=self._legacy_reset_epoch,
            base_revision=self._legacy_runtime_revision,
            state_fingerprint=fingerprint,
            state_step=state.step,
            state_timestamp=float(state.timestamp),
            profile=effective,
            cloud_plan=cloud_plan,
            scores=tuple(scores.items()),
            current_phase=state.current_phase,
            elapsed_phase_time=state.elapsed_phase_time,
            legal_targets=tuple(
                target
                for source, target in state.legal_phase_transitions
                if source == state.current_phase
            ),
            candidate_phases=tuple(phase.phase_index for phase in viable),
            selected_phase=selected_phase,
            selection_reason=selection_reason,
            decision_reason=decision_reason,
            actions=actions,
            next_pending_target_phase=next_pending,
            next_configured_phase=next_configured,
            next_base_green=effective.base_green,
            next_min_green=effective.min_green,
            next_max_green=effective.max_green,
        )
        self._pending_legacy_plan = plan
        return plan

    def _validate_legacy_plan(self, plan: LegacyDecisionPlan) -> bool:
        """Validate a legacy plan, returning False only after its first commit."""
        if not isinstance(plan, LegacyDecisionPlan):
            raise RuntimeError("legacy_plan_invalid_type")
        if plan.owner_token is not self._legacy_plan_owner:
            raise RuntimeError("legacy_plan_cross_owner")
        if plan.reset_epoch != self._legacy_reset_epoch:
            raise RuntimeError("legacy_plan_post_reset")
        if self._pending_legacy_plan is not None and plan is not self._pending_legacy_plan:
            raise RuntimeError("legacy_plan_superseded")
        if self._pending_legacy_plan is None and plan is self._committed_legacy_plan:
            return False
        if plan.base_revision != self._legacy_runtime_revision:
            raise RuntimeError("legacy_plan_stale_revision")
        if plan is not self._pending_legacy_plan:
            raise RuntimeError("legacy_plan_not_pending")
        if plan.cloud_plan is not None:
            self.cloud_policy.validate_plan(plan.cloud_plan)
        return True

    def validate_plan(self, plan: LegacyDecisionPlan) -> bool:
        return self._validate_legacy_plan(plan)

    def commit_plan(self, plan: LegacyDecisionPlan) -> None:
        """Commit controller and cloud next-state exactly once."""
        if not self._validate_legacy_plan(plan):
            return
        self.pending_target_phase = plan.next_pending_target_phase
        self._configured_phase = plan.next_configured_phase
        self.base_green = plan.next_base_green
        self.min_green = plan.next_min_green
        self.max_green = plan.next_max_green
        if plan.cloud_plan is not None:
            self.cloud_policy.commit(plan.cloud_plan)
        self._legacy_runtime_revision += 1
        self._committed_legacy_plan = plan
        self._pending_legacy_plan = None

    def step(self, state: JointState) -> List[ControlAction]:
        plan = self.plan_decision(state)
        self.commit_plan(plan)
        return plan.control_actions()

    def reset(self) -> None:
        self.pending_target_phase = None
        self._configured_phase = None
        self.base_green = self._initial_base_green
        self.min_green = self._initial_min_green
        self.max_green = self._initial_max_green
        self.overflow_threshold = self._initial_overflow_threshold
        self.prediction_weight = self._initial_prediction_weight
        self.yellow_duration = self._initial_yellow_duration
        self.all_red_duration = self._initial_all_red_duration
        self._legacy_reset_epoch += 1
        self._legacy_runtime_revision = 0
        self._pending_legacy_plan = None
        self._committed_legacy_plan = None
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
