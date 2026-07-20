"""TraCI 批量读写封装。

职责：把 SUMO 的底层 TraCI 调用转换为项目统一的 `JointState` 和 `ControlAction`，
让算法层无需直接依赖 traci 细节。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from core.types import ControlAction, JointState, QueueState

logger = logging.getLogger(__name__)

# 兼容本地 SUMO 安装：若通过 pip 安装 traci 则无需 SUMO_HOME。
if "SUMO_HOME" in os.environ:
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))

try:
    import traci
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "无法导入 traci。请安装 SUMO 并设置 SUMO_HOME 环境变量，"
        "或在虚拟环境中执行 `pip install traci>=1.18.0`。"
    ) from exc


class TraCIBridge:
    """SUMO 仿真与算法之间的桥接器。"""

    def __init__(self, sumo_cfg: Path, binary: str = "sumo") -> None:
        self.sumo_cfg = Path(sumo_cfg)
        self.binary = binary
        self.tls_id: Optional[str] = None
        self._controlled_lanes: List[str] = []

    def start(self) -> None:
        """启动 SUMO 仿真进程。"""
        if not self.sumo_cfg.exists():
            raise FileNotFoundError(f"SUMO 配置文件不存在: {self.sumo_cfg}")

        cmd = [self.binary, "-c", str(self.sumo_cfg), "--no-step-log", "true"]
        logger.info("启动 SUMO: %s", " ".join(cmd))
        traci.start(cmd)

        tls_ids = traci.trafficlight.getIDList()
        if not tls_ids:
            raise RuntimeError("场景中没有信号灯，无法运行交通控制算法")
        self.tls_id = tls_ids[0]
        self._controlled_lanes = list(traci.trafficlight.getControlledLanes(self.tls_id))
        logger.info("控制信号灯: %s, 控制车道数: %d", self.tls_id, len(self._controlled_lanes))

    def close(self) -> None:
        """关闭 SUMO 仿真进程。"""
        if traci.isLoaded():
            traci.close()

    def step(self) -> float:
        """推进一个仿真步，返回当前仿真时间。"""
        traci.simulationStep()
        return traci.simulation.getTime()

    def get_state(self) -> JointState:
        """读取当前联合状态。"""
        if self.tls_id is None:
            raise RuntimeError("TraCIBridge 尚未 start()")

        step = int(traci.simulation.getTime())
        current_phase = traci.trafficlight.getPhase(self.tls_id)
        program = traci.trafficlight.getAllProgramLogics(self.tls_id)[0]
        phase_obj = program.phases[current_phase]
        phase_name = getattr(phase_obj, "name", f"phase_{current_phase}")
        elapsed = traci.trafficlight.getPhaseDuration(self.tls_id) - traci.trafficlight.getNextSwitch(self.tls_id) + traci.simulation.getTime()

        queues: List[QueueState] = []
        flows: dict[str, float] = {}
        for lane_id in self._controlled_lanes:
            # 用 lane_id 本身作为方向标识； teammates 后续可按路口几何映射为 north/south/east/west。
            direction = lane_id
            queue_length = traci.lane.getLastStepHaltingNumber(lane_id)
            waiting_time = traci.lane.getWaitingTime(lane_id)
            vehicle_count = traci.lane.getLastStepVehicleNumber(lane_id)
            queues.append(
                QueueState(
                    direction=direction,
                    queue_length=float(queue_length),
                    waiting_time=waiting_time,
                    vehicle_count=vehicle_count,
                )
            )
            # 流量近似：当前车辆数 × 3600（后续可改为检测器计数）
            flows[direction] = float(vehicle_count) * 3600.0

        return JointState(
            step=step,
            timestamp=float(step),
            tls_id=self.tls_id,
            current_phase=current_phase,
            current_phase_name=phase_name,
            elapsed_phase_time=float(elapsed),
            queues=queues,
            flows=flows,
            detector_values={},
        )

    def apply_actions(self, actions: List[ControlAction]) -> None:
        """将算法输出的控制动作写入 SUMO。"""
        for action in actions:
            if action.action_type == "set_phase":
                traci.trafficlight.setPhase(action.tls_id, int(action.value))
            elif action.action_type == "set_phase_duration":
                traci.trafficlight.setPhaseDuration(action.tls_id, float(action.value))
            elif action.action_type == "set_program":
                traci.trafficlight.setProgram(action.tls_id, str(action.value))
            else:
                logger.warning("未知控制动作类型: %s", action.action_type)
