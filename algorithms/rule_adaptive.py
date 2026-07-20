"""规则自适应算法。

根据实时排队长度动态调整绿灯时长：
- 当前相位绿灯时间不足最小绿灯时，强制保持；
- 当前方向排队超过阈值且未达最大绿灯时，延长绿灯；
- 否则切换至下一相位。
"""

from __future__ import annotations

from typing import List

from algorithms.base import BaseControlAlgorithm
from core.config import get_config
from core.types import ControlAction, JointState, Scene


class RuleAdaptiveAlgorithm(BaseControlAlgorithm):
    """基于排队长度的规则自适应信号控制。"""

    def __init__(
        self,
        min_green: float | None = None,
        max_green: float | None = None,
        queue_threshold: float | None = None,
    ) -> None:
        cfg = get_config().get("algorithms.rule_adaptive", {})
        self.min_green = min_green if min_green is not None else cfg.get("min_green", 10)
        self.max_green = max_green if max_green is not None else cfg.get("max_green", 60)
        self.queue_threshold = (
            queue_threshold if queue_threshold is not None else cfg.get("queue_threshold", 5)
        )
        self.scene: Scene | None = None

    def init(self, scene: Scene) -> None:
        self.scene = scene

    def step(self, state: JointState) -> List[ControlAction]:
        if state.elapsed_phase_time < self.min_green:
            return []

        max_queue = max((q.queue_length for q in state.queues), default=0.0)

        # 排队严重且未达最大绿灯：延长当前相位。
        if max_queue > self.queue_threshold and state.elapsed_phase_time < self.max_green:
            return [
                ControlAction(
                    tls_id=state.tls_id,
                    action_type="set_phase_duration",
                    value=5.0,
                    reason="queue_high_extend_green",
                )
            ]

        # 排队不严重或已达最大绿灯：切换下一相位。
        # TODO: 后续根据实际相位数量取模，避免硬编码。
        next_phase = (state.current_phase + 1) % max(len(state.queues), 2)
        return [
            ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=next_phase,
                reason="queue_low_next_phase",
            )
        ]

    def reset(self) -> None:
        pass

    @property
    def name(self) -> str:
        return "rule_adaptive"
