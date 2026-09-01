"""特征工程。

将 JointState 转换为 ML 模型可用的特征字典；
并提供训练/推理共享的方向级流量特征契约。
"""

from __future__ import annotations

from typing import Dict

from core.types import JointState

# 方向级流量预测特征（训练与在线推理共用同一顺序）。
FEATURE_NAMES = (
    "flow_t",
    "flow_lag1",
    "queue_t",
    "queue_lag1",
    "avg_queue_t",
    "phase",
)


def build_flow_feature_row(
    flow_t: float,
    flow_lag1: float,
    queue_t: float,
    queue_lag1: float,
    avg_queue_t: float,
    phase: int,
) -> Dict[str, float]:
    """构造一个方向级特征行，字段顺序与 FEATURE_NAMES 一致。"""
    return {
        "flow_t": float(flow_t),
        "flow_lag1": float(flow_lag1),
        "queue_t": float(queue_t),
        "queue_lag1": float(queue_lag1),
        "avg_queue_t": float(avg_queue_t),
        "phase": float(phase),
    }


def extract_features(state: JointState, window: int = 5) -> Dict[str, list]:
    """从当前状态提取特征字典。

    Args:
        state: 当前联合状态。
        window: 滑动窗口大小（预留，当前未使用历史）。

    Returns:
        特征字典，包含 queue_lengths 和 flows。

    TODO(AB): 补充历史窗口、时段编码、相位 one-hot 等特征。
    """
    return {
        "queue_lengths": [q.queue_length for q in state.queues],
        "flows": [state.flows.get(q.direction, 0.0) for q in state.queues],
        "waiting_times": [q.waiting_time for q in state.queues],
        "current_phase": [state.current_phase],
    }
