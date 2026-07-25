"""算法接口契约测试：验证所有算法遵循 BaseControlAlgorithm 接口。"""

from algorithms.base import BaseControlAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from core.types import ControlAction, JointState, QueueState, Scene, SceneMeta
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
        CAMaxPressureAlgorithm().name,
    ]
    assert len(set(names)) == 3


def test_ca_maxpressure_mvi_selects_max_queue_phase():
    """MVI: 应选择排队最长方向对应的动作。"""
    from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
    algo = CAMaxPressureAlgorithm()
    algo.init(_make_scene())
    state = _make_state()
    actions = algo.step(state)
    assert len(actions) >= 1
    assert actions[0].tls_id == state.tls_id
    assert actions[0].action_type == "set_phase"
    assert "MVI" in actions[0].reason


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
