"""云端策略层：流量预测服务。

在赛道 B 单机实现中，用模块边界模拟云端：
- 离线训练产出 `ml/model.pkl`；
- 在线推理封装在 CloudPolicy.predict() 中；
- 边缘算法通过 CloudPolicy 获取未来流量预测。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, fields, is_dataclass
import logging
from pathlib import Path
from typing import Any, Optional

from core.config import get_config
from core.types import JointState, PredictionResult

logger = logging.getLogger(__name__)


def _freeze_decision_value(value: Any) -> Any:
    """Return a stable immutable representation of a decision input."""
    if is_dataclass(value) and not isinstance(value, type):
        return (
            type(value).__module__,
            type(value).__qualname__,
            tuple(
                (field.name, _freeze_decision_value(getattr(value, field.name)))
                for field in fields(value)
            ),
        )
    if isinstance(value, dict):
        frozen = (
            (_freeze_decision_value(key), _freeze_decision_value(item))
            for key, item in value.items()
        )
        return tuple(sorted(frozen, key=lambda pair: repr(pair[0])))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_decision_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted((_freeze_decision_value(item) for item in value), key=repr))
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, bytes, int, float, bool)):
        return value
    return repr(value)


def joint_state_fingerprint(state: JointState) -> tuple[Any, ...]:
    """Fingerprint every field so mutable observations cannot reuse a stale plan."""
    frozen = _freeze_decision_value(state)
    if not isinstance(frozen, tuple):
        raise TypeError("joint_state_fingerprint_not_tuple")
    return frozen


@dataclass(frozen=True)
class CloudPolicyPlan:
    """Immutable prediction/dispatch plan produced without changing runtime state."""

    owner_token: object
    reset_epoch: int
    base_revision: int
    state_fingerprint: tuple[Any, ...]
    state_step: int
    state_timestamp: float
    config_fingerprint: tuple[float, int, int]
    prediction_enabled: bool
    dispatch_enabled: bool
    predicted_flows: tuple[tuple[str, float], ...]
    horizon_steps: int
    horizon_seconds: float
    dispatched_params: tuple[tuple[str, float], ...]
    avg_pressure: float | None
    dispatch_updated: bool
    prediction_source: str
    observations: tuple[tuple[str, float, float], ...]
    next_prev_predicted: tuple[tuple[str, float], ...]
    next_prev_hourly_flow: tuple[tuple[str, float], ...]
    next_last_params: tuple[tuple[str, float], ...] | None
    next_last_dispatch_step: int

    def prediction_result(self) -> PredictionResult | None:
        if not self.prediction_enabled:
            return None
        return PredictionResult(
            horizon_steps=self.horizon_steps,
            horizon_seconds=self.horizon_seconds,
            predicted_flows=dict(self.predicted_flows),
        )

    def params(self) -> dict[str, float] | None:
        if not self.dispatch_enabled:
            return None
        return dict(self.dispatched_params)


class CloudPolicy:
    """云端流量预测策略（EWMA 指数加权移动平均）。"""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        cfg = get_config().get("algorithms.ca_maxpressure", {})
        self.alpha: float = cfg.get("ewma_alpha", 0.3)
        self.horizon: int = cfg.get("prediction_horizon", 300)
        self.update_interval: int = cfg.get("cloud_update_interval", 600)
        self.configured_prediction_weight: float = float(
            cfg.get("prediction_weight", 0.15)
        )
        self._prev_predicted: dict[str, float] = {}
        self._prev_hourly_flow: dict[str, float] = {}
        self._flow_history: dict[str, deque[tuple[float, float]]] = {}
        self._last_params: Optional[dict] = None
        self._last_dispatch_step: int = -10**9
        self._plan_owner = object()
        self._reset_epoch = 0
        self._runtime_revision = 0
        self._pending_plan: CloudPolicyPlan | None = None
        self._committed_plan: CloudPolicyPlan | None = None

        if model_path is None:
            model_path = get_config().path("paths.model_path")
        self.model_path = Path(model_path)
        self._model: Optional[dict] = None
        self.model_source = "ewma"
        self._load_model()

    def _load_model(self) -> None:
        """加载离线训练好的 GBR 流量预测模型；失败时回退 EWMA。"""
        from ml.train import load_flow_model

        loaded = load_flow_model(self.model_path)
        if loaded is not None:
            self._model = loaded
            logger.info("已加载云端流量预测模型: %s", self.model_path)

    def _observation(self, state: JointState) -> dict[str, tuple[float, float]]:
        """Return each direction's current hourly flow and total queue."""
        queues: dict[str, float] = {}
        for queue in state.queues:
            queues[queue.direction] = queues.get(queue.direction, 0.0) + queue.queue_length
        directions = dict.fromkeys(state.flows)
        for direction in queues:
            directions.setdefault(direction)
        return {
            direction: (
                float(state.flows.get(direction, 0.0)),
                queues.get(direction, 0.0),
            )
            for direction in directions
        }

    def _predict_with_model(
        self,
        state: JointState,
        observations: dict[str, tuple[float, float]],
    ) -> dict[str, float] | None:
        """Predict hourly flows once every direction has a lag observation."""
        from ml.features import build_flow_feature_row
        from ml.train import predict_flow

        if not observations:
            return None
        avg_queue = (
            sum(queue.queue_length for queue in state.queues) / len(state.queues)
            if state.queues
            else 0.0
        )
        predicted: dict[str, float] = {}
        for direction, (flow, queue) in observations.items():
            history = self._flow_history.get(direction)
            if not history:
                return None
            previous_flow, previous_queue = history[-1]
            features = build_flow_feature_row(
                flow_t=flow,
                flow_lag1=previous_flow,
                queue_t=queue,
                queue_lag1=previous_queue,
                avg_queue_t=avg_queue,
                phase=state.current_phase,
            )
            predicted[direction] = predict_flow(self._model, features)
        return predicted

    def _config_fingerprint(self) -> tuple[float, int, int]:
        return float(self.alpha), int(self.horizon), int(self.update_interval)

    @staticmethod
    def _items(values: dict[str, float]) -> tuple[tuple[str, float], ...]:
        return tuple(sorted((str(key), float(value)) for key, value in values.items()))

    def plan(
        self,
        state: JointState,
        *,
        prediction: bool,
        dispatch: bool,
    ) -> CloudPolicyPlan:
        """Plan prediction and parameter dispatch without changing runtime state."""
        fingerprint = joint_state_fingerprint(state)
        config_fingerprint = self._config_fingerprint()
        key = (fingerprint, config_fingerprint, bool(prediction), bool(dispatch))
        if self._pending_plan is not None:
            pending_key = (
                self._pending_plan.state_fingerprint,
                self._pending_plan.config_fingerprint,
                self._pending_plan.prediction_enabled,
                self._pending_plan.dispatch_enabled,
            )
            if (
                pending_key == key
                and self._pending_plan.reset_epoch == self._reset_epoch
                and self._pending_plan.base_revision == self._runtime_revision
            ):
                return self._pending_plan
        if self._committed_plan is not None:
            committed_key = (
                self._committed_plan.state_fingerprint,
                self._committed_plan.config_fingerprint,
                self._committed_plan.prediction_enabled,
                self._committed_plan.dispatch_enabled,
            )
            if committed_key == key:
                return self._committed_plan
            current_order = (state.step, float(state.timestamp))
            committed_order = (
                self._committed_plan.state_step,
                self._committed_plan.state_timestamp,
            )
            if current_order <= committed_order:
                raise RuntimeError("cloud_history_unavailable")

        predicted: dict[str, float] = {}
        observations = self._observation(state) if prediction else {}
        prediction_source = "none"
        next_prev_predicted = dict(self._prev_predicted)
        next_prev_hourly_flow = dict(self._prev_hourly_flow)
        if prediction:
            hourly_prediction: dict[str, float] | None = None
            if self._model is not None:
                try:
                    hourly_prediction = self._predict_with_model(state, observations)
                except (TypeError, ValueError) as exc:
                    logger.warning("模型预测失败，回退 EWMA: %s", exc)
            if hourly_prediction is not None:
                predicted = {
                    direction: flow * self.horizon / 3600.0
                    for direction, flow in hourly_prediction.items()
                }
                prediction_source = "model"
            else:
                for direction, (observed, _queue) in observations.items():
                    prev = self._prev_hourly_flow.get(direction, observed)
                    hourly_flow = self.alpha * observed + (1 - self.alpha) * prev
                    predicted[direction] = hourly_flow * self.horizon / 3600.0
                prediction_source = "ewma"
            next_prev_predicted = predicted
            next_prev_hourly_flow = {
                direction: vehicles * 3600.0 / self.horizon
                for direction, vehicles in predicted.items()
            }

        next_last_params = (
            None if self._last_params is None else dict(self._last_params)
        )
        next_last_dispatch_step = self._last_dispatch_step
        dispatched_params: dict[str, float] = {}
        pressure: float | None = None
        dispatch_updated = False
        if dispatch:
            pressure = self.avg_pressure(state)
            if (
                next_last_params is None
                or state.step - next_last_dispatch_step >= self.update_interval
            ):
                next_last_params = self._compute_params(pressure)
                next_last_dispatch_step = state.step
                dispatch_updated = True
            dispatched_params = dict(next_last_params)

        plan = CloudPolicyPlan(
            owner_token=self._plan_owner,
            reset_epoch=self._reset_epoch,
            base_revision=self._runtime_revision,
            state_fingerprint=fingerprint,
            state_step=state.step,
            state_timestamp=float(state.timestamp),
            config_fingerprint=config_fingerprint,
            prediction_enabled=bool(prediction),
            dispatch_enabled=bool(dispatch),
            predicted_flows=self._items(predicted),
            horizon_steps=self.horizon,
            horizon_seconds=float(self.horizon),
            dispatched_params=self._items(dispatched_params),
            avg_pressure=pressure,
            dispatch_updated=dispatch_updated,
            prediction_source=prediction_source,
            observations=tuple(
                (direction, flow, queue)
                for direction, (flow, queue) in observations.items()
            ),
            next_prev_predicted=self._items(next_prev_predicted),
            next_prev_hourly_flow=self._items(next_prev_hourly_flow),
            next_last_params=(
                None if next_last_params is None else self._items(next_last_params)
            ),
            next_last_dispatch_step=next_last_dispatch_step,
        )
        self._pending_plan = plan
        return plan

    def validate_plan(self, plan: CloudPolicyPlan) -> bool:
        """Validate a plan, returning False only when it is already committed."""
        if not isinstance(plan, CloudPolicyPlan):
            raise RuntimeError("cloud_plan_invalid_type")
        if plan.owner_token is not self._plan_owner:
            raise RuntimeError("cloud_plan_cross_owner")
        if plan.reset_epoch != self._reset_epoch:
            raise RuntimeError("cloud_plan_post_reset")
        if plan.config_fingerprint != self._config_fingerprint():
            raise RuntimeError("cloud_plan_config_changed")
        if plan is self._committed_plan:
            return False
        if self._committed_plan is not None:
            plan_key = (
                plan.state_fingerprint,
                plan.config_fingerprint,
                plan.prediction_enabled,
                plan.dispatch_enabled,
            )
            committed_key = (
                self._committed_plan.state_fingerprint,
                self._committed_plan.config_fingerprint,
                self._committed_plan.prediction_enabled,
                self._committed_plan.dispatch_enabled,
            )
            plan_order = (plan.state_step, plan.state_timestamp)
            committed_order = (
                self._committed_plan.state_step,
                self._committed_plan.state_timestamp,
            )
            if plan_key != committed_key and plan_order <= committed_order:
                raise RuntimeError("cloud_history_unavailable")
        if self._pending_plan is not None and plan is not self._pending_plan:
            raise RuntimeError("cloud_plan_superseded")
        if plan.base_revision != self._runtime_revision:
            raise RuntimeError("cloud_plan_stale_revision")
        if plan is not self._pending_plan:
            raise RuntimeError("cloud_plan_not_pending")
        return True

    def commit(self, plan: CloudPolicyPlan) -> None:
        """Apply one validated runtime transition; duplicate commit is a no-op."""
        if not self.validate_plan(plan):
            return
        self._prev_predicted = dict(plan.next_prev_predicted)
        self._prev_hourly_flow = dict(plan.next_prev_hourly_flow)
        self._last_params = (
            None if plan.next_last_params is None else dict(plan.next_last_params)
        )
        self._last_dispatch_step = plan.next_last_dispatch_step
        if plan.prediction_enabled:
            self.model_source = plan.prediction_source
            for direction, flow, queue in plan.observations:
                history = self._flow_history.setdefault(direction, deque(maxlen=2))
                history.append((flow, queue))
        self._runtime_revision += 1
        self._committed_plan = plan
        self._pending_plan = None
        if plan.dispatch_updated:
            logger.info(
                "云端下发参数: step=%d avg_pressure=%.3f params=%s",
                plan.state_step,
                plan.avg_pressure,
                dict(plan.dispatched_params),
            )

    def commit_plan(self, plan: CloudPolicyPlan) -> None:
        """Compatibility alias for callers that name both transaction phases."""
        self.commit(plan)

    def predict(self, state: JointState) -> PredictionResult:
        """Plan and commit one model-first prediction with EWMA fallback."""
        plan = self.plan(state, prediction=True, dispatch=False)
        self.commit(plan)
        result = plan.prediction_result()
        if result is None:
            raise RuntimeError("cloud_prediction_plan_missing_result")
        return result

    # (avg_pressure 阈值, 下发参数)：>0.8 极高压力（更激进）/ >0.4 中档 / 常规
    PRESSURE_TIERS = (
        (0.8, {"min_green": 20.0, "max_green": 120.0, "base_green": 45.0}),
        (0.4, {"min_green": 15.0, "max_green": 90.0, "base_green": 35.0}),
        (0.0, {"min_green": 10.0, "max_green": 90.0, "base_green": 30.0}),
    )

    def avg_pressure(self, state: JointState) -> float:
        """全局平均压力 = 各进口道 queue/capacity 均值（capacity 缺失时退化估计）。"""
        pressures = [q.queue_length / q.capacity for q in state.queues if q.capacity > 0]
        if pressures:
            return sum(pressures) / len(pressures)
        max_q = max((q.queue_length for q in state.queues), default=0.0)
        return min(1.0, max_q / 50.0)  # 无容量信息时的粗估计

    def _compute_params(self, avg_pressure: float) -> dict:
        """按全局压力分档计算下发参数。"""
        for threshold, params in self.PRESSURE_TIERS:
            if avg_pressure > threshold:
                return dict(params)
        return dict(self.PRESSURE_TIERS[-1][1])

    def dispatch_params(self, state: JointState) -> dict:
        """周期性下发控制参数：每 update_interval 步按全局压力重新分档一次。

        周期内返回上次缓存；每次重新下发打日志（step/avg_pressure/params）。

        Args:
            state: 当前联合状态（用于计算全局平均压力与判定下发周期）。

        Returns:
            控制参数 dict，含 min_green / max_green / base_green。
        """
        plan = self.plan(state, prediction=False, dispatch=True)
        self.commit(plan)
        params = plan.params()
        if params is None:
            raise RuntimeError("cloud_dispatch_plan_missing_params")
        return params

    def dispatch_base_green(self, state: JointState) -> float:
        """周期性下发 base_green 参数（云端全局协调）。"""
        return float(self.dispatch_params(state)["base_green"])

    def reset(self) -> None:
        """重置预测状态，用于新场景或重复实验。"""
        self._prev_predicted = {}
        self._prev_hourly_flow = {}
        self._flow_history = {}
        self._last_params = None
        self._last_dispatch_step = -10**9
        self._reset_epoch += 1
        self._runtime_revision = 0
        self._pending_plan = None
        self._committed_plan = None
        self.model_source = "ewma"
