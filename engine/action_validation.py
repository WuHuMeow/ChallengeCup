"""Shared validation for traffic-signal control actions."""

import math
from collections.abc import Mapping

from core.types import ControlAction


def validate_action_window(
    action: ControlAction,
    simulation_seconds: float,
) -> tuple[str | None, str | None]:
    """Validate optional action issue/expiry metadata in simulation seconds."""
    if action.issued_at is None and action.expires_at is None:
        return None, None
    if action.issued_at is None or action.expires_at is None:
        return (
            "invalid_action_window",
            "action validity requires both issued_at and expires_at",
        )
    try:
        issued_at = float(action.issued_at)
        expires_at = float(action.expires_at)
        current = float(simulation_seconds)
    except (TypeError, ValueError):
        return "invalid_action_window", "action validity must be numeric"
    if not all(math.isfinite(value) for value in (issued_at, expires_at, current)):
        return "invalid_action_window", "action validity must be finite"
    if issued_at < 0 or expires_at < issued_at:
        return (
            "invalid_action_window",
            f"invalid action window issued={issued_at:g} expires={expires_at:g}",
        )
    if current < issued_at:
        return (
            "action_not_yet_valid",
            f"action issued at simulation_seconds={issued_at:g}; current={current:g}",
        )
    if current >= expires_at:
        return (
            "stale_action",
            f"action expired at simulation_seconds={expires_at:g}; "
            f"current={current:g} issued={issued_at:g}",
        )
    return None, None


def validate_startup_program_safety(
    program: Mapping[str, object],
    *,
    min_green_seconds: float,
    yellow_seconds: float,
    all_red_seconds: float,
) -> tuple[str | None, str | None]:
    """Validate one normalized fixed-time program against the safety policy."""
    phases = program["phases"]
    service_greens = [
        index
        for index, phase in enumerate(phases)
        if any(signal in phase["state"] for signal in "Gg")
        and not any(signal in phase["state"] for signal in "Yy")
    ]
    if not service_greens:
        return "unsafe_startup_program", "startup program has no service green phase"

    for index in service_greens:
        duration = float(phases[index]["duration"])
        if duration < min_green_seconds:
            return (
                "unsafe_startup_program",
                f"startup program phase={index} green duration={duration:g} "
                f"requires min_green={min_green_seconds:g}",
            )

    phase_count = len(phases)
    for position, green_index in enumerate(service_greens):
        next_green = service_greens[(position + 1) % len(service_greens)]
        clearance: list[int] = []
        cursor = (green_index + 1) % phase_count
        while cursor != next_green:
            clearance.append(cursor)
            cursor = (cursor + 1) % phase_count
        if not clearance:
            return (
                "unsafe_startup_program",
                f"startup program has direct green-to-green transition "
                f"phase={green_index}->{next_green}",
            )

        yellow_duration = 0.0
        all_red_duration = 0.0
        all_red_started = False
        for index in clearance:
            phase = phases[index]
            state = phase["state"]
            duration = float(phase["duration"])
            if any(signal in state for signal in "Yy"):
                if all_red_started:
                    return (
                        "unsafe_startup_program",
                        f"startup program phase={green_index}->{next_green} "
                        "has yellow after all-red clearance",
                    )
                yellow_duration += duration
            elif all(signal in "rR" for signal in state):
                all_red_started = True
                all_red_duration += duration
            else:
                return (
                    "unsafe_startup_program",
                    f"startup program phase={index} is not yellow or all-red "
                    f"clearance before green phase={next_green}",
                )

        if yellow_duration == 0.0:
            return (
                "unsafe_startup_program",
                f"startup program phase={green_index}->{next_green} "
                f"is missing yellow clearance; requires {yellow_seconds:g} "
                "simulation seconds",
            )
        if yellow_duration < yellow_seconds:
            return (
                "unsafe_startup_program",
                f"startup program phase={green_index}->{next_green} yellow "
                f"clearance={yellow_duration:g} requires {yellow_seconds:g} "
                "simulation seconds",
            )
        if all_red_duration == 0.0:
            return (
                "unsafe_startup_program",
                f"startup program phase={green_index}->{next_green} "
                f"is missing all-red clearance; requires {all_red_seconds:g} "
                "simulation seconds",
            )
        if all_red_duration < all_red_seconds:
            return (
                "unsafe_startup_program",
                f"startup program phase={green_index}->{next_green} all-red "
                f"clearance={all_red_duration:g} requires {all_red_seconds:g} "
                "simulation seconds",
            )
    return None, None


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
