"""Shared validation for traffic-signal control actions."""

import math

from core.types import ControlAction


def validate_control_action(
    action: ControlAction,
    tls_id: str | None,
    *,
    phase_count: int | None = None,
    program_ids: set[str] | None = None,
) -> tuple[object | None, str | None]:
    """Return a normalized value or an explicit rejection reason."""
    if action.tls_id != tls_id:
        return None, f"unknown tls_id: {action.tls_id!r}"
    if action.action_type == "set_phase":
        if isinstance(action.value, bool) or not isinstance(action.value, int):
            return None, f"set_phase value must be an integer: {action.value!r}"
        if action.value < 0 or (
            phase_count is not None and action.value >= phase_count
        ):
            upper = phase_count - 1 if phase_count is not None else "unbounded"
            return (
                None,
                f"set_phase value out of range 0..{upper}: {action.value!r}",
            )
        return action.value, None
    if action.action_type == "set_phase_duration":
        try:
            duration = float(action.value)
        except (TypeError, ValueError):
            return (
                None,
                f"set_phase_duration value must be numeric: {action.value!r}",
            )
        if not math.isfinite(duration):
            return None, f"set_phase_duration value must be finite: {duration!r}"
        if duration <= 0:
            return None, f"set_phase_duration value must be positive: {duration!r}"
        return duration, None
    if action.action_type == "set_program":
        if action.value is None:
            return None, "set_program value must be non-empty"
        program = str(action.value).strip()
        if not program:
            return None, "set_program value must be non-empty"
        if program_ids is not None and program not in program_ids:
            return None, f"unknown signal program: {program!r}"
        return program, None
    return None, f"unknown action_type: {action.action_type!r}"
