import dataclasses
import json

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


def test_dynamic_green_averages_only_strictly_positive_phase_scores(state):
    """A zero-score candidate must not dilute a 20-point selected pressure."""
    scored = {
        0: type("Score", (), {"score": 20.0})(),
        1: type("Score", (), {"score": 0.0})(),
        2: type("Score", (), {"score": -5.0})(),
    }
    algorithm = CapacityAwareMaxPressureAlgorithm(
        CapacityAwareConfig(True, True, False, 10.0, 90.0, 0.9),
        base_green=30.0,
    )

    assert algorithm._duration(20.0, scored) == 30.0


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


def test_m2_m3_have_distinct_boundary_identity_and_serializable_audit(state):
    """Evidence consumers need the layer boundary and the complete selected decision."""
    m2 = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m2())
    m3 = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3())

    m2_audit = m2.audit_record(state)
    m3_audit = m3.audit_record(state)

    assert m2.manifest["layer"] == "M2"
    assert m3.manifest["layer"] == "M3"
    assert m2.manifest["safety_boundary"] != m3.manifest["safety_boundary"]
    assert m3_audit["selection_reason"] == "highest_viable_pressure"
    assert m3_audit["final_decision"]["action"] == "set_phase"
    assert m3_audit["phase_scores"]["0"]["movements"][0]["movement_id"] == "in_a->out_a"
    assert m2_audit["phase_scores"]["0"]["movements"][0]["blocked_reason"] is None
    assert json.loads(json.dumps(m3_audit))["layer"] == "M3"


def test_m4_audit_reuses_one_prediction_snapshot_and_sums_all_components(state):
    """Audit must describe the executed EWMA score, not a second updated forecast."""
    policy = CloudPolicy()
    policy.alpha = 0.5
    policy.horizon = 3600
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4(), policy)
    low_flow = dataclasses.replace(state, step=9, flows={"in_c": 0.0})
    high_flow = dataclasses.replace(state, step=10, flows={"in_c": 600.0})

    algorithm.step(low_flow)
    actions = algorithm.step(high_flow)
    audit = algorithm.audit_record(high_flow)

    movement = audit["phase_scores"]["1"]["movements"][0]
    assert actions[0].value == 1
    assert policy._prev_hourly_flow["in_c"] == 300.0
    assert movement["prediction_pressure"] == pytest.approx(4.5)
    assert movement["pressure"] == pytest.approx(
        movement["normalized_pressure"] + movement["prediction_pressure"]
    )
    assert audit["phase_scores"]["1"]["score"] == pytest.approx(
        sum(component["pressure"] for component in audit["phase_scores"]["1"]["movements"])
    )


@pytest.mark.parametrize(
    ("min_green", "max_green", "threshold", "message"),
    (
        (float("nan"), 30.0, 0.9, "min_green"),
        (float("inf"), 30.0, 0.9, "min_green"),
        (-float("inf"), 30.0, 0.9, "min_green"),
        (0.0, 30.0, 0.9, "min_green"),
        (-1.0, 30.0, 0.9, "min_green"),
        (10.0, float("nan"), 0.9, "max_green"),
        (10.0, float("inf"), 0.9, "max_green"),
        (10.0, 0.0, 0.9, "max_green"),
        (31.0, 30.0, 0.9, "min_green"),
        (10.0, 30.0, float("nan"), "overflow_threshold"),
        (10.0, 30.0, float("inf"), "overflow_threshold"),
        (10.0, 30.0, -float("inf"), "overflow_threshold"),
        (10.0, 30.0, -0.01, "overflow_threshold"),
        (10.0, 30.0, 1.01, "overflow_threshold"),
    ),
)
def test_capacity_config_rejects_nonfinite_and_unsafe_limits(
    min_green, max_green, threshold, message
):
    """Controller config must be valid before it can influence live movement scoring."""
    with pytest.raises(ValueError, match=message):
        CapacityAwareConfig(True, True, False, min_green, max_green, threshold)


@pytest.mark.parametrize(
    "kwargs",
    (
        {"overflow_occupancy_threshold": float("nan")},
        {"overflow_occupancy_threshold": 1.01},
        {"prediction_weight": float("inf")},
        {"prediction_weight": -0.1},
        {"base_green": float("nan")},
        {"base_green": 0.0},
    ),
)
def test_capacity_constructor_overrides_cannot_restore_unsafe_values(kwargs):
    """Override paths must honor the same finite, safe controller contract."""
    with pytest.raises(ValueError):
        CapacityAwareMaxPressureAlgorithm(**kwargs)


def test_audit_explains_equal_score_keep_current_tie(state):
    """Current phase wins a tied pressure score by the frozen deterministic rule."""
    tied = dataclasses.replace(
        state,
        phase_movements=(
            state.phase_movements[0],
            dataclasses.replace(
                state.phase_movements[1],
                movements=(_movement("in_c", "out_c", 5, 1, 10, 10),),
            ),
        ),
    )

    audit = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3()).audit_record(tied)

    assert audit["selection_reason"] == "equal_score_keep_current"
    assert audit["current_phase"] == 0
    assert audit["elapsed_phase_time"] == 30.0
    assert audit["legal_targets"] == [1]
    assert audit["candidate_phases"] == [0, 1]
    assert audit["selected_phase"] == 0


def test_audit_explains_equal_score_smallest_index_tie(state):
    """Without a tied current phase, the smallest viable phase index wins."""
    tied = dataclasses.replace(
        state,
        current_phase=2,
        current_phase_name="p2",
        phase_movements=(
            state.phase_movements[0],
            dataclasses.replace(
                state.phase_movements[1],
                movements=(_movement("in_c", "out_c", 5, 1, 10, 10),),
            ),
            PhaseMovementState(
                2, "G", (_movement("in_d", "out_d", 1, 0, 10, 10),), 30
            ),
        ),
        legal_phase_transitions=((2, 0), (2, 1)),
    )

    audit = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3()).audit_record(tied)

    assert audit["selection_reason"] == "equal_score_smallest_index"
    assert audit["current_phase"] == 2
    assert audit["elapsed_phase_time"] == 30.0
    assert audit["legal_targets"] == [0, 1]
    assert audit["candidate_phases"] == [0, 1, 2]
    assert audit["selected_phase"] == 0


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
