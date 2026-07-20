"""仿真数据采集器。

每个仿真步将 JointState 和指标写入 CSV，供 ML 训练与实验分析使用。
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List

from core.types import JointState, SimulationMetrics

logger = logging.getLogger(__name__)


class MetricsCollector:
    """按步采集仿真状态与指标，输出 CSV。"""

    def __init__(self, output_file: Path) -> None:
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self._rows: List[dict] = []

    def record(self, step: int, state: JointState, metrics: SimulationMetrics) -> None:
        """记录单步数据。"""
        row = {
            "step": step,
            "timestamp": state.timestamp,
            "tls_id": state.tls_id,
            "current_phase": state.current_phase,
            "avg_queue_length": metrics.avg_queue_length,
            "max_queue_length": metrics.max_queue_length,
            "avg_delay": metrics.avg_delay,
            "total_throughput": metrics.total_throughput,
            "avg_travel_time": metrics.avg_travel_time,
            "total_stops": metrics.total_stops,
            "fuel_consumption": metrics.fuel_consumption,
        }
        # 展开排队状态：lane -> queue_length
        for q in state.queues:
            row[f"queue_{q.direction}"] = q.queue_length
            row[f"flow_{q.direction}"] = state.flows.get(q.direction, 0.0)
        self._rows.append(row)

    def save(self) -> None:
        """将缓存写入 CSV 文件。"""
        if not self._rows:
            logger.warning("没有数据可保存")
            return

        fieldnames = list(self._rows[0].keys())
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._rows)

        logger.info("已保存 %d 条记录到 %s", len(self._rows), self.output_file)
