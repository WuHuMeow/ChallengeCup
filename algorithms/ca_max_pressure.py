"""Phase-aware Capacity-Aware MaxPressure (CA-MP) control."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import List, Optional, Tuple

from algorithms.base import BaseControlAlgorithm
from cloud.cloud_policy import CloudPolicy
from core.config import get_config
from core.types import ControlAction, JointState, PhaseTrafficState, Scene


@dataclass(frozen=True)
class _LegacyPlanningProfile:
    """Parameter bundle captured at planning time (no live mutation)."""

    prediction_enabled: bool
    dispatch_enabled: bool
    base_green: float
    min_green: float
    max_green: float
    overflow_threshold: float
    prediction_weight: float
    delegation_mode: bool = False


@dataclass(frozen=True)
class LegacyDecisionPlan:
    """Immutable legacy (phase-state) decision awaiting commit."""

    fingerprint: tuple
    scores: Tuple[Tuple[int, float], ...]
    current_phase: int
    elapsed_phase_time: float
    legal_targets: Tuple[int, ...]
    candidate_phases: Tuple[int, ...]
    selected_phase: Optional[int]
    selection_reason: str
    decision_reason: str
    actions: Tuple[ControlAction, ...]
    cloud_plan: object | None = None
    next_pending_target: Optional[int] = None
    next_configured_phase: Optional[int] = None


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
        self.cloud_policy = (
            cloud_policy if cloud_policy is not None else CloudPolicy()
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
        self._legacy_reset_epoch = 0
        self._legacy_runtime_revision = 0
        self._pending_legacy_plan: LegacyDecisionPlan | None = None
        self._committed_legacy_plan: LegacyDecisionPlan | None = None

    def init(self, scene: Scene) -> None:
        self.scene = scene
        self._legacy_reset_epoch += 1
        self._legacy_runtime_revision = 0
        self._pending_legacy_plan = None
        self._committed_legacy_plan = None
        self.pending_target_phase = None
        self._configured_phase = None

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
        plan = self.plan_decision(state)
        self.commit_plan(plan)
        return list(plan.actions)

    def plan_decision(
        self,
        state: JointState,
        profile: _LegacyPlanningProfile | None = None,
    ) -> LegacyDecisionPlan:
        """Plan one legacy decision without mutating controller or cloud state."""
        from cloud.cloud_policy import joint_state_fingerprint

        fingerprint = joint_state_fingerprint(state)
        if profile is None:
            profile = self._legacy_profile()
        if not state.phase_states:
            return LegacyDecisionPlan(
                fingerprint=fingerprint,
                scores=(),
                current_phase=state.current_phase,
                elapsed_phase_time=state.elapsed_phase_time,
                legal_targets=(),
                candidate_phases=(),
                selected_phase=None,
                selection_reason="no_phase_states",
                decision_reason="no_phase_states",
                actions=(),
            )

        cloud_plan = self.cloud_policy.plan(
            state,
            prediction=profile.prediction_enabled,
            dispatch=profile.dispatch_enabled,
        )
        return self._plan_from_phase_states(
            state, profile, cloud_plan, fingerprint
        )

    def _legacy_profile(self) -> _LegacyPlanningProfile:
        return _LegacyPlanningProfile(
            prediction_enabled=True,
            dispatch_enabled=True,
            base_green=self._frozen_base_green,
            min_green=self.min_green,
            max_green=self.max_green,
            overflow_threshold=self.overflow_threshold,
            prediction_weight=self.prediction_weight,
        )

    def _plan_from_phase_states(
        self,
        state: JointState,
        profile: _LegacyPlanningProfile,
        cloud_plan,
        fingerprint: tuple,
    ) -> LegacyDecisionPlan:
        """Pure decision body shared by step() and external planners."""
        from cloud.cloud_policy import joint_state_fingerprint

        prediction = (
            cloud_plan.prediction_result()
            if profile.prediction_enabled
            else None
        )
        params = cloud_plan.params or {}
        base_green = (
            profile.base_green
            if profile.base_green is not None
            else float(params.get("base_green", self.base_green))
        )
        min_green = (
            profile.min_green
            if profile.min_green is not None
            else float(params.get("min_green", self.min_green))
        )
        max_green = (
            profile.max_green
            if profile.max_green is not None
            else float(params.get("max_green", self.max_green))
        )

        phases = list(state.phase_states)
        by_index = {phase.phase_index: phase for phase in phases}
        green_phases = [phase for phase in phases if self._is_green(phase)]
        if not green_phases:
            return LegacyDecisionPlan(
                fingerprint=fingerprint,
                scores=(),
                current_phase=state.current_phase,
                elapsed_phase_time=state.elapsed_phase_time,
                legal_targets=(),
                candidate_phases=(),
                selected_phase=None,
                selection_reason="no_green_phases",
                decision_reason="no_green_phases",
                actions=(),
                cloud_plan=cloud_plan,
            )

        scores: dict[int, float] = {}
        predicted_flows = (
            prediction.predicted_flows if prediction is not None else {}
        )
        for phase in green_phases:
            predicted_arrivals = sum(
                predicted_flows.get(lane, 0.0)
                for lane in phase.incoming_lanes
            )
            scores[phase.phase_index] = self._profile_phase_pressure(
                phase,
                predicted_arrivals,
                profile,
            )
        viable = [
            phase
            for phase in green_phases
            if isfinite(scores[phase.phase_index])
        ]

        def duration_for(selected_pressure: float) -> float:
            finite_positive = [
                max(score, 0.0) for score in scores.values() if isfinite(score)
            ]
            average = (
                sum(finite_positive) / len(finite_positive)
                if finite_positive
                else 0.0
            )
            if selected_pressure <= 0 or average <= 0:
                duration = base_green
            else:
                duration = base_green * selected_pressure / average
            return float(min(max_green, max(min_green, duration)))

        def activate(target: int, duration: float, reason: str) -> tuple:
            return (
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
            )

        selection_reason = "highest_viable_pressure"
        decision_reason = ""
        actions: tuple = ()
        next_pending: int | None = None
        next_configured: int | None = None

        if not viable:
            return LegacyDecisionPlan(
                fingerprint=fingerprint,
                scores=tuple(sorted(scores.items())),
                current_phase=state.current_phase,
                elapsed_phase_time=state.elapsed_phase_time,
                legal_targets=self._legal_targets(state),
                candidate_phases=(),
                selected_phase=None,
                selection_reason="all_blocked",
                decision_reason="all_blocked",
                actions=(),
                cloud_plan=cloud_plan,
            )

        highest_score = max(scores[phase.phase_index] for phase in viable)
        tied = tuple(sorted(
            phase.phase_index
            for phase in viable
            if scores[phase.phase_index] == highest_score
        ))
        if len(tied) > 1:
            selection_reason = (
                "equal_score_keep_current"
                if state.current_phase in tied
                else "equal_score_smallest_index"
            )
            selected_phase = (
                state.current_phase
                if state.current_phase in tied
                else tied[0]
            )
        else:
            selected_phase = tied[0]
            selection_reason = (
                "current_phase_selected"
                if tied[0] == state.current_phase
                else "highest_viable_pressure"
            )
        selected = by_index[selected_phase]
        current = by_index.get(state.current_phase)

        if (
            self.pending_target_phase is not None
            and state.current_phase == self.pending_target_phase
        ):
            selected = by_index[self.pending_target_phase]
            selection_reason = "pending_target_reached"
            decision_reason = f"pending_target_reached target={selected.phase_index}"
            actions = activate(
                selected.phase_index,
                duration_for(scores.get(selected.phase_index, 0.0)),
                decision_reason,
            )
            next_pending = None
            next_configured = selected.phase_index
        elif self.pending_target_phase is not None and not self._is_green(current):
            if (
                not profile.delegation_mode
                and (
                    current is None
                    or state.elapsed_phase_time
                    < self._transition_duration(current)
                )
            ):
                actions = ()
                selection_reason = "wait_transition"
                decision_reason = "wait_transition"
            else:
                target = self.pending_target_phase
                selection_reason = "transition_complete"
                decision_reason = f"transition_complete target={target}"
                actions = activate(
                    target,
                    duration_for(scores.get(target, 0.0)),
                    decision_reason,
                )
                next_pending = None
                next_configured = target
        else:
            if (
                self._is_green(current)
                and state.elapsed_phase_time >= max_green
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
                    actions = ()
                    selection_reason = "hold_current"
                    decision_reason = "hold_current"
                    next_configured = state.current_phase
                else:
                    decision_reason = (
                        "dispatch_safety_executor"
                        if profile.delegation_mode
                        else f"max_pressure target={selected.phase_index}"
                    )
                    actions = activate(
                        selected.phase_index,
                        duration_for(scores[selected.phase_index]),
                        decision_reason,
                    )
                    next_pending = None
                    next_configured = selected.phase_index
            elif (
                not profile.delegation_mode
                and self._is_green(current)
                and state.elapsed_phase_time < min_green
            ):
                actions = ()
                selection_reason = "min_green_hold"
                decision_reason = "min_green_hold"
            else:
                transition = self._transition_after(
                    state.current_phase,
                    selected.phase_index,
                    phases,
                )
                if transition is None:
                    decision_reason = (
                        "dispatch_safety_executor"
                        if profile.delegation_mode
                        else f"direct_switch target={selected.phase_index}"
                    )
                    actions = activate(
                        selected.phase_index,
                        duration_for(scores[selected.phase_index]),
                        decision_reason,
                    )
                    next_pending = None
                    next_configured = selected.phase_index
                else:
                    if profile.delegation_mode:
                        # Clearance timing belongs to the safety executor:
                        # switch to the target directly, never wait in-phase.
                        next_pending = None
                        next_configured = selected.phase_index
                        decision_reason = "dispatch_safety_executor"
                        actions = activate(
                            selected.phase_index,
                            duration_for(scores[selected.phase_index]),
                            decision_reason,
                        )
                        return LegacyDecisionPlan(
                            fingerprint=fingerprint,
                            scores=tuple(sorted(scores.items())),
                            current_phase=state.current_phase,
                            elapsed_phase_time=state.elapsed_phase_time,
                            legal_targets=self._legal_targets(state),
                            candidate_phases=tuple(sorted(scores)),
                            selected_phase=selected.phase_index,
                            selection_reason=selection_reason,
                            decision_reason=decision_reason,
                            actions=actions,
                            cloud_plan=cloud_plan,
                            next_pending_target=next_pending,
                            next_configured_phase=next_configured,
                        )
                    next_pending = selected.phase_index
                    next_configured = None
                    selection_reason = "safe_transition"
                    decision_reason = (
                        f"safe_transition phase={transition.phase_index} "
                        f"target={selected.phase_index}"
                    )
                    transition_duration = self._transition_duration(transition)
                    actions = (
                        ControlAction(
                            tls_id=state.tls_id,
                            action_type="set_phase",
                            value=int(transition.phase_index),
                            reason=decision_reason,
                        ),
                        ControlAction(
                            tls_id=state.tls_id,
                            action_type="set_phase_duration",
                            value=float(transition_duration),
                            reason=f"transition_duration target={selected.phase_index}",
                        ),
                    )

        return LegacyDecisionPlan(
            fingerprint=fingerprint,
            scores=tuple(sorted(scores.items())),
            current_phase=state.current_phase,
            elapsed_phase_time=state.elapsed_phase_time,
            legal_targets=self._legal_targets(state),
            candidate_phases=tuple(sorted(scores)),
            selected_phase=selected.phase_index if viable else None,
            selection_reason=selection_reason,
            decision_reason=decision_reason,
            actions=actions,
            cloud_plan=cloud_plan,
            next_pending_target=next_pending,
            next_configured_phase=next_configured,
        )

    @staticmethod
    def _legal_targets(state: JointState) -> tuple[int, ...]:
        return tuple(
            target
            for source, target in getattr(state, "legal_phase_transitions", ())
            if source == state.current_phase
        )

    def _profile_phase_pressure(
        self,
        phase: PhaseTrafficState,
        predicted_arrivals: float,
        profile: _LegacyPlanningProfile,
    ) -> float:
        """Profile-parameterized pressure (pure; no self thresholds)."""
        if phase.outgoing_occupancy >= profile.overflow_threshold:
            return float("-inf")
        incoming = phase.incoming_queue / max(phase.incoming_capacity, 1.0)
        outgoing = phase.outgoing_queue / max(phase.outgoing_capacity, 1.0)
        prediction = profile.prediction_weight * (
            predicted_arrivals / max(phase.incoming_capacity, 1.0)
        )
        return incoming - outgoing + prediction

    def _validate_legacy_plan(self, plan: LegacyDecisionPlan) -> None:
        """Validate a legacy plan before any nested transition is applied."""
        if not isinstance(plan, LegacyDecisionPlan):
            raise RuntimeError("legacy_plan_invalid_type")

    def commit_plan(self, plan: LegacyDecisionPlan) -> None:
        """Commit the planned transition once, applying controller side effects."""
        self._validate_legacy_plan(plan)
        if plan is self._committed_legacy_plan:
            return
        if plan.cloud_plan is not None:
            self.cloud_policy.commit(plan.cloud_plan)
        self.pending_target_phase = plan.next_pending_target
        self._configured_phase = plan.next_configured_phase
        self._legacy_runtime_revision += 1
        self._committed_legacy_plan = plan
        self._pending_legacy_plan = None

    def reset(self) -> None:
        self.pending_target_phase = None
        self._configured_phase = None
        self.cloud_policy.reset()
        self._legacy_reset_epoch += 1
        self._legacy_runtime_revision = 0
        self._pending_legacy_plan = None
        self._committed_legacy_plan = None

    @property
    def name(self) -> str:
        return "ca_maxpressure"
