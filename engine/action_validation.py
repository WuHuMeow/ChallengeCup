"""Shared validation for traffic-signal control actions."""

import math

from core.types import ControlAction


def _fmt(value: float) -> str:
    """Format one simulation-second value the way rejection details read."""
    return f"{float(value):g}"


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
        raw = action.value
        if isinstance(raw, dict):
            # Structured programs carry their own provenance and are
            # safety-validated by the executor's program branch.
            return (raw if raw else None), (
                None if raw else "set_program value must be non-empty"
            )
        program = str(raw).strip()
        if not program:
            return None, "set_program value must be non-empty"
        if program_ids is not None and program not in program_ids:
            return None, f"unknown signal program: {program!r}"
        return program, None
    return None, f"unknown action_type: {action.action_type!r}"


def validate_phase_change_timing(
    action: ControlAction,
    *,
    current_phase: int,
    elapsed_phase_time: float,
    required_seconds: float,
    reason_code: str,
    requirement: str,
) -> tuple[str | None, str | None]:
    """Reject a phase change before its required minimum has elapsed.

    A no-op on the current phase is always allowed. The boundary itself
    (elapsed == required) is accepted.
    """
    if action.action_type == "set_phase" and action.value == current_phase:
        return None, None
    if float(elapsed_phase_time) < float(required_seconds):
        return (
            reason_code,
            f"{requirement} requires {_fmt(required_seconds)} simulation "
            f"seconds; elapsed={_fmt(elapsed_phase_time)}",
        )
    return None, None


def validate_clearance_duration(
    action: ControlAction,
    *,
    elapsed_phase_time: float,
    required_seconds: float,
    reason_code: str,
    requirement: str,
) -> tuple[str | None, str | None]:
    """Reject a phase-duration extension shorter than the clearance need."""
    remaining = float(required_seconds) - float(elapsed_phase_time)
    try:
        requested = float(action.value)
    except (TypeError, ValueError):
        requested = float("nan")
    if remaining > 0 and (not math.isfinite(requested) or requested < remaining):
        return (
            reason_code,
            f"{requirement} requires {_fmt(required_seconds)} simulation "
            f"seconds; elapsed={_fmt(elapsed_phase_time)} "
            f"remaining={_fmt(remaining)} requested_duration={_fmt(requested)}",
        )
    return None, None


def validate_action_window(
    action: ControlAction,
    current_simulation_seconds: float,
) -> tuple[str | None, str | None]:
    """Reject actions whose expiry has passed; no window stays compatible."""
    expires_at = action.expires_at
    if expires_at is None:
        return None, None
    if float(current_simulation_seconds) >= float(expires_at):
        issued = action.issued_at
        return (
            "stale_action",
            f"action expired at simulation_seconds={_fmt(expires_at)}; "
            f"current={_fmt(current_simulation_seconds)} "
            f"issued={_fmt(issued) if issued is not None else 'unknown'}",
        )
    return None, None


def validate_plan_program_safety(program: dict) -> tuple[str | None, str | None]:
    """Reject a startup signal program that cannot safely serve traffic."""
    phases = program.get("phases") or []
    if not phases:
        return "unsafe_startup_program", "program has no phases"
    widths: set[int] = set()
    has_service_green = False
    for index, phase in enumerate(phases):
        try:
            duration = float(phase.get("duration"))
        except (TypeError, ValueError):
            duration = float("nan")
        state = str(phase.get("state", ""))
        widths.add(len(state))
        if not math.isfinite(duration) or duration <= 0:
            return (
                "unsafe_startup_program",
                f"phase {index} has invalid duration={phase.get('duration')!r}",
            )
        if any(signal in state for signal in "Gg"):
            has_service_green = True
    if len(widths) > 1:
        return (
            "unsafe_startup_program",
            f"phase state widths are inconsistent: {sorted(widths)}",
        )
    if not has_service_green:
        return (
            "unsafe_startup_program",
            "program has no service green in any phase",
        )
    return None, None


def validate_startup_program_safety(
    program: dict,
    *,
    min_green_seconds: float = 10.0,
    yellow_seconds: float = 3.0,
    all_red_seconds: float = 1.0,
) -> tuple[str | None, str | None]:
    """Strict per-signal clearance validation for algorithm-authored programs.

    Unlike plan-derived official baselines (validated structurally by
    ``validate_plan_program_safety``), an algorithm-authored cycle must give
    every service green at least ``min_green_seconds``, clear each green-out
    with a yellow on the same signal lasting ``yellow_seconds``, and follow it
    with an all-red interval of ``all_red_seconds``.
    """
    structural_reason, structural_detail = validate_plan_program_safety(program)
    if structural_reason is not None:
        return structural_reason, structural_detail

    phases = program.get("phases") or []
    violations: list[str] = []
    previous_greens: set[int] = set()
    for index, phase in enumerate(phases):
        state = str(phase.get("state", ""))
        try:
            duration = float(phase.get("duration"))
        except (TypeError, ValueError):
            duration = float("nan")
        greens = {i for i, signal in enumerate(state) if signal in "Gg"}
        yellows = {i for i, signal in enumerate(state) if signal in "yY"}

        if greens and duration < min_green_seconds:
            violations.append(
                f"service green duration={duration:g} shorter than "
                f"min_green={min_green_seconds:g}"
            )
        if index > 0:
            if greens and previous_greens:
                violations.append(
                    f"direct green-to-green between phases {index - 1}->{index}"
                )
            for signal in sorted(previous_greens - greens):
                if signal not in yellows:
                    violations.append(
                        f"missing yellow clearance for signal_index={signal}"
                    )
                elif duration < yellow_seconds:
                    violations.append(
                        f"yellow clearance={duration:g} requires "
                        f"{yellow_seconds:g}"
                    )
                else:
                    if index + 1 >= len(phases):
                        violations.append(
                            f"missing all-red clearance for signal_index={signal}"
                        )
                        continue
                    next_phase = phases[index + 1]
                    next_state = str(next_phase.get("state", ""))
                    try:
                        next_duration = float(next_phase.get("duration"))
                    except (TypeError, ValueError):
                        next_duration = float("nan")
                    if any(signal_char in "GgyY" for signal_char in next_state):
                        violations.append(
                            f"missing all-red clearance for signal_index={signal}"
                        )
                    elif next_duration < all_red_seconds:
                        violations.append(
                            f"all-red clearance={next_duration:g} requires "
                            f"{all_red_seconds:g}"
                        )
            for signal in sorted(yellows - previous_greens - greens):
                if previous_greens:
                    violations.append(
                        f"yellow on unrelated signal_index={signal}"
                    )
        previous_greens = greens

    if violations:
        return "unsafe_startup_program", "; ".join(violations)
    return None, None
