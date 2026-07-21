"""CA-MP（Capacity-Aware MaxPressure）容量感知最大压力控制算法。

核心创新三项改进：
1. 容量归一化压力：pressure = queue / capacity，短车道自动获得高优先级；
2. 溢出门控：进口道占用率 > 阈值时强制放行，防止窄路死锁；
3. 云端动态绿灯：CloudCoordinator 根据全局压力周期性下发 base_green，
   边缘按压力比例动态分配绿灯时长。

云-边协同实现：
- 边缘层提取本地排队特征；
- 调用云端 CloudPolicy.predict() 获取未来流量预测（EWMA）；
- 融合预测结果与本地排队状态，生成信号配时动作。
"""

from __future__ import annotations

from typing import List

from algorithms.base import BaseControlAlgorithm
from cloud.cloud_policy import CloudPolicy
from core.config import get_config
from core.types import ControlAction, JointState, Scene


class CAMaxPressureAlgorithm(BaseControlAlgorithm):
    """容量感知最大压力控制器（CA-MP，核心创新）。"""

    def __init__(self, cloud_policy: CloudPolicy | None = None) -> None:
        cfg = get_config().get("algorithms.ca_maxpressure", {})
        self.cloud_policy = cloud_policy or CloudPolicy()
        self.scene: Scene | None = None
        self.overflow_threshold: float = cfg.get("overflow_occupancy_threshold", 0.9)
        self.base_green: float = cfg.get("base_green", 30)
        self.min_green: float = cfg.get("min_green", 10)
        self.max_green: float = cfg.get("max_green", 90)

    def init(self, scene: Scene) -> None:
        self.scene = scene

    def step(self, state: JointState) -> List[ControlAction]:
        pred = self.cloud_policy.predict(state)

        if not state.queues:
            return []

        # --- MVI: 最小可运行实现，验证接口闭环 ---
        # 选择排队最长的方向，输出 set_phase 动作。
        # 后续正式实现将替换此段逻辑，接口不变。

        # TODO(AB): 容量归一化压力 — pressure = queue_length / capacity
        #   需要 QueueState 扩展 capacity 字段或从 SceneMeta 获取车道容量。
        # TODO(AB): 溢出门控 — occupancy > self.overflow_threshold 时强制放行
        #   需要检测器占用率数据（state.detector_values 或 QueueState 扩展）。
        # TODO(AB): 云端动态绿灯 — base_green * (phase_pressure / avg_pressure)
        #   融合 pred.predicted_flows 修正压力值，clamp(duration, min_green, max_green)。

        best_queue = max(state.queues, key=lambda q: q.queue_length)

        return [
            ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=best_queue.direction,
                reason=f"MVI: 最大排队方向 {best_queue.direction}",
            )
        ]

    def reset(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "ca_maxpressure"
