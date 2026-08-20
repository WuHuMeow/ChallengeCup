"""EdgeChannel V2X message envelope, expiry and direction tests."""
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
