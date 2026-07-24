"""云端策略层：流量预测服务。

在赛道 B 单机实现中，用模块边界模拟云端：
- 离线训练产出 `ml/model.pkl`；
- 在线推理封装在 CloudPolicy.predict() 中；
- 边缘算法通过 CloudPolicy 获取未来流量预测。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from core.config import get_config
from core.types import JointState, PredictionResult

logger = logging.getLogger(__name__)


class CloudPolicy:
    """云端流量预测策略（EWMA 指数加权移动平均）。"""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        cfg = get_config().get("algorithms.ca_maxpressure", {})
        self.alpha: float = cfg.get("ewma_alpha", 0.3)
        self.horizon: int = cfg.get("prediction_horizon", 300)
        self.update_interval: int = cfg.get("cloud_update_interval", 60)
        self._prev_predicted: dict[str, float] = {}
        self._last_params: Optional[dict] = None
        self._last_dispatch_step: int = -10**9

        if model_path is None:
            model_path = get_config().path("paths.model_path")
        self.model_path = Path(model_path)
        self._model: Optional[object] = None
        self._load_model()

    def _load_model(self) -> None:
        """加载离线训练好的 ML 模型（可选，XGBoost 扩展用）。"""
        if not self.model_path.exists():
            return

        try:
            import joblib

            loaded = joblib.load(self.model_path)
            if loaded is not None:
                self._model = loaded
                logger.info("已加载云端模型: %s", self.model_path)
        except Exception as exc:
            logger.warning("加载模型失败: %s，将使用 EWMA 预测", exc)

    def predict(self, state: JointState) -> PredictionResult:
        """EWMA 流量预测：predicted(t+1) = α × observed(t) + (1-α) × predicted(t)。"""
        predicted: dict[str, float] = {}
        for direction, observed in state.flows.items():
            prev = self._prev_predicted.get(direction, observed)
            predicted[direction] = self.alpha * observed + (1 - self.alpha) * prev

        self._prev_predicted = predicted

        return PredictionResult(
            horizon_steps=self.horizon,
            horizon_seconds=float(self.horizon),
            predicted_flows=predicted,
        )

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
        self._last_params = None
        self._last_dispatch_step = -10**9
