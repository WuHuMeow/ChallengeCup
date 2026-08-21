"""算法接口契约测试：验证所有算法遵循 BaseControlAlgorithm 接口。"""

import dataclasses

import pytest

from algorithms.base import BaseControlAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from algorithms.classic_max_pressure import ClassicMaxPressureAlgorithm
from cloud.cloud_policy import CloudPolicy
from core.types import (
    ControlAction,
    JointState,
    PhaseTrafficState,
    QueueState,
    Scene,
    SceneMeta,
)
from pathlib import Path
from typing import List


def _make_scene() -> Scene:
    data_dir = Path(__file__).resolve().parents[1] / "data" / "intersection_data" / "1"
    sumo_dir = data_dir / "sumo工程"
    meta = SceneMeta(
        intersection_id="1",
        name="test",
        sumo_net=sumo_dir / "demo_1.net.xml",
        sumo_rou=sumo_dir / "demo_1.rou.xml",
        sumo_flow=sumo_dir / "demo_1.flow.xml",
        sumo_turn=sumo_dir / "demo_1.turn.xml",
        sumo_cfg=sumo_dir / "demo_1.sumocfg",
        timing_xlsx=data_dir / "路口数据" / "demo_1流量和交叉口配时方案.xlsx",
    )
    return Scene(meta=meta)


def _make_state() -> JointState:
    return JointState(
        step=100,
        timestamp=100.0,
        tls_id="tls_0",
        current_phase=0,
        current_phase_name="phase_0",
        elapsed_phase_time=15.0,
        queues=[
            QueueState(direction="E0", queue_length=10.0, waiting_time=20.0, vehicle_count=12),
            QueueState(direction="E1", queue_length=3.0, waiting_time=5.0, vehicle_count=4),
        ],
        flows={"E0": 400.0, "E1": 200.0},
    )


def test_all_algorithms_implement_interface():
    algorithms: List[BaseControlAlgorithm] = [
        FixedTimeAlgorithm(),
        RuleAdaptiveAlgorithm(),
        ClassicMaxPressureAlgorithm(),
        CAMaxPressureAlgorithm(),
    ]
    for algo in algorithms:
        assert hasattr(algo, "init")
        assert hasattr(algo, "step")
        assert hasattr(algo, "reset")
        assert hasattr(algo, "name")


def test_fixed_time_returns_list():
    algo = FixedTimeAlgorithm()
    algo.init(_make_scene())
    result = algo.step(_make_state())
    assert isinstance(result, list)
    assert algo.resolved_timing_plan is not None


def test_rule_adaptive_returns_control_actions():
    algo = RuleAdaptiveAlgorithm(min_green=5, max_green=60, queue_threshold=5)
    algo.init(_make_scene())
    result = algo.step(_make_state())
    assert isinstance(result, list)
    for action in result:
        assert isinstance(action, ControlAction)
        assert action.tls_id == "tls_0"


def test_ca_maxpressure_returns_control_actions():
    algo = CAMaxPressureAlgorithm()
    algo.init(_make_scene())
    result = algo.step(_make_state())
    assert isinstance(result, list)
    for action in result:
        assert isinstance(action, ControlAction)
        assert action.tls_id == "tls_0"


def test_algorithm_names_unique():
    names = [
        FixedTimeAlgorithm().name,
        RuleAdaptiveAlgorithm().name,
        ClassicMaxPressureAlgorithm().name,
        CAMaxPressureAlgorithm().name,
    ]
    assert names == [
        "fixed_time",
        "actuated",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    ]


def _phase(
    phase_index,
    incoming_queue,
    incoming_capacity,
    outgoing_queue,
    outgoing_capacity,
    outgoing_occupancy,
    signal_state="Grr",
):
    return PhaseTrafficState(
        phase_index=phase_index,
        signal_state=signal_state,
        nominal_duration=30.0 if "G" in signal_state else 3.0,
        incoming_lanes=(f"in_{phase_index}",),
        outgoing_lanes=(f"out_{phase_index}",),
        incoming_queue=incoming_queue,
        incoming_capacity=incoming_capacity,
        outgoing_queue=outgoing_queue,
        outgoing_capacity=outgoing_capacity,
        outgoing_occupancy=outgoing_occupancy,
    )


def _phase_state(current, elapsed, phases, flows=None):
    return JointState(
        step=100,
        timestamp=10.0,
        tls_id="tls_0",
        current_phase=current,
        current_phase_name=f"phase_{current}",
        elapsed_phase_time=elapsed,
        queues=[],
        flows=flows or {},
        phase_states=phases,
    )


