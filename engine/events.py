"""仿真事件日志（events.csv）。

记录运行生命周期与算法控制动作；AB 实现溢出门控后，
其 ControlAction 会自动进入事件流（机制先行）。
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class EventLogger:
    """事件行：step / type / detail。

    Args:
        output_file: 输出 CSV 路径（父目录自动创建）。
    """

    def __init__(self, output_file: Path) -> None:
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self._rows: List[dict] = []

    def log(self, step: int, event_type: str, detail: str) -> None:
        """记录一条事件。

        Args:
            step: 事件发生的仿真步。
            event_type: 事件类型（run_start/run_end/控制动作类型等）。
            detail: 事件详情（动作值或原因说明）。
        """
        self._rows.append({"step": step, "type": event_type, "detail": detail})

    def save(self) -> None:
        """写入 CSV 文件；无事件时为 no-op。"""
        if not self._rows:
            logger.warning("没有数据可保存")
            return
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["step", "type", "detail"])
            writer.writeheader()
            writer.writerows(self._rows)
        logger.info("已保存 %d 条事件到 %s", len(self._rows), self.output_file)
