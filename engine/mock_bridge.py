"""离线模拟桥接器。

提供与 TraCIBridge 相同的公共接口，但无需安装 SUMO 即可运行。
用于单元测试、CI 环境以及无 SUMO 依赖的离线开发场景。
所有返回数据均为确定性数据（无随机性），确保测试结果可复现。
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from core.types import ControlAction, JointState, QueueState

logger = logging.getLogger(__name__)

DEFAULT_DIRECTIONS: List[str] = ["north", "south", "east", "west"]


class MockBridge:
    """TraCIBridge 的离线替代实现，接口完全一致。"""

    def __init__(
        self,
        tls_id: str = "tls_0",
        directions: Optional[List[str]] = None,
        step_length: float = 1.0,
    ) -> None:
        self.tls_id = tls_id
        self.directions = directions or list(DEFAULT_DIRECTIONS)
        self.step_length = step_length
        self._current_step: int = 0
        self._started: bool = False
        self._applied_actions: List[ControlAction] = []

    def start(self) -> None:
        """模拟启动，标记桥接器为已启动状态。"""
        self._started = True
        logger.info("MockBridge 已启动, tls_id=%s, directions=%s", self.tls_id, self.directions)

    def close(self) -> None:
        """模拟关闭，重置启动状态。"""
        self._started = False
        logger.info("MockBridge 已关闭")

    def step(self) -> float:
        """推进一个仿真步，返回当前仿真时间。"""
        self._current_step += 1
        current_time = self._current_step * self.step_length
        return current_time

    def get_state(self) -> JointState:
        """返回确定性的模拟联合状态。"""
        queues: List[QueueState] = []
        flows: Dict[str, float] = {}

        for i, direction in enumerate(self.directions):
            # 确定性数据：基于步数和方向索引生成固定模式
            queue_length = float((self._current_step + i * 3) % 20)
            waiting_time = float((self._current_step + i * 5) % 30)
            vehicle_count = (self._current_step + i * 2) % 15
            queues.append(
                QueueState(
                    direction=direction,
                    queue_length=queue_length,
                    waiting_time=waiting_time,
                    vehicle_count=vehicle_count,
                )
            )
            flows[direction] = float(vehicle_count) * 3600.0

        current_phase = self._current_step % 4
        return JointState(
            step=self._current_step,
            timestamp=float(self._current_step) * self.step_length,
            tls_id=self.tls_id,
            current_phase=current_phase,
            current_phase_name=f"phase_{current_phase}",
            elapsed_phase_time=float(self._current_step % 30),
            queues=queues,
            flows=flows,
            detector_values={},
        )

    def apply_actions(self, actions: List[ControlAction]) -> None:
        """记录控制动作（无实际操作）。"""
        for action in actions:
            logger.debug(
                "MockBridge 收到动作: tls_id=%s, type=%s, value=%s",
                action.tls_id,
                action.action_type,
                action.value,
            )
        self._applied_actions.extend(actions)
