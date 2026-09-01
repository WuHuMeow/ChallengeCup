import dataclasses
import json
from pathlib import Path

import pytest

from algorithms.capacity_aware_max_pressure import (
    CapacityAwareConfig,
    CapacityAwareMaxPressureAlgorithm,
)
from algorithms.classic_max_pressure import ClassicMaxPressureAlgorithm
from cloud.cloud_policy import CloudPolicy
from core.movements import MovementKey, MovementState, PhaseMovementState
from core.types import JointState, PhaseTrafficState, QueueState
from engine.mock_bridge import MockBridge
from engine.safety_executor import SafetyExecutor


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


def _legacy_phase(index: int, queue: float, lane: str) -> PhaseTrafficState:
    return PhaseTrafficState(
        phase_index=index,
        signal_state="G",
        nominal_duration=30.0,
        incoming_lanes=(lane,),
        outgoing_lanes=(f"{lane}_out",),
        incoming_queue=queue,
        incoming_capacity=10.0,
        outgoing_queue=0.0,
        outgoing_capacity=10.0,
        outgoing_occupancy=0.0,
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


def test_capacity_controller_delegates_min_green_to_the_safety_executor(state):
    state.elapsed_phase_time = 9.5

    actions = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3()).step(state)

    assert [(action.action_type, action.value) for action in actions] == [
        ("set_phase", 1),
        ("set_phase_duration", 30.0),
    ]
    assert all(
        action.issued_at == state.timestamp
        and action.expires_at == state.timestamp + 60.0
        for action in actions
    )


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
    assert m3.manifest["safety_boundary"] == "safety_executor"
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


def test_legacy_phase_states_share_one_prediction_snapshot():
    """Legacy state must retain one EWMA update for a state passed to audit."""
    policy = CloudPolicy()
    policy.alpha = 0.5
    policy.horizon = 3600
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4(), policy)
    phases = [_legacy_phase(0, 1.0, "in_current"), _legacy_phase(1, 10.0, "in_target")]
    low = JointState(
        step=9,
        timestamp=9.0,
        tls_id="tls_legacy",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=30.0,
        flows={"in_current": 0.0, "in_target": 0.0},
        phase_states=phases,
        phase_movements=(),
        legal_phase_transitions=((0, 1),),
    )
    high = dataclasses.replace(
        low,
        step=10,
        timestamp=10.0,
        flows={"in_current": 0.0, "in_target": 600.0},
    )

    algorithm.step(low)
    algorithm.step(high)
    algorithm.audit_record(high)

    expected_hourly_ewma = 0.5 * 600.0 + (1.0 - 0.5) * 0.0
    assert expected_hourly_ewma == 300.0
    assert policy._prev_hourly_flow["in_target"] == expected_hourly_ewma


def test_legacy_phase_states_audit_records_exact_action_and_existing_results():
    """Legacy audit must serialize the actions and ActionResults actually returned."""
    legacy_state = JointState(
        step=10,
        timestamp=10.0,
        tls_id="tls_legacy",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=30.0,
        phase_states=[
            _legacy_phase(0, 1.0, "in_current"),
            _legacy_phase(1, 10.0, "in_target"),
        ],
        phase_movements=(),
        legal_phase_transitions=((0, 1),),
    )
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3())

    actions = algorithm.step(legacy_state)
    results = SafetyExecutor().apply(
        actions, legacy_state, MockBridge(tls_id="tls_legacy")
    )
    audit = algorithm.audit_record(legacy_state, results)

    assert actions[0].action_type == "set_phase"
    assert actions[0].value == 1
    assert actions[1].action_type == "set_phase_duration"
    assert [result.action for result in results] == actions
    assert [result.accepted for result in results] == [False, False]
    assert [result.reason_code for result in results] == [
        "clearance_path_unavailable",
        "phase_change_rejected",
    ]
    assert audit["final_decision"]["action"] == actions[0].action_type
    assert [(action["action_type"], action["value"]) for action in audit["final_decision"]["actions"]] == [
        (action.action_type, action.value) for action in actions
    ]
    assert [(result["action_type"], result["value"], result["accepted"]) for result in audit["final_decision"]["action_results"]] == [
        (result.action.action_type, result.action.value, result.accepted)
        for result in results
    ]


