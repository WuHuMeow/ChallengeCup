"""云端策略层：流量预测服务。

在赛道 B 单机实现中，用模块边界模拟云端：
- 离线训练产出 `ml/model.pkl`（scripts/train_ml.py，GradientBoosting 流量预测）；
- 在线推理封装在 CloudPolicy.predict() 中，模型优先、EWMA 回退；
- 边缘算法通过 CloudPolicy 获取未来流量预测。
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Optional

from core.config import get_config
from core.types import JointState, PredictionResult

logger = logging.getLogger(__name__)


def joint_state_fingerprint(state: JointState) -> tuple:
    """Immutable identity of one JointState for plan/commit transactions."""
    return (
        state.step,
        float(state.timestamp),
        state.tls_id,
        state.current_phase,
        float(state.elapsed_phase_time),
        tuple(sorted(state.flows.items())),
        tuple(
            (q.direction, q.queue_length, q.capacity) for q in state.queues
        ),
    )


@dataclass(frozen=True)
class CloudPolicyPlan:
    """Side-effect-free cloud decision awaiting commit."""

    state_fingerprint: tuple
    state_step: int
    prediction: Optional[PredictionResult]
    params: Optional[dict]
    observations: tuple[tuple[str, float, float], ...] = ()
    policy_revision: int = 0

    def prediction_result(self) -> Optional[PredictionResult]:
        return self.prediction


class CloudPolicy:
    """云端流量预测策略（GBR 模型优先，EWMA 指数加权移动平均回退）。"""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        cfg = get_config().get("algorithms.ca_maxpressure", {})
        self.alpha: float = cfg.get("ewma_alpha", 0.3)
        self.horizon: int = cfg.get("prediction_horizon", 300)
        self.update_interval: int = cfg.get("cloud_update_interval", 600)
        # Writable plain attribute: the capacity layer may inject a frozen
        # prediction weight without mutating policy defaults elsewhere.
        self.configured_prediction_weight: float = float(
            cfg.get("prediction_weight", 0.0)
        )
        self._prev_predicted: dict[str, float] = {}
        self._prev_hourly_flow: dict[str, float] = {}
        self._last_params: Optional[dict] = None
        self._last_dispatch_step: int = -10**9
        self._flow_history: dict[str, Deque[tuple[float, float]]] = {}
        self._model_used: bool = False
        self._runtime_revision: int = 0

        if model_path is None:
            model_path = get_config().path("paths.model_path")
        self.model_path = Path(model_path)
        self._model: Optional[dict] = None
        self.model_source: str = "ewma"
        self._load_model()

    def _load_model(self) -> None:
        """加载离线训练好的 GBR 流量预测模型；失败时回退 EWMA。"""
        from ml.train import load_flow_model

        payload = load_flow_model(self.model_path)
        if payload is not None:
            self._model = payload
            logger.info("已加载云端流量预测模型: %s", self.model_path)

    def _observation(self, state: JointState) -> dict[str, tuple[float, float]]:
        """每个方向的 (flow veh/h, 总排队) 当前观测。

        方向集以 state.flows 为准（云端预测的输入是到达率）；
        queues 仅提供同方向排队长度（缺失记 0）。
        """
        queues: dict[str, float] = {}
        for queue in state.queues:
            queues[queue.direction] = queues.get(queue.direction, 0.0) + queue.queue_length
        directions = dict.fromkeys(state.flows)
        for direction in queues:
            directions.setdefault(direction)
        return {
            direction: (float(state.flows.get(direction, 0.0)), queues.get(direction, 0.0))
            for direction in directions
        }

    def _predict_with_model(
        self, state: JointState, observations: dict[str, tuple[float, float]]
    ) -> Optional[dict[str, float]]:
        """全部方向都有滞后历史时用 GBR 逐方向预测；否则返回 None。"""
        from ml.features import build_flow_feature_row
        from ml.train import predict_flow

        if not observations:
            return None
        avg_queue = (
            sum(q.queue_length for q in state.queues) / len(state.queues)
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

    def predict(self, state: JointState) -> PredictionResult:
        """流量预测：GBR 模型优先（需各方向滞后历史），EWMA 回退。

        一次 predict() 等价于一次完整事务：plan（无副作用）→ commit（推进
        veh/h EWMA 历史与模型观测历史）。输出为 horizon 窗口内车辆数。
        """
        plan = self.plan(state, prediction=True, dispatch=False)
        self.commit(plan)
        self.model_source = "model" if self._model is not None and self._model_used else "ewma"
        prediction = plan.prediction
        assert prediction is not None
        return prediction

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
        pressure = self.avg_pressure(state)
        if (
            self._last_params is None
            or state.step - self._last_dispatch_step >= self.update_interval
        ):
            self._last_params = self._compute_params(pressure)
            self._last_dispatch_step = state.step
            logger.info("云端下发参数: step=%d avg_pressure=%.3f params=%s",
                        state.step, pressure, self._last_params)
        return dict(self._last_params)

    def dispatch_base_green(self, state: JointState) -> float:
        """周期性下发 base_green 参数（云端全局协调）。"""
        return float(self.dispatch_params(state)["base_green"])

    def reset(self) -> None:
        """重置预测状态，用于新场景或重复实验。"""
        self._prev_predicted = {}
        self._prev_hourly_flow = {}
        self._last_params = None
        self._last_dispatch_step = -10**9
        self._flow_history = {}
        self._model_used = False
        self._runtime_revision += 1
        self.model_source = "ewma"

    @property
    def prediction_weight(self) -> float:
        """Alias kept for callers reading the configured weight."""
        return self.configured_prediction_weight

    def plan(
        self,
        state: JointState,
        *,
        prediction: bool = True,
        dispatch: bool = False,
    ) -> CloudPolicyPlan:
        """无副作用地规划一次云端决策；commit() 才推进内部状态。"""
        observations = self._observation(state)
        predicted: Optional[PredictionResult] = None
        if prediction:
            flows = self._plan_flows(state, observations)
            predicted = PredictionResult(
                horizon_steps=self.horizon,
                horizon_seconds=float(self.horizon),
                predicted_flows=flows,
            )
        params = self._plan_params(state) if dispatch else None
        return CloudPolicyPlan(
            state_fingerprint=joint_state_fingerprint(state),
            state_step=state.step,
            prediction=predicted,
            params=params,
            policy_revision=self._runtime_revision,
            observations=tuple(
                (direction, flow, queue)
                for direction, (flow, queue) in observations.items()
            ),
        )

    def _plan_flows(
        self,
        state: JointState,
        observations: dict[str, tuple[float, float]],
    ) -> dict[str, float]:
        """流量预测（纯计算，不写历史）。

        EWMA 递推在 veh/h 域进行并保存（_prev_hourly_flow）；
        输出换算为 horizon 窗口内的车辆数（veh/h × horizon/3600）。
        """
        scale = float(self.horizon) / 3600.0
        if self._model is not None:
            try:
                hourly = self._predict_with_model(state, observations)
            except (ValueError, TypeError) as exc:
                logger.warning("模型预测失败，回退 EWMA: %s", exc)
                hourly = None
            if hourly is not None:
                self._model_used = True
                return {d: v * scale for d, v in hourly.items()}
            self._model_used = False
        planned: dict[str, float] = {}
        for direction, (flow, _queue) in observations.items():
            previous = self._prev_hourly_flow.get(direction, flow)
            hourly = self.alpha * flow + (1 - self.alpha) * previous
            planned[direction] = hourly * scale
        self._model_used = False
        return planned

    def _plan_params(self, state: JointState) -> dict:
        """按当前压力计算下发参数（不更新缓存）。"""
        return self._compute_params(self.avg_pressure(state))

    def validate_plan(self, plan: CloudPolicyPlan) -> bool:
        """Validate a pending cloud plan belongs to this policy transaction."""
        if not isinstance(plan, CloudPolicyPlan):
            raise RuntimeError("cloud_plan_invalid_type")
        if plan.policy_revision != self._runtime_revision:
            raise RuntimeError("cloud_plan_post_reset")
        return True

    def commit(self, plan: CloudPolicyPlan) -> None:
        """Apply a planned decision: advance prediction history and params."""
        if not self.validate_plan(plan):
            return
        if plan.prediction is not None:
            scale = float(self.horizon) / 3600.0
            self._prev_predicted = dict(plan.prediction.predicted_flows)
            # EWMA history stays in veh/h so consecutive forecasts do not
            # compound the horizon conversion.
            self._prev_hourly_flow = {
                direction: value / scale
                for direction, value in plan.prediction.predicted_flows.items()
            }
            for direction, flow, queue in plan.observations:
                history = self._flow_history.setdefault(direction, deque(maxlen=2))
                history.append((flow, queue))
        if plan.params is not None:
            self._last_params = dict(plan.params)
            self._last_dispatch_step = plan.state_step
            logger.info(
                "云端下发参数: step=%d avg_pressure params=%s",
                plan.state_step,
                self._last_params,
            )