def test_ca_mp_uses_capacity_normalized_pressure():
    phases = [
        _phase(0, 8, 10, 1, 10, 0.1),
        _phase(1, 0, 1, 0, 1, 0.0, signal_state="yrr"),
        _phase(2, 12, 30, 0, 30, 0.1),
        _phase(3, 0, 1, 0, 1, 0.0, signal_state="rrr"),
    ]

    actions = CAMaxPressureAlgorithm().step(
        _phase_state(current=0, elapsed=20, phases=phases)
    )

    assert actions[0].action_type == "set_phase"
    assert actions[0].value == 0
    assert isinstance(actions[0].value, int)
    assert actions[1].action_type == "set_phase_duration"
    assert isinstance(actions[1].value, float)


def test_ca_mp_blocks_saturated_downstream_and_uses_safe_transition():
    phases = [
        _phase(0, 8, 10, 0, 10, 0.95),
        _phase(1, 0, 1, 0, 1, 0.0, signal_state="yrr"),
        _phase(2, 4, 10, 0, 10, 0.20),
        _phase(3, 0, 1, 0, 1, 0.0, signal_state="rrr"),
    ]
    algorithm = CAMaxPressureAlgorithm()

    first = algorithm.step(_phase_state(current=0, elapsed=20, phases=phases))
    second = algorithm.step(
        dataclasses.replace(
            _phase_state(current=1, elapsed=3, phases=phases),
            step=101,
            timestamp=11.0,
        )
    )

    assert first[0].value == 1
    assert "target=2" in first[0].reason
    assert second[0].value == 2
    assert second[1].action_type == "set_phase_duration"


def test_ca_mp_respects_minimum_green_before_switching():
    phases = [
        _phase(0, 1, 10, 0, 10, 0.1),
        _phase(1, 0, 1, 0, 1, 0.0, signal_state="yrr"),
        _phase(2, 9, 10, 0, 10, 0.1),
    ]

    actions = CAMaxPressureAlgorithm().step(
        _phase_state(current=0, elapsed=5, phases=phases)
    )

    assert actions == []


def test_ca_mp_dynamic_green_is_clamped_and_reset_clears_pending_state():
    phases = [
        _phase(0, 1, 10, 0, 10, 0.1),
        _phase(1, 0, 1, 0, 1, 0.0, signal_state="yrr"),
        _phase(2, 100, 10, 0, 10, 0.1),
    ]
    algorithm = CAMaxPressureAlgorithm()
    first = algorithm.step(_phase_state(current=2, elapsed=20, phases=phases))

    duration = next(action.value for action in first if action.action_type == "set_phase_duration")
    assert algorithm.min_green <= duration <= algorithm.max_green

    algorithm.step(
        dataclasses.replace(
            _phase_state(current=0, elapsed=20, phases=phases),
            step=101,
            timestamp=11.0,
        )
    )
    assert algorithm.pending_target_phase == 2
    algorithm.reset()
    assert algorithm.pending_target_phase is None


def test_ca_mp_frozen_base_green_survives_cloud_dispatch():
    phases = [_phase(0, 5, 10, 0, 10, 0.1)]
    algorithm = CAMaxPressureAlgorithm(base_green=45.0)

    actions = algorithm.step(
        _phase_state(current=0, elapsed=20, phases=phases)
    )

    duration = next(
        action.value
        for action in actions
        if action.action_type == "set_phase_duration"
    )
    assert duration == 45.0


def test_ca_maxpressure_empty_queues_returns_empty():
    """空排队时不应产生动作。"""
    from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
    from core.types import JointState
    algo = CAMaxPressureAlgorithm()
    algo.init(_make_scene())
    state = JointState(
        step=0, timestamp=0.0, tls_id="tls_0",
        current_phase=0, current_phase_name="p0",
        elapsed_phase_time=0.0, queues=[], flows={},
    )
    actions = algo.step(state)
    assert actions == []


