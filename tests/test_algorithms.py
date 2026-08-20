"""算法接口契约测试：验证所有算法遵循 BaseControlAlgorithm 接口。"""

from algorithms.base import BaseControlAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from algorithms.classic_max_pressure import ClassicMaxPressureAlgorithm
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
    meta = SceneMeta(
        intersection_id="1",
        name="test",
        sumo_net=Path("dummy.net.xml"),
        sumo_rou=Path("dummy.rou.xml"),
        sumo_flow=Path("dummy.flow.xml"),
        sumo_turn=Path("dummy.turn.xml"),
        sumo_cfg=Path("dummy.sumocfg"),
        timing_xlsx=Path("dummy.xlsx"),
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
    result = algo.step(_make_state())
    assert isinstance(result, list)


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
    second = algorithm.step(_phase_state(current=1, elapsed=3, phases=phases))

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

    algorithm.step(_phase_state(current=0, elapsed=20, phases=phases))
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
