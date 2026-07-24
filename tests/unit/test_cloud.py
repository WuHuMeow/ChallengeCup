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


def _make_pressured_state(queue: float, capacity: float, step: int = 100) -> JointState:
    return JointState(
        step=step, timestamp=float(step), tls_id="tls_0",
        current_phase=0, current_phase_name="p0", elapsed_phase_time=10.0,
        queues=[QueueState(direction="E0", queue_length=queue,
                           waiting_time=8.0, vehicle_count=6, capacity=capacity)],
        flows={"E0": 300.0},
    )


def test_pressure_tiers():
    policy = CloudPolicy()
    # avg_pressure = queue/capacity
    assert policy._compute_params(0.9)["min_green"] == 20.0   # 极高档
    assert policy._compute_params(0.5)["min_green"] == 15.0   # 中档
    assert policy._compute_params(0.1)["min_green"] == 10.0   # 常规档


def test_avg_pressure_uses_capacity():
    policy = CloudPolicy()
    state = _make_pressured_state(queue=9.0, capacity=10.0)
    assert abs(policy.avg_pressure(state) - 0.9) < 1e-9


def test_dispatch_params_interval_and_logging(caplog):
    import logging
    policy = CloudPolicy()
    with caplog.at_level(logging.INFO):
        p1 = policy.dispatch_params(_make_pressured_state(9.0, 10.0, step=0))
        p2 = policy.dispatch_params(_make_pressured_state(0.0, 10.0, step=30))  # 未到 60 步
        p3 = policy.dispatch_params(_make_pressured_state(0.0, 10.0, step=60))  # 重新分档
    assert p1["min_green"] == 20.0
    assert p2 == p1  # 周期内返回缓存
    assert p3["min_green"] == 10.0  # 压力回落 → 常规档
    assert any("云端下发参数" in r.message for r in caplog.records)


def test_dispatch_base_green_backward_compatible():
    policy = CloudPolicy()
    assert policy.dispatch_base_green(_make_state()) > 0