def test_legacy_phase_states_audit_explains_equal_score_smallest_index_tie():
    """Without movement state, equal legacy pressure still chooses the smallest index."""
    legacy_tie = JointState(
        step=10,
        timestamp=10.0,
        tls_id="tls_legacy",
        current_phase=2,
        current_phase_name="p2",
        elapsed_phase_time=30.0,
        phase_states=[
            _legacy_phase(0, 10.0, "in_zero"),
            _legacy_phase(1, 10.0, "in_one"),
            _legacy_phase(2, 1.0, "in_current"),
        ],
        phase_movements=(),
        legal_phase_transitions=((2, 0), (2, 1)),
    )
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3())

    actions = algorithm.step(legacy_tie)
    audit = algorithm.audit_record(legacy_tie)

    assert actions[0].action_type == "set_phase"
    assert actions[0].value == 0
    assert actions[1].action_type == "set_phase_duration"
    assert audit["selection_reason"] == "equal_score_smallest_index"
    assert audit["current_phase"] == 2
    assert audit["elapsed_phase_time"] == 30.0
    assert audit["legal_targets"] == [0, 1]
    assert audit["candidate_phases"] == [0, 1, 2]
    assert audit["selected_phase"] == 0


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
    policy = CloudPolicy(model_path=Path("nonexistent-model.pkl"))
    policy.horizon = 300
    predicted = policy.predict(dataclasses.replace(state, flows={"in_a": 600.0}))

    assert predicted.predicted_flows == {"in_a": 50.0}


def test_prediction_keeps_ewma_history_in_hourly_flow_units(state):
    """Storing horizon vehicles as EWMA history would make the second 600 veh/h forecast 36.25."""
    policy = CloudPolicy(model_path=Path("nonexistent-model.pkl"))
    policy.horizon = 300
    hourly = dataclasses.replace(state, flows={"in_a": 600.0})

    policy.predict(hourly)
    predicted = policy.predict(hourly)

    assert predicted.predicted_flows == {"in_a": 50.0}


def _legacy_decision_state(
    *,
    with_transition: bool,
    step: int = 10,
    elapsed: float = 20.0,
    flows: dict[str, float] | None = None,
) -> JointState:
    phases = [_legacy_phase(0, 1.0, "in_current")]
    target_phase = 2 if with_transition else 1
    if with_transition:
        phases.append(
            dataclasses.replace(
                _legacy_phase(1, 0.0, "in_transition"), signal_state="y"
            )
        )
    phases.append(_legacy_phase(target_phase, 10.0, "in_target"))
    return JointState(
        step=step,
        timestamp=float(step),
        tls_id="tls_legacy",
        current_phase=0,
        current_phase_name="p0",
        elapsed_phase_time=elapsed,
        flows=flows or {"in_current": 0.0, "in_target": 600.0},
        phase_states=phases,
        phase_movements=(),
        legal_phase_transitions=((0, target_phase),),
    )


def _capacity_runtime_state(algorithm: CapacityAwareMaxPressureAlgorithm):
    return (
        algorithm._configured_phase,
        algorithm.base_green,
        algorithm.min_green,
        algorithm.max_green,
        dict(algorithm.cloud_policy._prev_predicted),
        dict(algorithm.cloud_policy._prev_hourly_flow),
        None
        if algorithm.cloud_policy._last_params is None
        else dict(algorithm.cloud_policy._last_params),
        algorithm.cloud_policy._last_dispatch_step,
    )


@pytest.mark.parametrize("with_transition", (False, True), ids=("direct", "safe"))
def test_legacy_observation_first_is_pure_and_converges_with_clean_step(
    with_transition,
):
    """Legacy inspection must not change the direct or safe-transition action path."""
    observed_policy = CloudPolicy()
    clean_policy = CloudPolicy()
    for policy in (observed_policy, clean_policy):
        policy.alpha = 0.5
        policy.horizon = 3600
    observed = CapacityAwareMaxPressureAlgorithm(
        CapacityAwareConfig.m4(), observed_policy
    )
    clean = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4(), clean_policy)
    high = _legacy_decision_state(with_transition=with_transition)
    low = dataclasses.replace(
        high,
        step=9,
        timestamp=9.0,
        flows={"in_current": 0.0, "in_target": 0.0},
    )
    observed_policy.predict(low)
    clean_policy.predict(low)
    before_observation = _capacity_runtime_state(observed)

    observed.audit_record(high)
    observed.score_breakdown(high)

    assert _capacity_runtime_state(observed) == before_observation
    equivalent_high = dataclasses.replace(
        high, phase_states=list(high.phase_states), flows=dict(high.flows)
    )
    observed_actions = observed.step(equivalent_high)
    clean_actions = clean.step(high)
    assert observed_actions == clean_actions
    assert _capacity_runtime_state(observed) == _capacity_runtime_state(clean)
    assert observed_policy._prev_hourly_flow["in_target"] == 300.0
    audit_after_step = observed.audit_record(high)
    assert audit_after_step["final_decision"]["actions"] == [
        {
            "action_type": action.action_type,
            "value": action.value,
            "reason": action.reason,
        }
        for action in observed_actions
    ]
    assert observed_policy._prev_hourly_flow["in_target"] == 300.0


