"""Central safety boundary for traffic-signal action execution."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from core.movements import PhaseMovementState
from core.types import ActionResult, ControlAction, JointState
from engine.action_validation import (
    validate_action_window,
    validate_clearance_duration,
    validate_control_action,
    validate_phase_change_timing,
)

if TYPE_CHECKING:
    from engine.traci_bridge import TraCIBridge


class SafetyExecutor:
    """Turn controller phase requests into legal signal writes."""

    def __init__(
        self,
        min_green_seconds: float | Callable[[], float] = 10.0,
    ) -> None:
        if callable(min_green_seconds):
            self._min_green_provider = min_green_seconds
        else:
            normalized = self._validate_min_green(min_green_seconds)
            self._min_green_provider = lambda: normalized
        self.min_green_seconds

    @property
    def min_green_seconds(self) -> float:
        return self._validate_min_green(self._min_green_provider())

    @staticmethod
    def _validate_min_green(value: object) -> float:
        normalized = float(value)
        if not math.isfinite(normalized) or normalized <= 0:
            raise ValueError("min_green_seconds must be positive and finite")
        return normalized

    def apply(
        self,
        actions: Sequence[ControlAction],
        state: JointState,
        bridge: TraCIBridge,
    ) -> tuple[ActionResult, ...]:
        """Validate controller requests and write only actions that pass safety."""
        requested = tuple(actions)
        min_green_seconds = self.min_green_seconds
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
            reason_code, detail = validate_action_window(
                action,
                float(state.timestamp),
            )
            if detail is not None:
                fallback = self.fallback(state)
                fallback_name = (
                    "preserve_current_phase"
                    if fallback
                    else "fixed_timing_unchanged"
                )
                results[index] = ActionResult(
                    action,
                    False,
                    f"{detail}; fallback={fallback_name}",
                    reason_code or "",
                )
                continue
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
            if action.action_type == "set_program" and (
                not isinstance(value, dict)
                or state.step != 0
                or float(state.timestamp) != 0.0
                or float(state.elapsed_phase_time) != 0.0
            ):
                results[index] = ActionResult(
                    action,
                    False,
                    "program changes are restricted to validated simulation startup",
                    "unsafe_program_switch",
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
            timing = self._timing_requirement(current, min_green_seconds)
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

        if current is not None and timing is not None:
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

        for phase_index, duration_index in phase_duration_pairs.items():
            if results[phase_index] is not None or results[duration_index] is not None:
                continue
            target = int(normalized[phase_index])
            target_phase = next(
                (phase for phase in phases if phase.phase_index == target),
                None,
            )
            if target_phase is None or not any(
                signal in target_phase.signal_state for signal in "Gg"
            ):
                continue
            rejection_code, detail = validate_clearance_duration(
                requested[duration_index],
                elapsed_phase_time=0.0,
                required_seconds=min_green_seconds,
                reason_code="minimum_green_violation",
                requirement="min_green",
            )
            if detail is not None:
                results[duration_index] = ActionResult(
                    requested[duration_index],
                    False,
                    detail,
                    rejection_code or "",
                )
                results[phase_index] = ActionResult(
                    requested[phase_index],
                    False,
                    "phase change fallback: requested green duration is unsafe",
                    "invalid_transition_duration",
                )

        for index, action in enumerate(requested):
            if (
                results[index] is not None
                or action.action_type != "set_phase"
                or index in phase_duration_pairs
            ):
                continue
            target = int(normalized[index])
            if target == state.current_phase:
                continue
            target_phase = next(
                (phase for phase in phases if phase.phase_index == target),
                None,
            )
            if (
                target_phase is not None
                and any(signal in target_phase.signal_state for signal in "Gg")
                and float(target_phase.nominal_duration) < min_green_seconds
            ):
                results[index] = ActionResult(
                    action,
                    False,
                    f"target min_green requires {min_green_seconds:g} "
                    "simulation seconds; "
                    f"nominal_duration={float(target_phase.nominal_duration):g}",
                    "minimum_green_violation",
                )

        for phase_index, duration_index in phase_duration_pairs.items():
            if results[phase_index] is not None or results[duration_index] is not None:
                continue
            target = int(normalized[phase_index])
            target_phase = next(
                (phase for phase in phases if phase.phase_index == target),
                None,
            )
            if target_phase is None or any(
                signal in target_phase.signal_state for signal in "Gg"
            ):
                continue
            requested_duration = float(normalized[duration_index])
            nominal_duration = float(target_phase.nominal_duration)
            if requested_duration < nominal_duration:
                results[duration_index] = ActionResult(
                    requested[duration_index],
                    False,
                    f"unsafe clearance duration requested={requested_duration:g}; "
                    f"nominal_duration={nominal_duration:g}; "
                    "applied internal nominal fallback",
                    "clearance_duration_corrected",
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
                    ControlAction(
                        action.tls_id,
                        action.action_type,
                        value,
                        action.reason,
                        issued_at=action.issued_at,
                        expires_at=action.expires_at,
                    )
                )
                execution_map.append((index, None, None))
                continue

            target = int(value)
            target_phase = next(
                (phase for phase in phases if phase.phase_index == target),
                None,
            )
            current_is_green = current is not None and any(
                signal in current.signal_state for signal in "Gg"
            )
            target_is_green = target_phase is not None and any(
                signal in target_phase.signal_state for signal in "Gg"
            )
            legal_targets = tuple(
                candidate
                for source, candidate in state.legal_phase_transitions
                if source == state.current_phase
            )
            if legal_targets:
                if current_is_green and target_is_green:
                    next_phase = next(
                        (
                            phase
                            for phase in phases
                            if phase.phase_index in legal_targets
                            and not any(
                                signal in phase.signal_state for signal in "Gg"
                            )
                            and self._phase_is_reachable(
                                phase.phase_index,
                                target,
                                state.legal_phase_transitions,
                            )
                        ),
                        None,
                    )
                    transition = (
                        (next_phase.phase_index, float(next_phase.nominal_duration))
                        if next_phase is not None
                        else None
                    )
                    if transition is None:
                        results[index] = ActionResult(
                            action,
                            False,
                            f"green transition {state.current_phase}->{target} "
                            "has no yellow/all-red clearance path",
                            "clearance_path_unavailable",
                        )
                        duration_index = phase_duration_pairs.get(index)
                        if duration_index is not None:
                            results[duration_index] = ActionResult(
                                requested[duration_index],
                                False,
                                "phase duration fallback: clearance path is unavailable",
                                "phase_change_rejected",
                            )
                        continue
                elif target in legal_targets:
                    transition = (
                        None
                        if target_phase is None or target_is_green
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
                            and self._phase_is_reachable(
                                phase.phase_index,
                                target,
                                state.legal_phase_transitions,
                            )
                        ),
                        None,
                    )
                    transition = (
                        (next_phase.phase_index, float(next_phase.nominal_duration))
                        if next_phase is not None
                        else None
                    )
                    if transition is None:
                        results[index] = ActionResult(
                            action,
                            False,
                            f"set_phase transition is not reachable: "
                            f"{state.current_phase}->{target}",
                            "illegal_phase_transition",
                        )
                        duration_index = phase_duration_pairs.get(index)
                        if duration_index is not None:
                            results[duration_index] = ActionResult(
                                requested[duration_index],
                                False,
                                "phase duration fallback: requested phase is unreachable",
                                "phase_change_rejected",
                            )
                        continue
            else:
                transition = self.next_transition(
                    state.current_phase,
                    target,
                    phases,
                )
                if current_is_green and target_is_green and transition is None:
                    results[index] = ActionResult(
                        action,
                        False,
                        f"green transition {state.current_phase}->{target} "
                        "has no yellow/all-red clearance path",
                        "clearance_path_unavailable",
                    )
                    duration_index = phase_duration_pairs.get(index)
                    if duration_index is not None:
                        results[duration_index] = ActionResult(
                            requested[duration_index],
                            False,
                            "phase duration fallback: clearance path is unavailable",
                            "phase_change_rejected",
                        )
                    continue
            if transition is not None:
                transition_phase = next(
                    (
                        phase
                        for phase in phases
                        if phase.phase_index == transition[0]
                    ),
                    None,
                )
                if (
                    transition_phase is not None
                    and any(
                        signal in transition_phase.signal_state
                        for signal in "Gg"
                    )
                    and float(transition_phase.nominal_duration)
                    < min_green_seconds
                ):
                    results[index] = ActionResult(
                        action,
                        False,
                        f"intermediate min_green requires {min_green_seconds:g} "
                        "simulation seconds; "
                        f"phase={transition_phase.phase_index} "
                        f"nominal_duration={float(transition_phase.nominal_duration):g}",
                        "minimum_green_violation",
                    )
                    duration_index = phase_duration_pairs.get(index)
                    if duration_index is not None:
                        results[duration_index] = ActionResult(
                            requested[duration_index],
                            False,
                            "phase duration fallback: intermediate green is unsafe",
                            "phase_change_rejected",
                        )
                    continue
            effective_phase = target if transition is None else transition[0]
            effective_actions.append(
                ControlAction(
                    action.tls_id,
                    "set_phase",
                    effective_phase,
                    action.reason,
                    issued_at=action.issued_at,
                    expires_at=action.expires_at,
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
                        issued_at=duration_action.issued_at,
                        expires_at=duration_action.expires_at,
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
                        issued_at=action.issued_at,
                        expires_at=action.expires_at,
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
        min_green_seconds: float,
    ) -> tuple[float, str, str]:
        if any(signal in phase.signal_state for signal in "Gg"):
            return (
                min_green_seconds,
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
            ControlAction.for_simulation_time(
                state.tls_id,
                "set_phase",
                state.current_phase,
                "safety_fallback_preserve_current_phase",
                state.timestamp,
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

    @staticmethod
    def _phase_is_reachable(
        source_phase: int,
        target_phase: int,
        transitions: Sequence[tuple[int, int]],
    ) -> bool:
        if source_phase == target_phase:
            return True
        adjacency: dict[int, list[int]] = {}
        for source, target in transitions:
            adjacency.setdefault(source, []).append(target)
        pending = list(adjacency.get(source_phase, ()))
        visited = {source_phase}
        while pending:
            candidate = pending.pop(0)
            if candidate == target_phase:
                return True
            if candidate in visited:
                continue
            visited.add(candidate)
            pending.extend(adjacency.get(candidate, ()))
        return False
