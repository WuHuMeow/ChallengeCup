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
        self._prev_predicted: dict[str, float] = {}

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

    def dispatch_base_green(self, state: JointState) -> float:
        """周期性下发 base_green 参数（云端全局协调）。

        MVI：返回配置的固定 base_green。
        TODO(AB): 根据全局压力评估动态调整 base_green，
        实现 README 中"CloudCoordinator 根据全局压力周期性下发 base_green"。
        """
        cfg = get_config().get("algorithms.ca_maxpressure", {})
        return float(cfg.get("base_green", 30))

    def reset(self) -> None:
        """重置预测状态，用于新场景或重复实验。"""
        self._prev_predicted = {}
