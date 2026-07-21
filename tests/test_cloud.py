"""云端策略接口测试。"""
from core.types import JointState, QueueState, PredictionResult
from cloud.cloud_policy import CloudPolicy


def _make_state() -> JointState:
    return JointState(
        step=100, timestamp=100.0, tls_id="tls_0",
        current_phase=0, current_phase_name="p0",
        elapsed_phase_time=10.0,
        queues=[QueueState(direction="E0", queue_length=5.0, waiting_time=8.0, vehicle_count=6)],
        flows={"E0": 300.0},
    )


def test_predict_returns_prediction_result():
    policy = CloudPolicy()
    result = policy.predict(_make_state())
    assert isinstance(result, PredictionResult)
    assert "E0" in result.predicted_flows


def test_dispatch_base_green_returns_float():
    policy = CloudPolicy()
    state = _make_state()
    base_green = policy.dispatch_base_green(state)
    assert isinstance(base_green, float)
    assert base_green > 0


def test_reset_clears_state():
    policy = CloudPolicy()
    policy.predict(_make_state())
    policy.reset()
    assert policy._prev_predicted == {}
