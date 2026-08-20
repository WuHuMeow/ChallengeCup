import dataclasses

import pytest

from algorithms.capacity_aware_max_pressure import (
    CapacityAwareConfig,
    CapacityAwareMaxPressureAlgorithm,
)
from algorithms.classic_max_pressure import ClassicMaxPressureAlgorithm
from cloud.cloud_policy import CloudPolicy
from core.movements import MovementKey, MovementState, PhaseMovementState
from core.types import JointState


def _movement(
    incoming: str,
    outgoing: str,
    queue: float,
    downstream: float,
    incoming_capacity: float,
    downstream_capacity: float,
    occupancy: float = 0.0,
    service_rate: float = 1.0,
) -> MovementState:
    return MovementState(
        key=MovementKey(incoming, outgoing),
        queue_vehicles=queue,
        downstream_queue_vehicles=downstream,
        incoming_capacity=incoming_capacity,
        downstream_capacity=downstream_capacity,
        downstream_occupancy=occupancy,
        saturation_rate=service_rate,
        turn_ratio=1.0,
    )


@pytest.fixture
def state() -> JointState:
    return JointState(
        step=10,
        timestamp=10.0,
        tls_id="tls0",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=30.0,
        phase_movements=(
            PhaseMovementState(
                0,
                "Gr",
                (
                    _movement("in_a", "out_a", 8, 2, 20, 20),
                    _movement("in_b", "out_b", 2, 0, 20, 20),
                ),
                30,
            ),
            PhaseMovementState(
                1,
                "rG",
                (_movement("in_c", "out_c", 6, 1, 10, 10),),
                30,
            ),
        ),
        legal_phase_transitions=((0, 1),),
    )


def test_m0_matches_classic_without_capacity_spillback_or_prediction(state):
    """A change from raw classic movement pressure must break this comparison."""
    assert (
        CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m0()).score_breakdown(state)
        == ClassicMaxPressureAlgorithm().score_breakdown(state)
    )


def test_m1_prefers_lower_capacity_for_equal_queue(state):
    """Removing capacity normalization must select phase 0 instead of phase 1."""
    adjusted = dataclasses.replace(
        state,
        phase_movements=(
            dataclasses.replace(
                state.phase_movements[0],
                movements=(_movement("in_a", "out_a", 6, 0, 20, 20),),
            ),
            dataclasses.replace(
                state.phase_movements[1],
                movements=(_movement("in_c", "out_c", 6, 0, 10, 10),),
            ),
        ),
    )

    actions = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m1()).step(adjusted)

    assert actions[0].value == 1


def test_m2_blocks_only_movements_with_full_downstream_lane(state):
    """Dropping downstream gating would wrongly include in_a->out_a as service."""
    blocked = dataclasses.replace(
        state,
        phase_movements=(
            dataclasses.replace(
                state.phase_movements[0],
                movements=(
                    _movement("in_a", "out_a", 8, 2, 20, 20, occupancy=0.9),
                    _movement("in_b", "out_b", 2, 0, 20, 20),
                ),
            ),
            state.phase_movements[1],
        ),
    )

    scores = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m2()).score_breakdown(blocked)

    assert scores[0].blocked_movements == ("in_a->out_a",)
    assert scores[0].movement_ids == ("in_b->out_b",)
    assert scores[0].score == 0.1


def test_all_blocked_phases_keep_the_current_phase_as_safe_fallback(state):
    """Returning a blocked target would send an unsafe phase action."""
    full = dataclasses.replace(
        state,
        phase_movements=tuple(
            dataclasses.replace(
                phase,
                movements=tuple(
                    dataclasses.replace(movement, downstream_occupancy=0.9)
                    for movement in phase.movements
                ),
            )
            for phase in state.phase_movements
        ),
    )

    assert CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m2()).step(full) == []


def test_dynamic_green_is_clamped_to_the_frozen_layer_limits(state):
    """Ignoring config limits would emit a duration outside 10..30 seconds."""
    config = CapacityAwareConfig(True, True, False, 10.0, 30.0, 0.9)
    actions = CapacityAwareMaxPressureAlgorithm(config).step(state)

    duration = next(action.value for action in actions if action.action_type == "set_phase_duration")
    assert duration == 30.0


def test_m3_freezes_the_attributable_config_but_uses_legal_actions(state):
    """Bypassing the existing legal action path would emit a direct illegal action."""
    config = CapacityAwareConfig.m3()
    actions = CapacityAwareMaxPressureAlgorithm(config).step(state)

    assert config == CapacityAwareConfig.m3()
    assert [(action.action_type, action.value) for action in actions] == [
        ("set_phase", 1),
        ("set_phase_duration", 30.0),
    ]


def test_m4_prediction_is_disabled_by_default():
    """Enabling forecast pressure in the default configuration would invalidate M0-M3 attribution."""
    assert CapacityAwareConfig.default().prediction is False
    assert CapacityAwareConfig.m4().prediction is True


def test_manifest_records_prediction_units_and_frozen_layer_flags():
    """Omitting the horizon or flag would make an observed score impossible to attribute."""
    manifest = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3()).manifest

    assert manifest["prediction_enabled"] is False
    assert manifest["horizon_seconds"] == 300.0
    assert manifest["prediction_weight"] == 0.15
    assert manifest["capacity_normalization"] is True
    assert manifest["spillback_gate"] is True


def test_prediction_converts_hourly_flow_to_vehicles_over_the_horizon(state):
    """Using veh/h directly would produce 600 instead of the hand-derived 50 vehicles."""
    policy = CloudPolicy()
    policy.horizon = 300
    predicted = policy.predict(dataclasses.replace(state, flows={"in_a": 600.0}))

    assert predicted.predicted_flows == {"in_a": 50.0}


def test_prediction_keeps_ewma_history_in_hourly_flow_units(state):
    """Storing horizon vehicles as EWMA history would make the second 600 veh/h forecast 36.25."""
    policy = CloudPolicy()
    policy.horizon = 300
    hourly = dataclasses.replace(state, flows={"in_a": 600.0})

    policy.predict(hourly)
    predicted = policy.predict(hourly)

    assert predicted.predicted_flows == {"in_a": 50.0}
