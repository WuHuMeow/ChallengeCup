"""特征工程。

将 `JointState` 和 CSV 历史数据转换为 ML 模型可用的特征向量。
"""

from __future__ import annotations

from typing import List

import numpy as np

from core.types import JointState


def extract_features(state: JointState, history: List[JointState] | None = None) -> np.ndarray:
    """从当前状态和可选的历史状态中提取特征向量。

    当前骨架使用简化特征：
    - 各方向当前排队长度
    - 各方向当前流量
    - 当前相位 one-hot（占位，后续完善）

    Args:
        state: 当前联合状态。
        history: 前若干步历史状态，用于滑动窗口特征。

    Returns:
        1D 特征向量。
    """
    queue_features = [q.queue_length for q in state.queues]
    flow_features = [state.flows.get(q.direction, 0.0) for q in state.queues]
    # TODO: 成员4 补充历史窗口、时段编码、相位 one-hot 等特征。
    return np.array(queue_features + flow_features, dtype=np.float32)


def extract_labels(future_states: List[JointState]) -> np.ndarray:
    """根据未来状态生成标签：未来 horizon 内各方向总流量。"""
    # TODO: 按方向聚合未来流量作为回归标签。
    return np.zeros(len(future_states), dtype=np.float32)
