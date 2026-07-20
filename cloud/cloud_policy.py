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
    """云端流量预测策略。"""

    def __init__(self, model_path: Optional[Path] = None) -> None:
        if model_path is None:
            model_path = get_config().path("paths.model_path")
        self.model_path = Path(model_path)
        self._model: Optional[object] = None
        self._load_model()

    def _load_model(self) -> None:
        """加载离线训练好的 ML 模型。"""
        if not self.model_path.exists():
            logger.warning("模型文件不存在: %s，将使用兜底预测", self.model_path)
            return

        try:
            import joblib

            self._model = joblib.load(self.model_path)
            logger.info("已加载云端模型: %s", self.model_path)
        except Exception as exc:
            logger.warning("加载模型失败: %s，将使用兜底预测", exc)

    def predict(self, state: JointState) -> PredictionResult:
        """预测未来各方向流量。

        若模型未加载成功，返回当前流量作为兜底，确保边缘算法仍可运行。
        """
        horizon = get_config().get("algorithms.ca_maxpressure.prediction_horizon", 300)

        if self._model is not None:
            # TODO: 调用 ml/features.py 生成特征向量，再调用 self._model.predict()
            # 当前返回兜底值，由成员3/成员4 后续替换为真实推理。
            predicted = state.flows
        else:
            predicted = state.flows

        return PredictionResult(
            horizon_steps=int(horizon),
            horizon_seconds=float(horizon),
            predicted_flows=predicted,
        )
