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
from typing import Callable, List, Optional

from defusedxml import ElementTree as ET

from core.types import (
    ActionResult,
    ControlAction,
    JointState,
    PhaseTrafficState,
    QueueState,
    VehicleState,
)
from engine.artifacts import RunArtifacts

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
        artifacts: Optional[RunArtifacts] = None,
        seed: Optional[int] = None,
        max_restarts: int = 0,
        vehicle_sample_rate: int = 1,
        event_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.sumo_cfg = Path(sumo_cfg)
        self.binary = binary
        self.additional_files = list(additional_files or [])
        self.artifacts = artifacts
        self.seed = seed
        self.max_restarts = max(0, int(max_restarts))
        self._restarts = 0
        self.tls_id: Optional[str] = None
        self._controlled_lanes: List[str] = []
        self._inbound_lanes: Optional[List[str]] = None  # edge_mapping 进口道筛选结果
        self.lane_directions: dict[str, str] = {}  # lane_id -> 方位（供 AB 压力映射）
        self.vehicle_sample_rate = max(1, int(vehicle_sample_rate))
        self.event_callback = event_callback or (lambda event_type, detail: None)
        self._arrival_window: deque[int] = deque(maxlen=3000)  # 滚动 3000 步（= 300 秒）到达历史

    def _emit(self, event_type: str, detail: str) -> None:
        self.event_callback(event_type, detail)

    def _build_cmd(self) -> List[str]:
        """组装 traci.start 命令（含可选 --seed 与 additional files）。"""
        cmd = [self.binary, "-c", str(self.sumo_cfg), "--no-step-log", "true"]
        if self.seed is not None:
            cmd += ["--seed", str(self.seed)]
        if self.additional_files:
            cmd += ["-a", ",".join(str(f) for f in self.additional_files)]
        if self.artifacts is not None:
            cmd.extend([
                "--tripinfo-output",
                self.artifacts.tripinfo.resolve().as_posix(),
                "--tripinfo-output.write-unfinished",
                "true",
                "--device.emissions.probability",
                "1",
                "--summary-output",
                self.artifacts.stats.resolve().as_posix(),
                "--fcd-output",
                self.artifacts.trajectory.resolve().as_posix(),
            ])
            if self._config_has_queue_output():
                cmd.extend([
                    "--queue-output",
                    self.artifacts.queues.resolve().as_posix(),
                ])
        return cmd

    def _config_has_queue_output(self) -> bool:
        try:
            root = ET.parse(self.sumo_cfg).getroot()
        except (OSError, ET.ParseError):
            return False
        return any(node.tag == "queue-output" for node in root.iter())

    def start(self) -> None:
        """启动 SUMO 仿真进程。

        Raises:
            FileNotFoundError: sumo_cfg 配置文件不存在。
            RuntimeError: 场景中没有信号灯，无法运行交通控制算法。
        """
        # Clear discovery state before every start so reconnects cannot retain
        # identifiers or lane mappings from the previous SUMO process.
        self.tls_id = None
        self._controlled_lanes = []
        self._inbound_lanes = None
        self.lane_directions = {}

        if not self.sumo_cfg.exists():
            raise FileNotFoundError(f"SUMO 配置文件不存在: {self.sumo_cfg}")

        cmd = self._build_cmd()
        logger.info("启动 SUMO: %s", " ".join(cmd))
        traci.start(cmd)

        tls_ids = traci.trafficlight.getIDList()
        if not tls_ids:
            raise RuntimeError("场景中没有信号灯，无法运行交通控制算法")
        self._activate_additional_signal_programs(set(tls_ids))
        self.tls_id = tls_ids[0]
        self._controlled_lanes = list(traci.trafficlight.getControlledLanes(self.tls_id))
        logger.info("控制信号灯: %s, 控制车道数: %d", self.tls_id, len(self._controlled_lanes))
        self._load_edge_mapping()

    def _activate_additional_signal_programs(self, tls_ids: set[str]) -> None:
        """Activate deterministic variant programs loaded from additional files."""
        for path in self.additional_files:
            try:
                root = ET.parse(path).getroot()
            except (OSError, ET.ParseError):
                continue
            for logic in root.findall("tlLogic"):
                tls_id = logic.get("id", "")
                program_id = logic.get("programID", "")
                if tls_id in tls_ids and program_id.startswith("variant_"):
                    traci.trafficlight.setProgram(tls_id, program_id)

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
                self._emit(
                    "reconnect_started",
                    f"attempt={self._restarts}/{self.max_restarts}",
                )
                logger.info("尝试自动重连 (%d/%d)", self._restarts, self.max_restarts)
                self.close()
                try:
                    self.start()
                except Exception as restart_exc:
                    self._emit("reconnect_failed", str(restart_exc))
                    self.close()
                    return None
                self._emit("reconnect_succeeded", f"attempt={self._restarts}")
                return traci.simulation.getTime()
            self._emit("reconnect_failed", f"retry limit exhausted: {exc}")
            self.close()
            return None

    def is_exhausted(self) -> bool:
        """Return whether SUMO has no active or expected vehicles."""
        return traci.simulation.getMinExpectedNumber() <= 0

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
        programs = traci.trafficlight.getAllProgramLogics(self.tls_id)
        active_program = traci.trafficlight.getProgram(self.tls_id)
        program = next(
            (
                candidate
                for candidate in programs
                if candidate.programID == active_program
            ),
            programs[0],
        )
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
            phase_states=self._build_phase_states(
                program,
                traci.trafficlight.getControlledLinks(self.tls_id),
            ),
        )

    def _build_phase_states(
        self,
        program: object,
        controlled_links: object,
    ) -> List[PhaseTrafficState]:
        """Map legal phases to unique incoming/outgoing lane measurements."""
        links_by_signal = list(controlled_links)
        states: List[PhaseTrafficState] = []
        for phase_index, phase in enumerate(program.phases):
            incoming: set[str] = set()
            outgoing: set[str] = set()
            signal_state = str(phase.state)
            for signal_index, signal in enumerate(signal_state):
                if signal not in "Gg" or signal_index >= len(links_by_signal):
                    continue
                for link in links_by_signal[signal_index] or ():
                    if len(link) < 2:
                        continue
                    incoming.add(str(link[0]))
                    outgoing.add(str(link[1]))

            incoming_lanes = tuple(sorted(incoming))
            outgoing_lanes = tuple(sorted(outgoing))
            incoming_queue = sum(
                float(traci.lane.getLastStepHaltingNumber(lane))
                for lane in incoming_lanes
            )
            outgoing_queue = sum(
                float(traci.lane.getLastStepHaltingNumber(lane))
                for lane in outgoing_lanes
            )
            incoming_capacity = sum(
                self.get_lane_capacity(lane) for lane in incoming_lanes
            )
            outgoing_capacity = sum(
                self.get_lane_capacity(lane) for lane in outgoing_lanes
            )
            occupancies = []
            for lane in outgoing_lanes:
                occupancy = float(traci.lane.getLastStepOccupancy(lane))
                if occupancy > 1.0:
                    occupancy /= 100.0
                occupancies.append(min(1.0, max(0.0, occupancy)))

            states.append(
                PhaseTrafficState(
                    phase_index=phase_index,
                    signal_state=signal_state,
                    nominal_duration=float(phase.duration),
                    incoming_lanes=incoming_lanes,
                    outgoing_lanes=outgoing_lanes,
                    incoming_queue=incoming_queue,
                    incoming_capacity=incoming_capacity,
                    outgoing_queue=outgoing_queue,
                    outgoing_capacity=outgoing_capacity,
                    outgoing_occupancy=max(occupancies, default=0.0),
                )
            )
        return states

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

    def apply_actions(self, actions: List[ControlAction]) -> list[ActionResult]:
        """将算法输出的控制动作写入 SUMO。

        set_phase 的 value 必须是相位索引 int；无法转换时打 warning 并跳过
        （已知：CA-MP MVI 桩把方向字符串当相位值，正式实现归 AB）。

        Args:
            actions: 控制动作列表，支持 set_phase / set_phase_duration /
                set_program；未知类型打 warning 并跳过。
        """
        results: list[ActionResult] = []
        for action in actions:
            if action.tls_id != self.tls_id:
                results.append(
                    ActionResult(action, False, f"unknown tls_id: {action.tls_id!r}")
                )
                continue
            if action.action_type == "set_phase":
                if not isinstance(action.value, int):
                    results.append(
                        ActionResult(
                            action,
                            False,
                            f"set_phase value must be an integer: {action.value!r}",
                        )
                    )
                    continue
                traci.trafficlight.setPhase(action.tls_id, action.value)
            elif action.action_type == "set_phase_duration":
                try:
                    duration = float(action.value)
                except (TypeError, ValueError):
                    results.append(
                        ActionResult(
                            action,
                            False,
                            "set_phase_duration value must be numeric: "
                            f"{action.value!r}",
                        )
                    )
                    continue
                if duration <= 0:
                    results.append(
                        ActionResult(
                            action,
                            False,
                            "set_phase_duration value must be positive: "
                            f"{duration!r}",
                        )
                    )
                    continue
                traci.trafficlight.setPhaseDuration(action.tls_id, duration)
            elif action.action_type == "set_program":
                program = str(action.value).strip()
                if not program:
                    results.append(
                        ActionResult(
                            action,
                            False,
                            "set_program value must be non-empty",
                        )
                    )
                    continue
                traci.trafficlight.setProgram(action.tls_id, program)
            else:
                results.append(
                    ActionResult(
                        action,
                        False,
                        f"unknown action_type: {action.action_type!r}",
                    )
                )
                continue
            results.append(ActionResult(action, True, "applied"))
        return results

    def get_lane_capacity(self, lane_id: str) -> float:
        """车道容量（辆）= 车道长度 / 7.5m（5m 车长 + 2.5m 间距）。

        CA-MP 容量归一化压力 pressure = queue / capacity 的分母。

        Args:
            lane_id: 车道 ID。

        Returns:
            车道可容纳车辆数。
        """
        return traci.lane.getLength(lane_id) / self.LANE_CAPACITY_METERS