def test_movement_m4_observation_first_is_pure_and_commits_prediction_once(state):
    """Movement inspection must cache forecast scores without advancing EWMA."""
    observed_policy = CloudPolicy()
    clean_policy = CloudPolicy()
    for policy in (observed_policy, clean_policy):
        policy.alpha = 0.5
        policy.horizon = 3600
    observed = CapacityAwareMaxPressureAlgorithm(
        CapacityAwareConfig.m4(), observed_policy
    )
    clean = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4(), clean_policy)
    low = dataclasses.replace(state, step=9, timestamp=9.0, flows={"in_c": 0.0})
    high = dataclasses.replace(state, flows={"in_c": 600.0})
    observed_policy.predict(low)
    clean_policy.predict(low)
    before_observation = _capacity_runtime_state(observed)

    observed.score_breakdown(high)
    observed.audit_record(high)

    assert _capacity_runtime_state(observed) == before_observation
    equivalent_high = dataclasses.replace(high, flows=dict(high.flows))
    observed_actions = observed.step(equivalent_high)
    clean_actions = clean.step(high)
    assert observed_actions == clean_actions
    assert _capacity_runtime_state(observed) == _capacity_runtime_state(clean)
    assert observed_policy._prev_hourly_flow == {"in_c": 300.0}
    observed.audit_record(high)
    assert observed_policy._prev_hourly_flow == {"in_c": 300.0}


def test_m3_legacy_disables_prediction_and_keeps_frozen_green_limits():
    """Cloud tiers must not enable M3 prediction or raise its 30-second maximum."""
    policy = CloudPolicy()
    policy.alpha = 0.5
    policy.horizon = 3600
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3(), policy)
    pressured = dataclasses.replace(
        _legacy_decision_state(with_transition=False),
        queues=[
            QueueState(
                direction="in_target",
                queue_length=9.0,
                waiting_time=0.0,
                vehicle_count=9,
                capacity=10.0,
            )
        ],
    )

    actions = algorithm.step(pressured)
    audit = algorithm.audit_record(pressured)

    duration = next(
        action.value
        for action in actions
        if action.action_type == "set_phase_duration"
    )
    audited_duration = next(
        action["value"]
        for action in audit["final_decision"]["actions"]
        if action["action_type"] == "set_phase_duration"
    )
    assert policy._prev_predicted == {}
    assert policy._prev_hourly_flow == {}
    assert duration == 30.0
    assert audited_duration == 30.0
    assert algorithm.min_green == algorithm.manifest["min_green"] == 10.0
    assert algorithm.max_green == algorithm.manifest["max_green"] == 30.0


def test_legacy_audit_delegates_clearance_state_to_the_safety_executor():
    """Legacy audit records the green request, never algorithm-owned clearance."""
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m3())
    initial = _legacy_decision_state(with_transition=True)
    algorithm.step(initial)
    waiting = dataclasses.replace(
        initial,
        step=11,
        timestamp=11.0,
        current_phase=1,
        current_phase_name="p1",
        elapsed_phase_time=1.0,
    )

    waiting_audit = algorithm.audit_record(waiting)
    waiting_actions = algorithm.step(waiting)
    complete = dataclasses.replace(
        waiting, step=12, timestamp=12.0, elapsed_phase_time=3.0
    )
    complete_audit = algorithm.audit_record(complete)
    complete_actions = algorithm.step(complete)

    assert waiting_audit["selection_reason"] == "highest_viable_pressure"
    assert waiting_audit["decision_reason"] == "dispatch_safety_executor"
    assert waiting_actions[0].value == 2
    assert complete_audit["selection_reason"] == "highest_viable_pressure"
    assert complete_audit["decision_reason"] == "dispatch_safety_executor"
    assert complete_actions[0].value == 2


