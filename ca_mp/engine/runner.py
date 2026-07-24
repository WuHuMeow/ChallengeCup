"""单次仿真运行器。

封装 SUMO 生命周期：启动 → 逐步运行 → 算法决策 → 采集指标 → 关闭。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from algorithms.base import BaseControlAlgorithm
from core.config import get_config
from core.types import ControlAction, Scene
from engine.collector import MetricsCollector, StepLogger
from engine.events import EventLogger
from engine.traci_bridge import TraCIBridge, traci
from experiments.metrics import compute_metrics

logger = logging.getLogger(__name__)


class SimulationRunner:
    """单次仿真实验运行器。"""

    def __init__(
        self,
        scene: Scene,
        algorithm: BaseControlAlgorithm,
        sumo_binary: Optional[str] = None,
        output_csv: Optional[Path] = None,
        snapshot_interval: Optional[int] = None,
        additional_files: Optional[List[Path]] = None,
        bridge: Optional[object] = None,
        seed: Optional[int] = None,
        step_log_csv: Optional[Path] = None,
        events_csv: Optional[Path] = None,
    ) -> None:
        self.scene = scene
        self.algorithm = algorithm
        self.seed = seed
        self.sumo_binary = sumo_binary or get_config().get("sumo.binary", "sumo")
        self.snapshot_interval = snapshot_interval or get_config().get(
            "metrics.snapshot_interval", 60
        )
        self.additional_files = additional_files or []

        if output_csv is None:
            output_root = Path(get_config().get("paths.output_root", "./output"))
            output_csv = (
                output_root
                / "csv"
                / f"{scene.meta.intersection_id}_{algorithm.name}.csv"
            )
        self.output_csv = output_csv

        if bridge is not None:
            self.bridge = bridge
        else:
            # 优先使用 engine/configs/ 下的增强版配置（IA W2：含 tripinfo/fcd/summary
            # 输出，引用只读原始数据）；不存在时回退原始 sumocfg。
            cfg = scene.meta.sumo_cfg
            enhanced = (
                Path(__file__).resolve().parent
                / "configs"
                / f"demo_{scene.meta.intersection_id}.sumocfg"
            )
            if enhanced.exists():
                cfg = enhanced
            self.bridge = TraCIBridge(
                cfg,
                binary=self.sumo_binary,
                additional_files=self.additional_files,
                seed=self.seed,
            )
        self.collector: Optional[MetricsCollector] = None
        self.metrics_history: List[dict] = []
        self.step_logger = StepLogger(step_log_csv) if step_log_csv else None
        self.event_logger = EventLogger(events_csv) if events_csv else None

    def run(self, steps: Optional[int] = None) -> List[dict]:
        """运行完整仿真并返回指标历史。

        Args:
            steps: 仿真步数；None 时使用配置 sumo.default_simulation_steps。

        Returns:
            指标快照列表（每 snapshot_interval 步一条），含 avg_queue_length /
            max_queue_length / avg_delay / total_throughput。
        """
        steps = steps or get_config().get("sumo.default_simulation_steps", 3600)
        self.collector = MetricsCollector(self.output_csv)
        self.metrics_history = []

        try:
            # 先启动 SUMO，让算法 init() 可以查询信号灯状态并写入配时方案。
            self.bridge.start()
            self.algorithm.init(self.scene)
            if self.event_logger:
                self.event_logger.log(
                    0, "run_start",
                    f"intersection={self.scene.meta.intersection_id}"
                    f" algorithm={self.algorithm.name}",
                )
            for step in range(steps):
                if not self._tick(step):
                    break
        finally:
            self.bridge.close()
            if self.collector:
                self.collector.save()
            if self.step_logger:
                self.step_logger.save()
            if self.event_logger:
                self.event_logger.log(
                    len(self.metrics_history), "run_end",
                    f"snapshots={len(self.metrics_history)}",
                )
                self.event_logger.save()

        return self.metrics_history

    def _tick(self, step: int) -> bool:
        """单个仿真步；返回 False 表示仿真已断开，应停止。"""
        try:
            state = self.bridge.get_state()
            actions: List[ControlAction] = self.algorithm.step(state)
            self.bridge.apply_actions(actions)
            if self.event_logger:
                for action in actions:
                    self.event_logger.log(
                        step, action.action_type, action.reason or str(action.value)
                    )
            sim_time = self.bridge.step()
        except traci.exceptions.FatalTraCIError as exc:
            # SUMO 进程被杀时，异常可能从 get_state 等任意 TraCI 调用抛出。
            logger.error("TraCI 连接断开: %s; closing gracefully", exc)
            return False
        if sim_time is None:
            logger.warning("仿真在 step %d 断开，提前结束", step)
            return False

        if self.step_logger:
            self.step_logger.record(step, state)

        # 记录间隔快照，避免 CSV 过大。
        if step % self.snapshot_interval == 0:
            metrics = compute_metrics(step, state)
            self.collector.record(step, state, metrics)
            self.metrics_history.append(
                {
                    "step": step,
                    "avg_queue_length": metrics.avg_queue_length,
                    "max_queue_length": metrics.max_queue_length,
                    "avg_delay": metrics.avg_delay,
                    "total_throughput": metrics.total_throughput,
                }
            )
        return True

    def __enter__(self) -> "SimulationRunner":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.bridge.close()