def _ca_runtime_state(algorithm: CAMaxPressureAlgorithm):
    return (
        algorithm.pending_target_phase,
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


def test_ca_mp_decision_plan_is_pure_then_commits_once_for_equivalent_state():
    """Planning must not pre-arm a transition or advance cloud runtime state."""
    phases = [
        _phase(0, 1, 10, 0, 10, 0.1),
        _phase(1, 0, 1, 0, 1, 0.0, signal_state="yrr"),
        _phase(2, 9, 10, 0, 10, 0.1),
    ]
    state = _phase_state(
        current=0,
        elapsed=20,
        phases=phases,
        flows={"in_0": 0.0, "in_2": 600.0},
    )
    equivalent = dataclasses.replace(
        state, phase_states=list(state.phase_states), flows=dict(state.flows)
    )
    algorithm = CAMaxPressureAlgorithm()
    before_plan = _ca_runtime_state(algorithm)

    plan = algorithm.plan_decision(state)
    equivalent_plan = algorithm.plan_decision(equivalent)

    assert equivalent_plan is plan
    assert _ca_runtime_state(algorithm) == before_plan
    planned_actions = plan.control_actions()
    algorithm.commit_plan(plan)
    after_first_commit = _ca_runtime_state(algorithm)
    algorithm.commit_plan(plan)
    assert _ca_runtime_state(algorithm) == after_first_commit
    assert algorithm.pending_target_phase == 2
    assert [(action.action_type, action.value) for action in planned_actions] == [
        ("set_phase", 1),
        ("set_phase_duration", 3.0),
    ]


def test_ca_mp_pending_wait_and_complete_reasons_come_from_planning_branch():
    """Transition wait and completion must not collapse into one inferred reason."""
    phases = [
        _phase(0, 1, 10, 0, 10, 0.1),
        _phase(1, 0, 1, 0, 1, 0.0, signal_state="yrr"),
        _phase(2, 9, 10, 0, 10, 0.1),
    ]
    algorithm = CAMaxPressureAlgorithm()
    algorithm.step(_phase_state(current=0, elapsed=20, phases=phases))
    waiting = dataclasses.replace(
        _phase_state(current=1, elapsed=1, phases=phases),
        step=101,
        timestamp=11.0,
    )
    complete = dataclasses.replace(waiting, step=102, timestamp=12.0, elapsed_phase_time=3.0)

    waiting_plan = algorithm.plan_decision(waiting)
    complete_plan = algorithm.plan_decision(complete)

    assert waiting_plan.decision_reason == "pending_transition_wait"
    assert waiting_plan.control_actions() == []
    assert complete_plan.decision_reason == "pending_transition_complete"
    assert complete_plan.control_actions()[0].value == 2


def test_ca_mp_commit_rejects_superseded_cross_owner_and_post_reset_plans():
    """Only the latest plan from the current controller epoch may change runtime state."""
    phases = [_phase(0, 5, 10, 0, 10, 0.1)]
    first_state = _phase_state(current=0, elapsed=20, phases=phases)
    next_state = dataclasses.replace(first_state, step=101, timestamp=11.0)
    algorithm = CAMaxPressureAlgorithm()
    old_plan = algorithm.plan_decision(first_state)
    current_plan = algorithm.plan_decision(next_state)

    with pytest.raises(RuntimeError, match="legacy_plan_superseded"):
        algorithm.commit_plan(old_plan)
    with pytest.raises(RuntimeError, match="legacy_plan_cross_owner"):
        CAMaxPressureAlgorithm().commit_plan(current_plan)
    algorithm.reset()
    with pytest.raises(RuntimeError, match="legacy_plan_post_reset"):
        algorithm.commit_plan(current_plan)


def test_ca_mp_preserves_falsy_injected_policy_and_requires_transactions():
    """Truthiness replacement or late failure would violate injected-policy ownership."""

    class FalsyCloudPolicy(CloudPolicy):
        def __bool__(self):
            return False

    class LegacyOnlyPolicy:
        def predict(self, state):
            raise AssertionError("legacy prediction API must not be accepted")

        def reset(self):
            pass

    policy = FalsyCloudPolicy()

    algorithm = CAMaxPressureAlgorithm(cloud_policy=policy)

    assert algorithm.cloud_policy is policy
    with pytest.raises(TypeError, match="cloud_policy_transactional_contract_missing"):
        CAMaxPressureAlgorithm(cloud_policy=LegacyOnlyPolicy())


def test_ca_mp_keeps_committed_history_while_a_newer_plan_is_pending():
    """Historical inspection must not invalidate the next live legacy decision."""
    phases = [_phase(0, 5, 10, 0, 10, 0.1)]
    committed_state = _phase_state(current=0, elapsed=20, phases=phases)
    algorithm = CAMaxPressureAlgorithm()
    committed_plan = algorithm.plan_decision(committed_state)
    algorithm.commit_plan(committed_plan)
    newer_state = dataclasses.replace(
        committed_state, step=101, timestamp=11.0, elapsed_phase_time=21.0
    )
    newer_plan = algorithm.plan_decision(newer_state)

    historical_plan = algorithm.plan_decision(dataclasses.replace(committed_state))

    assert historical_plan is committed_plan
    algorithm.commit_plan(newer_plan)


def test_ca_mp_duplicate_commit_preserves_a_newer_pending_plan():
    """A duplicate legacy commit is a no-op even while B is pending."""
    phases = [_phase(0, 5, 10, 0, 10, 0.1)]
    state = _phase_state(current=0, elapsed=20, phases=phases)
    algorithm = CAMaxPressureAlgorithm()
    committed = algorithm.plan_decision(state)
    algorithm.commit_plan(committed)
    newer = algorithm.plan_decision(
        dataclasses.replace(state, step=101, timestamp=11.0, elapsed_phase_time=21.0)
    )
    before_duplicate = (
        _ca_runtime_state(algorithm),
        algorithm._legacy_runtime_revision,
        algorithm.cloud_policy._runtime_revision,
    )

    algorithm.commit_plan(committed)

    assert (
        _ca_runtime_state(algorithm),
        algorithm._legacy_runtime_revision,
        algorithm.cloud_policy._runtime_revision,
    ) == before_duplicate
    assert algorithm._pending_legacy_plan is newer
    algorithm.commit_plan(newer)
    after_newer = (
        _ca_runtime_state(algorithm),
        algorithm._legacy_runtime_revision,
        algorithm.cloud_policy._runtime_revision,
    )
    assert algorithm._legacy_runtime_revision == before_duplicate[1] + 1
    algorithm.commit_plan(newer)
    assert (
        _ca_runtime_state(algorithm),
        algorithm._legacy_runtime_revision,
        algorithm.cloud_policy._runtime_revision,
    ) == after_newer


def test_ca_mp_rejects_planning_and_committing_changed_old_history():
    """The direct legacy transaction cannot advance from reconstructed history."""
    algorithm = CAMaxPressureAlgorithm()
    order_100 = _phase_state(
        current=0, elapsed=20, phases=[], flows={"in_0": 100.0}
    )
    changed_100 = dataclasses.replace(order_100, flows={"in_0": 200.0})
    historical = algorithm.plan_decision(changed_100)
    first = algorithm.plan_decision(order_100)
    algorithm.commit_plan(first)
    order_101 = dataclasses.replace(
        order_100, step=101, timestamp=11.0, flows={"in_0": 300.0}
    )
    second = algorithm.plan_decision(order_101)
    algorithm.commit_plan(second)
    committed_runtime = (
        _ca_runtime_state(algorithm),
        algorithm._legacy_runtime_revision,
    )

    with pytest.raises(RuntimeError, match="legacy_history_unavailable"):
        algorithm.commit_plan(historical)
    assert (
        _ca_runtime_state(algorithm),
        algorithm._legacy_runtime_revision,
    ) == committed_runtime

    with pytest.raises(RuntimeError, match="legacy_history_unavailable"):
        algorithm.plan_decision(changed_100)
    assert (
        _ca_runtime_state(algorithm),
        algorithm._legacy_runtime_revision,
    ) == committed_runtime


def test_ca_mp_cached_plan_rejects_an_injected_policy_reset():
    """A composite cache hit cannot replay actions from a reset policy epoch."""
    policy = CloudPolicy()
    algorithm = CAMaxPressureAlgorithm(cloud_policy=policy)
    phases = [_phase(0, 5, 10, 0, 10, 0.1)]
    state = _phase_state(current=0, elapsed=20, phases=phases)
    assert algorithm.step(state)

    policy.reset()

    with pytest.raises(RuntimeError, match="cloud_plan_post_reset"):
        algorithm.plan_decision(dataclasses.replace(state))


def test_ca_mp_repeated_selected_current_step_actions_then_no_action():
    """Direct step must plan from its newly committed configured-phase state."""
    state = _phase_state(
        current=0,
        elapsed=20,
        phases=[_phase(0, 5, 10, 0, 10, 0.1)],
    )
    algorithm = CAMaxPressureAlgorithm()

    first_actions = algorithm.step(state)
    second_actions = algorithm.step(dataclasses.replace(state))

    assert [(action.action_type, action.value) for action in first_actions] == [
        ("set_phase", 0),
        ("set_phase_duration", 30.0),
    ]
    assert second_actions == []

    explicit = CAMaxPressureAlgorithm()
    plan = explicit.plan_decision(state)
    explicit.commit_plan(plan)
    after_first_commit = (
        _ca_runtime_state(explicit),
        explicit._legacy_runtime_revision,
        explicit.cloud_policy._runtime_revision,
    )
    explicit.commit_plan(plan)
    assert (
        _ca_runtime_state(explicit),
        explicit._legacy_runtime_revision,
        explicit.cloud_policy._runtime_revision,
    ) == after_first_commit


def test_ca_mp_subclass_phase_pressure_override_changes_selected_phase():
    """The public scoring seam must control real direct-legacy selection."""

    class PreferCurrentPhase(CAMaxPressureAlgorithm):
        def phase_pressure(self, phase, predicted_arrivals):
            pressure = super().phase_pressure(phase, predicted_arrivals)
            return pressure + (10.0 if phase.phase_index == 0 else 0.0)

    state = _phase_state(
        current=0,
        elapsed=20,
        phases=[
            _phase(0, 1, 10, 0, 10, 0.1),
            _phase(1, 9, 10, 0, 10, 0.1),
        ],
    )

    base_actions = CAMaxPressureAlgorithm().step(state)
    overridden_actions = PreferCurrentPhase().step(state)

    assert base_actions[0].value == 1
    assert overridden_actions[0].value == 0
