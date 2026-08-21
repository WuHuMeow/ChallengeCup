import pytest

from core.types import ControlAction
from engine import action_validation


@pytest.mark.parametrize(
    ("reason_code", "requirement"),
    [
        ("minimum_green_violation", "min_green"),
        ("yellow_clearance_violation", "yellow_clearance"),
        ("all_red_clearance_violation", "all_red_clearance"),
    ],
)
def test_phase_change_timing_rejects_before_required_simulation_seconds(
    reason_code,
    requirement,
):
    action = ControlAction("tls", "set_phase", 2)

    result = action_validation.validate_phase_change_timing(
        action,
        current_phase=0,
        elapsed_phase_time=2.5,
        required_seconds=3.0,
        reason_code=reason_code,
        requirement=requirement,
    )

    assert result == (
        reason_code,
        f"{requirement} requires 3 simulation seconds; elapsed=2.5",
    )


def test_phase_change_timing_accepts_at_the_exact_simulation_second_boundary():
    result = action_validation.validate_phase_change_timing(
        ControlAction("tls", "set_phase", 2),
        current_phase=0,
        elapsed_phase_time=3.0,
        required_seconds=3.0,
        reason_code="yellow_clearance_violation",
        requirement="yellow_clearance",
    )

    assert result == (None, None)


def test_phase_change_timing_does_not_reject_a_current_phase_noop():
    result = action_validation.validate_phase_change_timing(
        ControlAction("tls", "set_phase", 0),
        current_phase=0,
        elapsed_phase_time=0.0,
        required_seconds=10.0,
        reason_code="minimum_green_violation",
        requirement="min_green",
    )

    assert result == (None, None)


def test_clearance_duration_rejects_less_than_the_remaining_simulation_seconds():
    result = action_validation.validate_clearance_duration(
        ControlAction("tls", "set_phase_duration", 0.1),
        elapsed_phase_time=2.5,
        required_seconds=3.0,
        reason_code="yellow_clearance_violation",
        requirement="yellow_clearance",
    )

    assert result == (
        "yellow_clearance_violation",
        "yellow_clearance requires 3 simulation seconds; "
        "elapsed=2.5 remaining=0.5 requested_duration=0.1",
    )


def test_action_window_rejects_a_stale_action_at_simulation_time():
    action = ControlAction(
        "tls",
        "set_phase",
        2,
        issued_at=4.0,
        expires_at=5.0,
    )

    result = action_validation.validate_action_window(action, 5.1)

    assert result == (
        "stale_action",
        "action expired at simulation_seconds=5; current=5.1 issued=4",
    )


def test_action_without_a_window_remains_backward_compatible():
    assert action_validation.validate_action_window(
        ControlAction("tls", "set_phase", 2),
        100.0,
    ) == (None, None)


def test_action_is_stale_at_its_exact_expiry_boundary():
    action = ControlAction(
        "tls",
        "set_phase",
        2,
        issued_at=4.0,
        expires_at=5.0,
    )

    assert action_validation.validate_action_window(action, 5.0)[0] == "stale_action"
