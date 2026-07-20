"""ML 增强算法。

云-边协同实现：
1. 边缘层提取本地特征；
2. 调用云端 CloudPolicy.predict() 获取未来流量预测；
3. 融合预测结果与本地排队状态，生成信号配时动作。
"""

from __future__ import annotations

from typing import List

from algorithms.base import BaseControlAlgorithm
from cloud.cloud_policy import CloudPolicy
from core.config import get_config
from core.types import ControlAction, JointState, Scene


class MLEnhancedAlgorithm(BaseControlAlgorithm):
    """ML 增强的交通信号控制算法。"""

    def __init__(self, cloud_policy: CloudPolicy | None = None) -> None:
        self.cloud_policy = cloud_policy or CloudPolicy()
        self.scene: Scene | None = None

    def init(self, scene: Scene) -> None:
        self.scene = scene

    def step(self, state: JointState) -> List[ControlAction]:
        # 1. 获取云端预测
        pred = self.cloud_policy.predict(state)

        # 2. TODO: 成员3 在此实现预测 + 排队融合决策逻辑。
        # 示例思路：
        # - 对预测流量高的方向预分配更多绿灯时间；
        # - 结合当前排队进行动态微调。

        # 当前为可运行骨架，不输出动作，避免干扰默认配时。
        return []

    def reset(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "ml_enhanced"
