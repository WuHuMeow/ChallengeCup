"""V2X 边缘通道：消息过滤 + 固定步数延迟模拟（PDF 加分项）。

模拟 V2X 消息的发送、接收与简单延迟：
- 车端/灯端通过 send() 把 JointState 投入通道；
- 边缘控制器通过 receive() 取回 delay_steps 步前发送的消息（不足则 None）；
- allowed_directions 非空时，消息在入通道前按方向过滤（消息过滤）。
"""

from __future__ import annotations

import dataclasses
import logging
from collections import deque
from typing import Deque, List, Optional

from core.types import JointState

logger = logging.getLogger(__name__)


class EdgeChannel:
    """带过滤与固定延迟的 V2X 消息通道。

    Args:
        delay_steps: 固定延迟步数；receive() 返回 delay_steps 步前发送的消息。
        allowed_directions: 允许通过的方向列表；None 表示不过滤。
    """

    def __init__(
        self,
        delay_steps: int = 1,
        allowed_directions: Optional[List[str]] = None,
    ) -> None:
        self.delay_steps = max(0, int(delay_steps))
        self.allowed_directions = allowed_directions
        self._buffer: Deque[JointState] = deque()

    def send(self, state: JointState) -> None:
        """发送状态消息入通道（可选方向过滤）。

        Args:
            state: 待发送的联合状态；allowed_directions 非空时先按方向过滤。
        """
        if self.allowed_directions is not None:
            allowed = set(self.allowed_directions)
            state = dataclasses.replace(
                state,
                queues=[q for q in state.queues if q.direction in allowed],
                flows={d: f for d, f in state.flows.items() if d in allowed},
            )
        self._buffer.append(state)

    def receive(self) -> Optional[JointState]:
        """接收 delay_steps 步前发送的消息。

        Returns:
            delay_steps 步前入通道的 JointState；缓冲不足（延迟未满）时返回 None。
        """
        if len(self._buffer) <= self.delay_steps:
            return None
        return self._buffer.popleft()
