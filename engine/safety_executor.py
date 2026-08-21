"""Central safety boundary for traffic-signal action execution."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.movements import PhaseMovementState
from core.types import ActionResult, ControlAction, JointState
from engine.action_validation import (
    validate_clearance_duration,
    validate_control_action,
    validate_phase_change_timing,
)

if TYPE_CHECKING:
    from engine.traci_bridge import TraCIBridge


class SafetyExecutor:
    """Turn controller phase requests into legal signal writes."""

    def __init__(self, min_green_seconds: float = 10.0) -> None:
        normalized = float(min_green_seconds)
        if not math.isfinite(normalized) or normalized <= 0:
            raise ValueError("min_green_seconds must be positive and finite")
        self.min_green_seconds = normalized

    def apply(
        self,
        actions: Sequence[ControlAction],
        state: JointState,
        bridge: TraCIBridge,
    ) -> tuple[ActionResult, ...]:
        """Validate controller requests and write only actions that pass safety."""
        requested = tuple(actions)
        phases = tuple(state.phase_movements or state.phase_states)
        phase_count = (
            max(phase.phase_index for phase in phases) + 1 if phases else None
        )
        current = next(
            (phase for phase in phases if phase.phase_index == state.current_phase),
            None,
        )
        results: list[ActionResult | None] = [None] * len(requested)
        normalized: list[object | None] = [None] * len(requested)
        for index, action in enumerate(requested):
            value, reason_code, detail = validate_control_action(
                action,
                state.tls_id,
                phase_count=phase_count,
            )
            if detail is not None:
                results[index] = ActionResult(
                    action, False, detail, reason_code or ""
                )
                continue
            normalized[index] = value

        phase_duration_pairs = {
            index: index + 1
            for index, action in enumerate(requested[:-1])
            if action.action_type == "set_phase"
            and requested[index + 1].action_type == "set_phase_duration"
        }
        for phase_index, duration_index in phase_duration_pairs.items():
            if results[phase_index] is not None and results[duration_index] is None:
                results[duration_index] = ActionResult(
                    requested[duration_index],
                    False,
                    "phase duration fallback: requested phase change was rejected",
                    "phase_change_rejected",
                )
            elif results[duration_index] is not None and results[phase_index] is None:
                results[phase_index] = ActionResult(
                    requested[phase_index],
                    False,
                    "phase change fallback: requested duration was invalid",
                    "invalid_transition_duration",
                )

        if current is not None:
            timing = self._timing_requirement(current)
        else:
            timing = None
        for index, action in enumerate(requested):
            if results[index] is not None or action.action_type != "set_phase":
                continue
            target = int(normalized[index])
            if target == state.current_phase:
                results[index] = ActionResult(
                    action, True, "phase already active; no signal write"
                )
                continue
            if timing is not None:
                required_seconds, reason_code, requirement = timing
                reason_code, detail = validate_phase_change_timing(
                    action,
                    current_phase=state.current_phase,
                    elapsed_phase_time=state.elapsed_phase_time,
                    required_seconds=required_seconds,
                    reason_code=reason_code,
                    requirement=requirement,
                )
                if detail is not None:
                    results[index] = ActionResult(
                        action, False, detail, reason_code or ""
                    )
                    duration_index = phase_duration_pairs.get(index)
                    if (
                        duration_index is not None
                        and results[duration_index] is None
                    ):
                        results[duration_index] = ActionResult(
                            requested[duration_index],
                            False,
                            "phase duration fallback: phase clearance is incomplete",
                            "phase_change_rejected",
                        )

        if (
            current is not None
            and timing is not None
            and not any(signal in current.signal_state for signal in "Gg")
        ):
            required_seconds, clearance_reason_code, requirement = timing
            for index, action in enumerate(requested):
                if (
                    results[index] is not None
                    or action.action_type != "set_phase_duration"
                ):
                    continue
                rejection_code, detail = validate_clearance_duration(
                    action,
                    elapsed_phase_time=state.elapsed_phase_time,
                    required_seconds=required_seconds,
                    reason_code=clearance_reason_code,
                    requirement=requirement,
                )
                if detail is not None:
                    results[index] = ActionResult(
                        action, False, detail, rejection_code or ""
                    )

        effective_actions: list[ControlAction] = []
        execution_map: list[tuple[int | None, int | None, str | None]] = []
        consumed: set[int] = set()
        for index, action in enumerate(requested):
            if index in consumed or results[index] is not None:
                continue
            value = normalized[index]
            if action.action_type != "set_phase":
                effective_actions.append(
                    ControlAction(action.tls_id, action.action_type, value, action.reason)
                )
                execution_map.append((index, None, None))
                continue

            target = int(value)
            legal_targets = tuple(
                candidate
                for source, candidate in state.legal_phase_transitions
                if source == state.current_phase
            )
            if legal_targets:
                if target in legal_targets:
                    target_phase = next(
                        (
                            phase
                            for phase in phases
                            if phase.phase_index == target
                        ),
                        None,
                    )
                    transition = (
                        None
                        if target_phase is None
                        or any(
                            signal in target_phase.signal_state
                            for signal in "Gg"
                        )
                        else (
                            target_phase.phase_index,
                            float(target_phase.nominal_duration),
                        )
                    )
                else:
                    next_phase = next(
                        (
                            phase
                            for phase in phases
                            if phase.phase_index in legal_targets
                        ),
                        None,
                    )
                    transition = (
                        (next_phase.phase_index, float(next_phase.nominal_duration))
                        if next_phase is not None
                        else None
                    )
            else:
                transition = self.next_transition(
                    state.current_phase,
                    target,
                    phases,
                )
            effective_phase = target if transition is None else transition[0]
            effective_actions.append(
                ControlAction(
                    action.tls_id,
                    "set_phase",
                    effective_phase,
                    action.reason,
                )
            )
            phase_detail = (
                None
                if transition is None
                else f"applied safe transition phase={effective_phase} toward target={target}"
            )
            execution_map.append((index, None, phase_detail))

            duration_index = phase_duration_pairs.get(index)
            if duration_index is not None and results[duration_index] is None:
                duration_action = requested[duration_index]
                duration = (
                    float(normalized[duration_index])
                    if transition is None
                    else transition[1]
                )
                effective_actions.append(
                    ControlAction(
                        duration_action.tls_id,
                        "set_phase_duration",
                        duration,
                        duration_action.reason,
                    )
                )
                duration_detail = (
                    None
                    if transition is None
                    else (
                        f"applied {duration:g} simulation-second "
                        "safety interval"
                    )
                )
                execution_map.append((duration_index, index, duration_detail))
                consumed.add(duration_index)
            elif transition is not None:
                effective_actions.append(
                    ControlAction(
                        action.tls_id,
                        "set_phase_duration",
                        transition[1],
                        f"safety clearance toward target={target}",
                    )
                )
                execution_map.append((None, index, None))

        bridge_results = (
            tuple(bridge._apply_actions(effective_actions))
            if effective_actions
            else ()
        )
        for raw, (index, parent_index, accepted_detail) in zip(
            bridge_results, execution_map
        ):
            if index is None:
                if not raw.accepted and parent_index is not None:
                    results[parent_index] = ActionResult(
                        requested[parent_index],
                        False,
                        raw.detail,
                        raw.reason_code,
                    )
                continue
            results[index] = ActionResult(
                requested[index],
                raw.accepted,
                accepted_detail if raw.accepted and accepted_detail else raw.detail,
                raw.reason_code,
            )
        return tuple(result for result in results if result is not None)

    def _timing_requirement(
        self,
        phase: PhaseMovementState,
    ) -> tuple[float, str, str]:
        if any(signal in phase.signal_state for signal in "Gg"):
            return (
                self.min_green_seconds,
                "minimum_green_violation",
                "min_green",
            )
        if any(signal in phase.signal_state for signal in "Yy"):
            return (
                float(phase.nominal_duration),
                "yellow_clearance_violation",
                "yellow_clearance",
            )
        return (
            float(phase.nominal_duration),
            "all_red_clearance_violation",
            "all_red_clearance",
        )

    @staticmethod
    def fallback(state: JointState) -> list[ControlAction]:
        """Return the deterministic no-change action for a known signal phase."""
        phases = tuple(state.phase_movements or state.phase_states)
        if not any(
            phase.phase_index == state.current_phase for phase in phases
        ):
            return []
        return [
            ControlAction(
                state.tls_id,
                "set_phase",
                state.current_phase,
                "safety_fallback_preserve_current_phase",
            )
        ]

    @staticmethod
    def next_transition(
        current_phase: int,
        target_phase: int,
        phases: Sequence[PhaseMovementState],
    ) -> tuple[int, float] | None:
        """Return the next yellow/all-red phase before a requested green."""
        ordered = tuple(sorted(phases, key=lambda phase: phase.phase_index))
        positions = {phase.phase_index: index for index, phase in enumerate(ordered)}
        if (
            not ordered
            or current_phase not in positions
            or target_phase not in positions
            or current_phase == target_phase
        ):
            return None
        start = positions[current_phase]
        for offset in range(1, len(ordered)):
            candidate = ordered[(start + offset) % len(ordered)]
            if candidate.phase_index == target_phase:
                return None
            if any(signal in candidate.signal_state for signal in "Gg"):
                return None
            return candidate.phase_index, float(candidate.nominal_duration)
        return None
