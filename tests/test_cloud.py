"""云端策略接口测试。"""
import dataclasses

import pytest

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
        p2 = policy.dispatch_params(_make_pressured_state(0.0, 10.0, step=300))  # 未到 600 步
        p3 = policy.dispatch_params(_make_pressured_state(0.0, 10.0, step=600))  # 重新分档
    assert p1["min_green"] == 20.0
    assert p2 == p1  # 周期内返回缓存
    assert p3["min_green"] == 10.0  # 压力回落 → 常规档
    assert any("云端下发参数" in r.message for r in caplog.records)


def test_dispatch_base_green_backward_compatible():
    policy = CloudPolicy()
    assert policy.dispatch_base_green(_make_state()) > 0


def _runtime_state(policy: CloudPolicy):
    return (
        dict(policy._prev_predicted),
        dict(policy._prev_hourly_flow),
        None if policy._last_params is None else dict(policy._last_params),
        policy._last_dispatch_step,
    )


def test_cloud_plan_is_observationally_pure_and_semantic_commit_is_idempotent():
    """Writing EWMA or dispatch caches during planning would let inspection alter control."""
    policy = CloudPolicy()
    policy.alpha = 0.5
    policy.horizon = 3600
    low = dataclasses.replace(
        _make_state(), step=99, timestamp=99.0, flows={"E0": 0.0}
    )
    high = dataclasses.replace(
        low, step=100, timestamp=100.0, flows={"E0": 600.0}
    )
    equivalent_high = dataclasses.replace(high, flows=dict(high.flows))
    policy.predict(low)
    before_plan = _runtime_state(policy)

    plan = policy.plan(high, prediction=True, dispatch=True)
    equivalent_plan = policy.plan(
        equivalent_high, prediction=True, dispatch=True
    )

    assert equivalent_plan is plan
    assert _runtime_state(policy) == before_plan
    policy.commit(plan)
    after_first_commit = _runtime_state(policy)
    policy.commit(plan)
    assert _runtime_state(policy) == after_first_commit
    assert policy._prev_hourly_flow == {"E0": 300.0}
    assert policy._last_dispatch_step == 100


def test_cloud_plan_fingerprint_rejects_mutation_supersession_and_cross_owner():
    """A changed flow or newer plan must not commit an obsolete prediction snapshot."""
    policy = CloudPolicy()
    state = _make_state()
    old_plan = policy.plan(state, prediction=True, dispatch=True)
    state.flows["E0"] = 600.0

    current_plan = policy.plan(state, prediction=True, dispatch=True)

    assert current_plan is not old_plan
    with pytest.raises(RuntimeError, match="cloud_plan_superseded"):
        policy.commit(old_plan)
    with pytest.raises(RuntimeError, match="cloud_plan_cross_owner"):
        CloudPolicy().commit(current_plan)
    policy.commit(current_plan)
    assert policy._prev_hourly_flow == {"E0": 600.0}


def test_cloud_plan_created_before_reset_is_rejected():
    """Reset must invalidate every plan derived from the prior runtime epoch."""
    policy = CloudPolicy()
    plan = policy.plan(_make_state(), prediction=True, dispatch=True)

    policy.reset()

    with pytest.raises(RuntimeError, match="cloud_plan_post_reset"):
        policy.commit(plan)


def test_cloud_keeps_committed_history_while_a_newer_plan_is_pending():
    """Looking up committed evidence must not supersede a newer pending plan."""
    policy = CloudPolicy()
    policy.alpha = 0.5
    committed_state = _make_state()
    committed_plan = policy.plan(
        committed_state, prediction=True, dispatch=True
    )
    policy.commit(committed_plan)
    newer_state = dataclasses.replace(
        committed_state, step=101, timestamp=101.0, flows={"E0": 600.0}
    )
    newer_plan = policy.plan(newer_state, prediction=True, dispatch=True)

    historical_plan = policy.plan(
        dataclasses.replace(committed_state, flows=dict(committed_state.flows)),
        prediction=True,
        dispatch=True,
    )

    assert historical_plan is committed_plan
    policy.commit(newer_plan)
    assert policy._prev_hourly_flow == {"E0": 450.0}


def test_cloud_duplicate_commit_preserves_a_newer_pending_plan():
    """Recommitting A must not supersede or discard the pending plan B."""
    policy = CloudPolicy()
    committed = policy.plan(_make_state(), prediction=True, dispatch=True)
    policy.commit(committed)
    newer_state = dataclasses.replace(
        _make_state(), step=101, timestamp=101.0, flows={"E0": 600.0}
    )
    newer = policy.plan(newer_state, prediction=True, dispatch=True)
    before_duplicate = (_runtime_state(policy), policy._runtime_revision)

    policy.commit(committed)

    assert (_runtime_state(policy), policy._runtime_revision) == before_duplicate
    assert policy._pending_plan is newer
    policy.commit(newer)
    after_newer = (_runtime_state(policy), policy._runtime_revision)
    assert policy._runtime_revision == before_duplicate[1] + 1
    policy.commit(newer)
    assert (_runtime_state(policy), policy._runtime_revision) == after_newer


def test_cloud_rejects_planning_and_committing_changed_old_history():
    """Order 100 cannot be reconstructed after order 101 has committed."""
    policy = CloudPolicy()
    order_100 = _make_state()
    changed_100 = dataclasses.replace(order_100, flows={"E0": 450.0})
    historical = policy.plan(changed_100, prediction=True, dispatch=True)
    first = policy.plan(order_100, prediction=True, dispatch=True)
    policy.commit(first)
    order_101 = dataclasses.replace(
        order_100, step=101, timestamp=101.0, flows={"E0": 600.0}
    )
    second = policy.plan(order_101, prediction=True, dispatch=True)
    policy.commit(second)
    committed_runtime = (_runtime_state(policy), policy._runtime_revision)

    with pytest.raises(RuntimeError, match="cloud_history_unavailable"):
        policy.commit(historical)
    assert (_runtime_state(policy), policy._runtime_revision) == committed_runtime

    with pytest.raises(RuntimeError, match="cloud_history_unavailable"):
        policy.plan(changed_100, prediction=True, dispatch=True)
    assert (_runtime_state(policy), policy._runtime_revision) == committed_runtime
