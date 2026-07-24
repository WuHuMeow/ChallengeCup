"""TraCI 批量读写封装。

职责：把 SUMO 的底层 TraCI 调用转换为项目统一的 `JointState` 和 `ControlAction`，
让算法层无需直接依赖 traci 细节。
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections import deque
from pathlib import Path
from typing import List, Optional

from core.types import ControlAction, JointState, QueueState, VehicleState

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
    """SUMO 仿真与算法之间的桥接器。

    封装 SUMO 进程生命周期与 TraCI 读写，向算法层屏蔽 traci 细节。

    Args:
        sumo_cfg: SUMO 配置文件（.sumocfg）路径。
        binary: SUMO 可执行文件名（sumo 或 sumo-gui）。
        additional_files: 追加的 SUMO 附加文件（如变体流量 rou.xml）。
        seed: 随机种子，非 None 时传入 traci.start --seed 保证可复现。
        max_restarts: TraCI 连接断开时的最大自动重连次数。
        vehicle_sample_rate: 车辆快照采样率（每 N 辆取 1 辆）。
    """

    LANE_CAPACITY_METERS = 7.5  # 5m 车长 + 2.5m 间距，CA-MP 压力归一化分母
    MAX_VEHICLES = 500  # JointState.vehicles 硬上限（W4）

    def __init__(
        self,
        sumo_cfg: Path,
        binary: str = "sumo",
        additional_files: Optional[List[Path]] = None,
        seed: Optional[int] = None,
        max_restarts: int = 0,
        vehicle_sample_rate: int = 1,
    ) -> None:
        self.sumo_cfg = Path(sumo_cfg)
        self.binary = binary
        self.additional_files = list(additional_files or [])
        self.seed = seed
        self.max_restarts = max(0, int(max_restarts))
        self._restarts = 0
        self.tls_id: Optional[str] = None
        self._controlled_lanes: List[str] = []
        self._inbound_lanes: Optional[List[str]] = None  # edge_mapping 进口道筛选结果
        self.lane_directions: dict[str, str] = {}  # lane_id -> 方位（供 AB 压力映射）
        self.vehicle_sample_rate = max(1, int(vehicle_sample_rate))
        self._arrival_window: deque[int] = deque(maxlen=300)  # 滚动 300 步到达历史

    def _build_cmd(self) -> List[str]:
        """组装 traci.start 命令（含可选 --seed 与 additional files）。"""
        cmd = [self.binary, "-c", str(self.sumo_cfg), "--no-step-log", "true"]
        if self.seed is not None:
            cmd += ["--seed", str(self.seed)]
        if self.additional_files:
            cmd += ["-a", ",".join(str(f) for f in self.additional_files)]
        return cmd

    def start(self) -> None:
        """启动 SUMO 仿真进程。

        Raises:
            FileNotFoundError: sumo_cfg 配置文件不存在。
            RuntimeError: 场景中没有信号灯，无法运行交通控制算法。
        """
        if not self.sumo_cfg.exists():
            raise FileNotFoundError(f"SUMO 配置文件不存在: {self.sumo_cfg}")

        cmd = self._build_cmd()
        logger.info("启动 SUMO: %s", " ".join(cmd))
        traci.start(cmd)

        tls_ids = traci.trafficlight.getIDList()
        if not tls_ids:
            raise RuntimeError("场景中没有信号灯，无法运行交通控制算法")
        self.tls_id = tls_ids[0]
        self._controlled_lanes = list(traci.trafficlight.getControlledLanes(self.tls_id))
        logger.info("控制信号灯: %s, 控制车道数: %d", self.tls_id, len(self._controlled_lanes))
        self._load_edge_mapping()

    def _load_edge_mapping(self) -> None:
        """加载 data/intersection_data/metadata/edge_mapping.json 并筛选进口道。

        路口编号从 sumocfg 文件名 demo_<n>.sumocfg 解析；JSON 缺失/无匹配时
        回退 getControlledLanes（打 warning，不中断）。
        """
        match = re.search(r"demo_(\d+)", self.sumo_cfg.stem)
        if not match:
            logger.warning("无法从 %s 解析路口编号，回退 getControlledLanes", self.sumo_cfg)
            return
        from core.config import get_config
        path = Path(get_config().path("paths.data_root")) / "metadata" / "edge_mapping.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("edge_mapping.json 不可用(%s)，回退 getControlledLanes: %s", path, exc)
            return
        edges = data.get(match.group(1), {}).get("edges", {})
        self._apply_edge_mapping(edges)

    def _apply_edge_mapping(self, edges: dict) -> None:
        """按 edge_mapping 筛选进口车道并建立 lane -> 方位映射（纯方法，可单测）。"""
        inbound: List[str] = []
        for edge_id, info in edges.items():
            if info.get("kind") != "entry":
                continue
            for i in range(int(info.get("lanes", 0))):
                lane_id = f"{edge_id}_{i}"
                if lane_id in self._controlled_lanes:
                    inbound.append(lane_id)
                    self.lane_directions[lane_id] = info.get("direction", "")
        if inbound:
            self._inbound_lanes = inbound
            logger.info("进口道筛选: %d/%d 车道", len(inbound), len(self._controlled_lanes))
        else:
            logger.warning("edge_mapping 无进口边命中，回退 getControlledLanes")

    def close(self) -> None:
        """关闭 SUMO 仿真进程；可重复调用，未加载时为 no-op。"""
        if traci.isLoaded():
            traci.close()

    def step(self) -> Optional[float]:
        """推进一个仿真步。

        Returns:
            当前仿真时间；FatalTraCIError（如 SUMO 进程被杀）时优雅关闭并
            返回 None；配置 max_restarts > 0 时先尝试自动重连。
        """
        try:
            traci.simulationStep()
            self._arrival_window.append(traci.simulation.getDepartedNumber())
            return traci.simulation.getTime()
        except traci.exceptions.FatalTraCIError as exc:
            logger.error("TraCI 连接断开: %s; closing gracefully", exc)
            if self._restarts < self.max_restarts:
                self._restarts += 1
                logger.info("尝试自动重连 (%d/%d)", self._restarts, self.max_restarts)
                self.close()
                self.start()
                return traci.simulation.getTime()
            self.close()
            return None

    def get_state(self) -> JointState:
        """读取当前联合状态。

        Returns:
            当前步的 JointState（相位/排队/流量/车辆快照/到达历史等）。

        Raises:
            RuntimeError: 尚未调用 start()。
        """
        if self.tls_id is None:
            raise RuntimeError("TraCIBridge 尚未 start()")

        step = int(traci.simulation.getTime())
        current_phase = traci.trafficlight.getPhase(self.tls_id)
        program = traci.trafficlight.getAllProgramLogics(self.tls_id)[0]
        phase_obj = program.phases[current_phase]
        phase_name = getattr(phase_obj, "name", f"phase_{current_phase}")
        elapsed = (
            traci.trafficlight.getPhaseDuration(self.tls_id)
            - traci.trafficlight.getNextSwitch(self.tls_id)
            + traci.simulation.getTime()
        )

        queues: List[QueueState] = []
        flows: dict[str, float] = {}
        lanes = self._inbound_lanes or self._controlled_lanes
        for lane_id in lanes:
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
                    capacity=self.get_lane_capacity(lane_id),
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
            vehicles=self._collect_vehicles(list(traci.vehicle.getIDList())),
            arrival_history=list(self._arrival_window),
        )

    def _collect_vehicles(self, ids: List[str]) -> List[VehicleState]:
        """采集车辆快照：先按 vehicle_sample_rate 采样，再按 MAX_VEHICLES 截断。

        超出上限时优先保留进口道（受控车道）上的车辆——CA-MP 只关心它们。
        """
        if self.vehicle_sample_rate > 1:
            ids = ids[:: self.vehicle_sample_rate]
        if len(ids) > self.MAX_VEHICLES:
            inbound = set(self._controlled_lanes)
            on_inbound = [v for v in ids if traci.vehicle.getLaneID(v) in inbound]
            rest = [v for v in ids if v not in set(on_inbound)]
            ids = (on_inbound + rest)[: self.MAX_VEHICLES]
        return [
            VehicleState(vehicle_id=v, lane_id=traci.vehicle.getLaneID(v),
                         speed=traci.vehicle.getSpeed(v))
            for v in ids
        ]

    def apply_actions(self, actions: List[ControlAction]) -> None:
        """将算法输出的控制动作写入 SUMO。

        set_phase 的 value 必须是相位索引 int；无法转换时打 warning 并跳过
        （已知：CA-MP MVI 桩把方向字符串当相位值，正式实现归 AB）。

        Args:
            actions: 控制动作列表，支持 set_phase / set_phase_duration /
                set_program；未知类型打 warning 并跳过。
        """
        for action in actions:
            if action.action_type == "set_phase":
                try:
                    phase_index = int(action.value)
                except (TypeError, ValueError):
                    logger.warning(
                        "set_phase 值非法，跳过: value=%r reason=%s", action.value, action.reason
                    )
                    continue
                traci.trafficlight.setPhase(action.tls_id, phase_index)
            elif action.action_type == "set_phase_duration":
                traci.trafficlight.setPhaseDuration(action.tls_id, float(action.value))
            elif action.action_type == "set_program":
                traci.trafficlight.setProgram(action.tls_id, str(action.value))
            else:
                logger.warning("未知控制动作类型: %s", action.action_type)

    def get_lane_capacity(self, lane_id: str) -> float:
        """车道容量（辆）= 车道长度 / 7.5m（5m 车长 + 2.5m 间距）。

        CA-MP 容量归一化压力 pressure = queue / capacity 的分母。

        Args:
            lane_id: 车道 ID。

        Returns:
            车道可容纳车辆数。
        """
        return traci.lane.getLength(lane_id) / self.LANE_CAPACITY_METERS
