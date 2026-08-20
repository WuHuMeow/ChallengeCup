"""Shared validation for traffic-signal control actions."""

import math

from core.types import ControlAction


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
