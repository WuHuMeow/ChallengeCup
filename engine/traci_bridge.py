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
from collections import Counter, deque
from pathlib import Path
from typing import Callable, List, Optional

from defusedxml import ElementTree as ET

from core.types import (
    ActionResult,
    ControlAction,
    JointState,
    PhaseTrafficState,
    QueueState,
    SafetyVehicleState,
    VehicleState,
)
from engine.action_validation import validate_control_action
from engine.artifacts import RunArtifacts
from engine.movement_state import MovementStateBuilder

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
        self.configured_end_time = self._read_configured_end_time()
        self.step_length = self._read_step_length()
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
        self._movement_state_builder: MovementStateBuilder | None = None
        self._turn_ratios: dict[tuple[str, str], float] = {}
        self._observed_turn_counts: Counter[tuple[str, str]] = Counter()
        self._approach_lanes_by_vehicle: dict[str, str] = {}

    def _read_configured_end_time(self) -> float | None:
        """Read the SUMO simulation horizon in seconds when one is configured."""
        try:
            end = ET.parse(self.sumo_cfg).getroot().find("./time/end")
            raw = end.get("value") if end is not None else None
            return float(raw) if raw is not None else None
        except (OSError, ET.ParseError, TypeError, ValueError):
            return None

    def _read_step_length(self) -> float:
        """Read the configured SUMO step length, whose default is one second."""
        try:
            step = ET.parse(self.sumo_cfg).getroot().find("./time/step-length")
            raw = step.get("value") if step is not None else None
            return float(raw) if raw is not None else 1.0
        except (OSError, ET.ParseError, TypeError, ValueError):
            return 1.0

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
                "--emissions.volumetric-fuel",
                "true",
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
        self._movement_state_builder = None
        self._turn_ratios = {}
        self._observed_turn_counts.clear()
        self._approach_lanes_by_vehicle.clear()

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
        self._load_turn_ratios()
        self._movement_state_builder = MovementStateBuilder(self, self.tls_id)

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

    def _load_turn_ratios(self) -> None:
        """Load edgeRelation probabilities without modifying source files."""
        self._turn_ratios = {}
        for path in self._turn_file_candidates():
            if not path.exists():
                continue
            try:
                root = ET.parse(path).getroot()
            except (OSError, ET.ParseError) as exc:
                logger.warning("turn ratio file unavailable (%s): %s", path, exc)
                return
            for relation in root.iter("edgeRelation"):
                incoming = relation.get("from")
                outgoing = relation.get("to")
                probability = relation.get("probability")
                if not incoming or not outgoing or probability is None:
                    continue
                try:
                    value = float(probability)
                except ValueError:
                    continue
                if 0 <= value <= 1:
                    self._turn_ratios[(incoming, outgoing)] = value
            return

    def _turn_file_candidates(self) -> tuple[Path, ...]:
        filename = f"{self.sumo_cfg.stem}.turn.xml"
        candidates = [self.sumo_cfg.parent / filename]
        match = re.search(r"demo_(\d+)", self.sumo_cfg.stem)
        if match:
            from core.config import get_config

            data_root = Path(get_config().path("paths.data_root"))
            candidates.append(
                data_root
                / match.group(1)
                / "sumo工程"
                / f"demo_{match.group(1)}.turn.xml"
            )
        return tuple(dict.fromkeys(candidates))

    @staticmethod
    def _lane_edge_id(lane_id: str) -> str:
        edge_id, separator, lane_index = lane_id.rpartition("_")
        return edge_id if separator and lane_index.isdigit() else lane_id

    def get_turn_ratio(
        self,
        incoming_lane: str,
        outgoing_lane: str,
    ) -> float | None:
        configured = self._turn_ratios.get(
            (
                self._lane_edge_id(incoming_lane),
                self._lane_edge_id(outgoing_lane),
            )
        )
        if configured is not None:
            return configured
        observed = self._observed_turn_counts[(incoming_lane, outgoing_lane)]
        total = sum(
            count
            for (candidate_incoming, _), count in self._observed_turn_counts.items()
            if candidate_incoming == incoming_lane
        )
        return observed / total if total else None

    def _record_turn_observations(
        self,
        observations: tuple[SafetyVehicleState, ...],
    ) -> None:
        if self._movement_state_builder is None:
            return
        movements = set(self._movement_state_builder.movement_keys)
        incoming_lanes = {movement.incoming_lane for movement in movements}
        outgoing_lanes = {movement.outgoing_lane for movement in movements}
        active_vehicle_ids = {observation.vehicle_id for observation in observations}
        for observation in observations:
            if observation.lane_id in incoming_lanes:
                self._approach_lanes_by_vehicle[observation.vehicle_id] = (
                    observation.lane_id
                )
                continue
            incoming_lane = self._approach_lanes_by_vehicle.get(
                observation.vehicle_id
            )
            if incoming_lane is None:
                continue
            if observation.lane_id in outgoing_lanes:
                movement = (incoming_lane, observation.lane_id)
                if any(
                    key.incoming_lane == movement[0]
                    and key.outgoing_lane == movement[1]
                    for key in movements
                ):
                    self._observed_turn_counts[movement] += 1
                self._approach_lanes_by_vehicle.pop(observation.vehicle_id, None)
            elif not observation.lane_id.startswith(":"):
                self._approach_lanes_by_vehicle.pop(observation.vehicle_id, None)
        for vehicle_id in set(self._approach_lanes_by_vehicle) - active_vehicle_ids:
            self._approach_lanes_by_vehicle.pop(vehicle_id, None)

    def get_controlled_links(self, tls_id: str) -> object:
        return traci.trafficlight.getControlledLinks(tls_id)

    def get_signal_program(self, tls_id: str) -> object:
        programs = traci.trafficlight.getAllProgramLogics(tls_id)
        active_program = traci.trafficlight.getProgram(tls_id)
        return next(
            (
                candidate
                for candidate in programs
                if candidate.programID == active_program
            ),
            programs[0],
        )

    def get_lane_length(self, lane_id: str) -> float:
        return float(traci.lane.getLength(lane_id))

    def get_lane_halting_number(self, lane_id: str) -> float:
        return float(traci.lane.getLastStepHaltingNumber(lane_id))

    def get_lane_occupancy(self, lane_id: str) -> float:
        return float(traci.lane.getLastStepOccupancy(lane_id)) / 100.0

    @property
    def movement_capacity_inputs(self) -> dict[str, float] | None:
        if self._movement_state_builder is None:
            return None
        return dict(self._movement_state_builder.capacity_inputs)

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

        simulation_time = float(traci.simulation.getTime())
        step = int(round(simulation_time / self.step_length))
        current_phase = traci.trafficlight.getPhase(self.tls_id)
        program = self.get_signal_program(self.tls_id)
        phase_obj = program.phases[current_phase]
        phase_name = getattr(phase_obj, "name", f"phase_{current_phase}")
        elapsed = traci.trafficlight.getSpentDuration(self.tls_id)

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

        controlled_links = traci.trafficlight.getControlledLinks(self.tls_id)
        vehicle_ids = list(traci.vehicle.getIDList())
        safety_vehicles = self._collect_safety_vehicles(vehicle_ids)
        self._record_turn_observations(safety_vehicles)
        phase_movements = (
            self._movement_state_builder.snapshot()
            if self._movement_state_builder is not None
            else ()
        )
        return JointState(
            step=step,
            timestamp=simulation_time,
            tls_id=self.tls_id,
            current_phase=current_phase,
            current_phase_name=phase_name,
            elapsed_phase_time=float(elapsed),
            queues=queues,
            flows=flows,
            detector_values={},
            vehicles=self._collect_vehicles(vehicle_ids),
            arrival_history=list(self._arrival_window),
            phase_states=self._build_phase_states(program, controlled_links),
            phase_movements=phase_movements,
            safety_vehicles=safety_vehicles,
            collision_vehicle_ids=self._simulation_vehicle_ids(
                "getCollidingVehiclesIDList"
            ),
            teleport_vehicle_ids=tuple(
                sorted(
                    set(self._simulation_vehicle_ids("getStartingTeleportIDList"))
                    | set(self._simulation_vehicle_ids("getEndingTeleportIDList"))
                )
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
                occupancy = self.get_lane_occupancy(lane)
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

    def _collect_safety_vehicles(
        self,
        ids: List[str],
    ) -> tuple[SafetyVehicleState, ...]:
        observations = []
        for vehicle_id in ids:
            try:
                next_tls = traci.vehicle.getNextTLS(vehicle_id)
                next_signal = next_tls[0] if next_tls else None
                observations.append(
                    SafetyVehicleState(
                        vehicle_id=vehicle_id,
                        lane_id=str(traci.vehicle.getLaneID(vehicle_id)),
                        speed_mps=float(traci.vehicle.getSpeed(vehicle_id)),
                        position_xy=tuple(
                            float(value)
                            for value in traci.vehicle.getPosition(vehicle_id)[:2]
                        ),
                        next_tls_id=(
                            str(next_signal[0]) if next_signal is not None else None
                        ),
                        next_tls_link_index=(
                            int(next_signal[1]) if next_signal is not None else None
                        ),
                        distance_to_tls_m=(
                            float(next_signal[2]) if next_signal is not None else None
                        ),
                        next_tls_state=(
                            str(next_signal[3]) if next_signal is not None else None
                        ),
                    )
                )
            except (
                traci.exceptions.TraCIException,
                traci.exceptions.FatalTraCIError,
            ):
                continue
        return tuple(observations)

    @staticmethod
    def _simulation_vehicle_ids(method_name: str) -> tuple[str, ...]:
        try:
            method = getattr(traci.simulation, method_name)
            return tuple(sorted(set(str(value) for value in method())))
        except (
            traci.exceptions.TraCIException,
            traci.exceptions.FatalTraCIError,
        ):
            return ()

    def apply_actions(self, actions: List[ControlAction]) -> list[ActionResult]:
        """将算法输出的控制动作写入 SUMO。

        set_phase 的 value 必须是合法相位索引 int；每个动作均返回可审计的
        ActionResult，拒绝原因由调用方写入事件日志。

        Args:
            actions: 控制动作列表，支持 set_phase / set_phase_duration /
                set_program；未知类型打 warning 并跳过。
        """
        results: list[ActionResult] = []
        for action in actions:
            value, error = validate_control_action(
                action,
                self.tls_id,
            )
            if error is not None:
                results.append(ActionResult(action, False, error))
                continue
            if action.action_type in {"set_phase", "set_program"}:
                try:
                    phase_count, program_ids = self._control_action_domain()
                except RuntimeError as exc:
                    results.append(
                        ActionResult(
                            action,
                            False,
                            f"control domain unavailable: {exc}",
                        )
                    )
                    continue
                value, error = validate_control_action(
                    action,
                    self.tls_id,
                    phase_count=phase_count,
                    program_ids=program_ids,
                )
                if error is not None:
                    results.append(ActionResult(action, False, error))
                    continue
            if action.action_type == "set_phase":
                traci.trafficlight.setPhase(action.tls_id, value)
            elif action.action_type == "set_phase_duration":
                traci.trafficlight.setPhaseDuration(action.tls_id, value)
            elif action.action_type == "set_program":
                traci.trafficlight.setProgram(action.tls_id, value)
            results.append(ActionResult(action, True, "applied"))
        return results

    def _control_action_domain(self) -> tuple[int, set[str]]:
        """Return the active phase count and available programs from SUMO."""
        try:
            programs = list(traci.trafficlight.getAllProgramLogics(self.tls_id))
            if not programs:
                raise RuntimeError("no signal programs returned")
            active_program = traci.trafficlight.getProgram(self.tls_id)
        except RuntimeError:
            raise
        except (traci.exceptions.TraCIException, traci.exceptions.FatalTraCIError) as exc:
            detail = str(exc) or type(exc).__name__
            raise RuntimeError(detail) from exc
        active_logic = next(
            (
                program
                for program in programs
                if program.programID == active_program
            ),
            programs[0],
        )
        return (
            len(active_logic.phases),
            {str(program.programID) for program in programs},
        )

    def get_lane_capacity(self, lane_id: str) -> float:
        """车道容量（辆）= 车道长度 / 7.5m（5m 车长 + 2.5m 间距）。

        CA-MP 容量归一化压力 pressure = queue / capacity 的分母。

        Args:
            lane_id: 车道 ID。

        Returns:
            车道可容纳车辆数。
        """
        return traci.lane.getLength(lane_id) / self.LANE_CAPACITY_METERS
