"""EdgeChannel V2X message envelope, expiry and direction tests."""
import dataclasses

import pytest

from core.types import JointState, QueueState
from engine.edge_channel import EdgeChannel, EdgeMessage


def _state(step: int, directions=("north", "south")) -> JointState:
    return JointState(
        step=step, timestamp=float(step), tls_id="tls_0",
        current_phase=0, current_phase_name="p0", elapsed_phase_time=0.0,
        queues=[QueueState(direction=d, queue_length=1.0, waiting_time=0.0,
                           vehicle_count=1) for d in directions],
        flows={d: 100.0 for d in directions},
    )


def _message(step: int, directions=("north", "south"), expires_at: float = 30.0):
    return EdgeMessage(
        run_id="run-42",
        simulation_time=float(step),
        sent_at=float(step),
        expires_at=expires_at,
        payload_version="joint-state.v1",
        payload=_state(step, directions),
    )


def test_message_sent_at_simulation_time_10_with_delay_2_arrives_at_12():
    """Changing release timing from simulation time plus delay must fail this contract."""
    ch = EdgeChannel(delay_seconds=2.0)
    ch.send(_message(10))

    assert ch.receive(now=11.9) is None
    got = ch.receive(now=12.0)
    assert got is not None and got.payload.step == 10
    assert (got.run_id, got.simulation_time, got.sent_at, got.expires_at) == (
        "run-42", 10.0, 10.0, 30.0,
    )
    assert got.payload_version == "joint-state.v1"


def test_expired_message_is_dropped():
    """Delivering an expired cloud state would allow stale traffic control."""
    ch = EdgeChannel(delay_seconds=0.0)
    ch.send(_message(10, expires_at=11.0))

    assert ch.receive(now=11.0) is None
    assert [event.event_type for event in ch.events] == ["message_expired"]


def test_disallowed_direction_is_rejected_with_an_event_record():
    """Silently filtering a forbidden direction would hide a channel-contract violation."""
    ch = EdgeChannel(delay_seconds=0.0, allowed_directions=["north"])
    ch.send(_message(10, directions=("north", "south")))

    assert ch.receive(now=10.0) is None
    assert [(event.event_type, event.detail) for event in ch.events] == [
        ("message_rejected", "disallowed_direction=south"),
    ]


def test_stale_run_and_incompatible_payload_version_are_rejected():
    """A receiver must accept only its active run and supported payload schema."""
    ch = EdgeChannel(
        delay_seconds=0.0,
        expected_run_id="active-run",
        accepted_payload_versions=["joint-state.v1"],
    )
    ch.send(_message(10))
    ch.send(EdgeMessage(
        run_id="active-run",
        simulation_time=11.0,
        sent_at=11.0,
        expires_at=30.0,
        payload_version="joint-state.v2",
        payload=_state(11),
    ))

    assert ch.receive(now=11.0) is None
    assert ch.receive(now=11.0) is None
    assert [(event.event_type, event.detail) for event in ch.events] == [
        ("message_rejected", "stale_run_id=run-42"),
        ("message_rejected", "incompatible_payload_version=joint-state.v2"),
    ]


@pytest.mark.parametrize(
    ("message", "reason"),
    (
        (
            dataclasses.replace(_message(10), payload=_state(11)),
            "payload_timestamp_mismatch",
        ),
        (
            dataclasses.replace(_message(10), sent_at=11.0),
            "sent_at_after_simulation_time",
        ),
        (
            dataclasses.replace(_message(10), sent_at=9.0, expires_at=9.0),
            "expires_at_not_after_sent_at",
        ),
        (
            dataclasses.replace(_message(10), sent_at=9.0, expires_at=10.0),
            "expires_at_not_after_simulation_time",
        ),
    ),
)
def test_inconsistent_message_times_are_rejected_before_buffering(message, reason):
    """Malformed timing envelopes must never become eligible for delivery."""
    channel = EdgeChannel(delay_seconds=0.0)

    channel.send(message)

    assert channel.receive(now=100.0) is None
    assert [(event.event_type, event.detail) for event in channel.events] == [
        ("message_rejected", reason),
    ]
