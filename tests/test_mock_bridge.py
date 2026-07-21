"""MockBridge 单元测试：验证离线桥接器接口行为。"""

from core.types import ControlAction, JointState
from engine.mock_bridge import MockBridge


def test_mock_bridge_start_close():
    bridge = MockBridge()
    bridge.start()
    assert bridge._started is True
    bridge.close()
    assert bridge._started is False


def test_mock_bridge_get_state_returns_joint_state():
    bridge = MockBridge(tls_id="tls_test")
    bridge.start()
    state = bridge.get_state()
    assert isinstance(state, JointState)
    assert state.tls_id == "tls_test"
    assert len(state.queues) == 4
    directions = {q.direction for q in state.queues}
    assert directions == {"north", "south", "east", "west"}


def test_mock_bridge_step_advances_time():
    bridge = MockBridge(step_length=1.0)
    bridge.start()
    t1 = bridge.step()
    t2 = bridge.step()
    assert t2 > t1


def test_mock_bridge_apply_actions_no_error():
    bridge = MockBridge()
    bridge.start()
    actions = [
        ControlAction(tls_id="tls_0", action_type="set_phase", value=1, reason="test"),
        ControlAction(tls_id="tls_0", action_type="set_phase_duration", value=30.0),
    ]
    bridge.apply_actions(actions)
    assert len(bridge._applied_actions) == 2
