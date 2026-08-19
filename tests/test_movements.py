"""Movement-level traffic state contract tests."""

from dataclasses import asdict

import pytest
from pydantic import ValidationError

from api.models import MovementStateModel, PhaseMovementStateModel
from core.movements import MovementKey, MovementState, PhaseMovementState


def test_movement_key_is_immutable_and_serializable():
    key = MovementKey("in_0", "out_0")

    assert asdict(key) == {"incoming_lane": "in_0", "outgoing_lane": "out_0"}
    with pytest.raises(AttributeError):
        key.incoming_lane = "other"


def test_movement_rejects_zero_capacity():
    with pytest.raises(ValueError, match="incoming_capacity"):
        MovementState(MovementKey("in", "out"), 1, 0, 0, 1, 0, 1, 1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("downstream_occupancy", 1.01),
        ("saturation_rate", -0.1),
        ("turn_ratio", float("nan")),
    ],
)
def test_movement_rejects_invalid_measurements(field, value):
    values = {
        "queue_vehicles": 2.0,
        "downstream_queue_vehicles": 1.0,
        "incoming_capacity": 20.0,
        "downstream_capacity": 20.0,
        "downstream_occupancy": 0.1,
        "saturation_rate": 0.5,
        "turn_ratio": 1.0,
    }
    values[field] = value

    with pytest.raises(ValueError, match=field):
        MovementState(MovementKey("in", "out"), **values)


def test_phase_movement_rejects_negative_phase_index():
    with pytest.raises(ValueError, match="phase_index"):
        PhaseMovementState(-1, "Gr", (), 30.0)


def test_phase_movement_payload_round_trips_through_api_model():
    payload = PhaseMovementStateModel(
        phase_index=0,
        signal_state="Gr",
        nominal_duration=30.0,
        movements=[
            MovementStateModel(
                incoming_lane="in_0",
                outgoing_lane="out_0",
                queue_vehicles=2.0,
                downstream_queue_vehicles=1.0,
                incoming_capacity=20.0,
                downstream_capacity=20.0,
                downstream_occupancy=0.1,
                saturation_rate=0.5,
                turn_ratio=1.0,
            )
        ],
    )

    state = payload.to_domain()

    assert state.phase_index == 0
    assert state.movements[0].key == MovementKey("in_0", "out_0")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("incoming_capacity", 0.0),
        ("downstream_occupancy", 1.01),
        ("saturation_rate", -0.1),
    ],
)
def test_api_model_rejects_invalid_movement_measurements(field, value):
    values = {
        "incoming_lane": "in_0",
        "outgoing_lane": "out_0",
        "queue_vehicles": 2.0,
        "downstream_queue_vehicles": 1.0,
        "incoming_capacity": 20.0,
        "downstream_capacity": 20.0,
        "downstream_occupancy": 0.1,
        "saturation_rate": 0.5,
        "turn_ratio": 1.0,
    }
    values[field] = value

    with pytest.raises(ValidationError):
        MovementStateModel(**values)