def test_decision_plan_validates_fingerprint_owner_epoch_revision_and_history(state):
    """Stale, foreign, reset, or reconstructed history plans must never commit."""
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4())
    old_plan = algorithm.plan_decision(state)
    state.flows["in_c"] = 600.0
    current_plan = algorithm.plan_decision(state)

    assert current_plan is not old_plan
    with pytest.raises(RuntimeError, match="decision_plan_superseded"):
        algorithm.commit_plan(old_plan)
    with pytest.raises(RuntimeError, match="decision_plan_cross_owner"):
        CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4()).commit_plan(
            current_plan
        )
    algorithm.commit_plan(current_plan)
    after_first_commit = _capacity_runtime_state(algorithm)
    algorithm.commit_plan(current_plan)
    assert _capacity_runtime_state(algorithm) == after_first_commit

    newer = dataclasses.replace(state, step=11, timestamp=11.0)
    algorithm.step(newer)
    changed_history = dataclasses.replace(
        state, flows={"in_c": 700.0}
    )
    with pytest.raises(RuntimeError, match="decision_history_unavailable"):
        algorithm.audit_record(changed_history)

    future = dataclasses.replace(state, step=12, timestamp=12.0)
    pre_reset_plan = algorithm.plan_decision(future)
    algorithm.reset()
    with pytest.raises(RuntimeError, match="decision_plan_post_reset"):
        algorithm.commit_plan(pre_reset_plan)


def test_capacity_injected_prediction_weight_is_effective_without_policy_mutation():
    """An algorithm override must not silently rewrite its injected policy config."""

    class FalsyCloudPolicy(CloudPolicy):
        def __bool__(self):
            return False

    policy = FalsyCloudPolicy()
    policy.configured_prediction_weight = 0.7

    algorithm = CapacityAwareMaxPressureAlgorithm(
        CapacityAwareConfig.m4(),
        policy,
        prediction_weight=0.2,
    )

    assert algorithm.cloud_policy is policy
    assert policy.configured_prediction_weight == 0.7
    assert algorithm.manifest["prediction_weight"] == 0.2


def test_capacity_rejects_transactional_policy_missing_required_configuration():
    """A partial transaction object must fail at injection, not during a live tick."""

    class IncompleteTransactionalPolicy:
        def plan(self, state, *, prediction, dispatch):
            raise AssertionError("incomplete policy must fail before planning")

        def validate_plan(self, plan):
            return True

        def commit(self, plan):
            pass

        def reset(self):
            pass

    with pytest.raises(TypeError, match="capacity_cloud_policy_contract_missing"):
        CapacityAwareMaxPressureAlgorithm(
            CapacityAwareConfig.m4(), IncompleteTransactionalPolicy()
        )


def test_capacity_keeps_committed_audit_while_a_newer_plan_is_pending(state):
    """Post-step audit must not replace the pending next-tick decision."""
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4())
    committed_actions = algorithm.step(state)
    committed_audit = algorithm.audit_record(state)
    newer_state = dataclasses.replace(
        state, step=11, timestamp=11.0, flows={"in_c": 600.0}
    )
    newer_plan = algorithm.plan_decision(newer_state)

    historical_audit = algorithm.audit_record(dataclasses.replace(state))

    assert historical_audit == committed_audit
    algorithm.commit_plan(newer_plan)
    assert newer_plan.actions
    assert committed_actions


def test_capacity_duplicate_commit_preserves_a_newer_pending_plan(state):
    """Recommitting A must leave the capacity and nested B transactions intact."""
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4())
    committed = algorithm.plan_decision(state)
    algorithm.commit_plan(committed)
    newer = algorithm.plan_decision(
        dataclasses.replace(state, step=11, timestamp=11.0, flows={"in_c": 600.0})
    )
    before_duplicate = (
        _capacity_runtime_state(algorithm),
        algorithm._decision_runtime_revision,
        algorithm.cloud_policy._runtime_revision,
    )

    algorithm.commit_plan(committed)

    assert (
        _capacity_runtime_state(algorithm),
        algorithm._decision_runtime_revision,
        algorithm.cloud_policy._runtime_revision,
    ) == before_duplicate
    assert algorithm._pending_decision_plan is newer
    algorithm.commit_plan(newer)
    after_newer = (
        _capacity_runtime_state(algorithm),
        algorithm._decision_runtime_revision,
        algorithm.cloud_policy._runtime_revision,
    )
    assert algorithm._decision_runtime_revision == before_duplicate[1] + 1
    algorithm.commit_plan(newer)
    assert (
        _capacity_runtime_state(algorithm),
        algorithm._decision_runtime_revision,
        algorithm.cloud_policy._runtime_revision,
    ) == after_newer


def test_capacity_cached_plan_rejects_an_injected_policy_reset(state):
    """A capacity cache hit cannot replay actions from a reset policy epoch."""
    policy = CloudPolicy()
    algorithm = CapacityAwareMaxPressureAlgorithm(CapacityAwareConfig.m4(), policy)
    assert algorithm.step(state)

    policy.reset()

    with pytest.raises(RuntimeError, match="cloud_plan_post_reset"):
        algorithm.step(dataclasses.replace(state))
