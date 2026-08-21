"""Shared validation for traffic-signal control actions."""

import math
from collections.abc import Mapping

from core.types import ControlAction


def validate_phase_change_timing(
    action: ControlAction,
    *,
    current_phase: int,
    elapsed_phase_time: float,
    required_seconds: float,
    reason_code: str,
    requirement: str,
) -> tuple[str | None, str | None]:
    """Return a structured rejection when a phase clearance is incomplete."""
    if (
        action.action_type != "set_phase"
        or action.value == current_phase
        or elapsed_phase_time >= required_seconds
    ):
        return None, None
    return (
        reason_code,
        f"{requirement} requires {required_seconds:g} simulation seconds; "
        f"elapsed={elapsed_phase_time:g}",
    )


def validate_clearance_duration(
    action: ControlAction,
    *,
    elapsed_phase_time: float,
    required_seconds: float,
    reason_code: str,
    requirement: str,
) -> tuple[str | None, str | None]:
    """Reject a duration that would end yellow/all-red clearance too early."""
    if action.action_type != "set_phase_duration":
        return None, None
    try:
        duration = float(action.value)
    except (TypeError, ValueError):
        return None, None
    remaining = max(0.0, required_seconds - elapsed_phase_time)
    if duration >= remaining:
        return None, None
    return (
        reason_code,
        f"{requirement} requires {required_seconds:g} simulation seconds; "
        f"elapsed={elapsed_phase_time:g} remaining={remaining:g} "
        f"requested_duration={duration:g}",
    )


def validate_control_action(
    action: ControlAction,
    tls_id: str | None,
    *,
    phase_count: int | None = None,
    program_ids: set[str] | None = None,
    current_phase: int | None = None,
    allowed_phase_targets: set[int] | None = None,
) -> tuple[object | None, str | None, str | None]:
    """Return normalized value, structured reason code, and rejection detail."""
    if action.tls_id != tls_id:
        return None, "unknown_tls", f"unknown tls_id: {action.tls_id!r}"
    if action.action_type == "set_phase":
        if isinstance(action.value, bool) or not isinstance(action.value, int):
            return (
                None,
                "invalid_phase_type",
                f"set_phase value must be an integer: {action.value!r}",
            )
        if action.value < 0 or (
            phase_count is not None and action.value >= phase_count
        ):
            upper = phase_count - 1 if phase_count is not None else "unbounded"
            return (
                None,
                "phase_out_of_range",
                f"set_phase value out of range 0..{upper}: {action.value!r}",
            )
        if (
            phase_count is not None
            and current_phase is not None
            and action.value
            not in {current_phase, *(allowed_phase_targets or set())}
        ):
            return (
                None,
                "illegal_phase_transition",
                f"set_phase transition must be sequential: "
                f"{current_phase}->{action.value}",
            )
        return action.value, None, None
    if action.action_type == "set_phase_duration":
        try:
            duration = float(action.value)
        except (TypeError, ValueError):
            return (
                None,
                "invalid_duration_type",
                f"set_phase_duration value must be numeric: {action.value!r}",
            )
        if not math.isfinite(duration):
            return (
                None,
                "duration_not_finite",
                f"set_phase_duration value must be finite: {duration!r}",
            )
        if duration <= 0:
            return (
                None,
                "duration_not_positive",
                f"set_phase_duration value must be positive: {duration!r}",
            )
        return duration, None, None
    if action.action_type == "set_program":
        if isinstance(action.value, Mapping):
            return _validate_program_definition(action.value)
        if action.value is None:
            return None, "program_empty", "set_program value must be non-empty"
        program = str(action.value).strip()
        if not program:
            return None, "program_empty", "set_program value must be non-empty"
        if program_ids is not None and program not in program_ids:
            return None, "unknown_program", f"unknown signal program: {program!r}"
        return program, None, None
    return (
        None,
        "unknown_action_type",
        f"unknown action_type: {action.action_type!r}",
    )


def _validate_program_definition(
    payload: Mapping[object, object],
) -> tuple[object | None, str | None, str | None]:
    program_id = payload.get("program_id")
    if not isinstance(program_id, str) or not program_id.strip():
        return None, "program_empty", "set_program definition needs a program_id"
    phases = payload.get("phases")
    if not isinstance(phases, (list, tuple)) or not phases:
        return None, "program_phases_empty", "set_program definition needs phases"
    normalized_phases: list[dict[str, object]] = []
    state_length: int | None = None
    for phase in phases:
        if not isinstance(phase, Mapping):
            return None, "invalid_program_phase", "set_program phases must be mappings"
        try:
            duration = float(phase.get("duration"))
        except (TypeError, ValueError):
            return None, "invalid_program_duration", "set_program phase duration must be numeric"
        state = phase.get("state")
        if not math.isfinite(duration) or duration <= 0:
            return None, "invalid_program_duration", "set_program phase duration must be positive and finite"
        if not isinstance(state, str) or not state:
            return None, "invalid_program_state", "set_program phase state must be non-empty"
        if any(signal not in "rRgGyYoOu" for signal in state):
            return None, "invalid_program_state", "set_program phase state has an unsupported signal"
        if state_length is None:
            state_length = len(state)
        elif len(state) != state_length:
            return None, "invalid_program_state", "set_program phase states must have equal length"
        normalized_phases.append({"duration": duration, "state": state})
    return {
        "program_id": program_id.strip(),
        "phases": normalized_phases,
    }, None, None
