"""TraCI 批量读写封装。

职责：把 SUMO 的底层 TraCI 调用转换为项目统一的 `JointState` 和 `ControlAction`，
让算法层无需直接依赖 traci 细节。
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import sys
from collections import Counter, deque
from pathlib import Path
from typing import Callable, List, Optional

from defusedxml import ElementTree as ET

from core.types import (
    ActionResult,
    CollisionRecord,
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
from engine.safety import ConflictDefinition

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
        process_factory: Optional[Callable[..., subprocess.Popen]] = None,
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
        self._tls_ids: tuple[str, ...] = ()
        self._controlled_lanes: List[str] = []
        self._inbound_lanes: Optional[List[str]] = None  # edge_mapping 进口道筛选结果
        self.lane_directions: dict[str, str] = {}  # lane_id -> 方位（供 AB 压力映射）
        self.vehicle_sample_rate = max(1, int(vehicle_sample_rate))
        self.event_callback = event_callback or (lambda event_type, detail: None)
        self._process_factory = process_factory or subprocess.Popen
        self._arrival_window: deque[int] = deque(maxlen=3000)  # 滚动 3000 步（= 300 秒）到达历史
        self._movement_state_builder: MovementStateBuilder | None = None
        self._turn_ratios: dict[tuple[str, str], float] = {}
        self._observed_turn_counts: Counter[tuple[str, str]] = Counter()
        self._approach_lanes_by_vehicle: dict[str, str] = {}
        self._conflict_definitions: tuple[ConflictDefinition, ...] = ()
        self._pending_startup_actions: tuple[ControlAction, ...] = ()
        self._owned_process: subprocess.Popen | None = None
        self._owned_pid: int | None = None

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
                "--collision-output",
                self.artifacts.collisions.resolve().as_posix(),
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
        self._tls_ids = ()
        self._controlled_lanes = []
        self._inbound_lanes = None
        self.lane_directions = {}
        self._movement_state_builder = None
        self._turn_ratios = {}
        self._observed_turn_counts.clear()
        self._approach_lanes_by_vehicle.clear()
        self._conflict_definitions = ()
        self._pending_startup_actions = ()

        if not self.sumo_cfg.exists():
            raise FileNotFoundError(f"SUMO 配置文件不存在: {self.sumo_cfg}")

        cmd = self._build_cmd()
        logger.info("启动 SUMO: %s", " ".join(cmd))
        try:
            self._start_owned_connection(cmd)
            tls_ids = tuple(traci.trafficlight.getIDList())
            if not tls_ids:
                raise RuntimeError("场景中没有信号灯，无法运行交通控制算法")
            self._tls_ids = tls_ids
            self.tls_id = tls_ids[0]
            self._pending_startup_actions = self._additional_signal_program_actions(
                set(tls_ids)
            )
            self._controlled_lanes = list(
                traci.trafficlight.getControlledLanes(self.tls_id)
            )
            logger.info(
                "控制信号灯: %s, 控制车道数: %d",
                self.tls_id,
                len(self._controlled_lanes),
            )
            self._load_edge_mapping()
            self._load_turn_ratios()
            self._load_conflict_definitions()
            self._movement_state_builder = MovementStateBuilder(self, self.tls_id)
        except Exception:
            self.close()
            raise

    def _start_owned_connection(self, cmd: list[str]) -> None:
        """Create, record, and connect the exact SUMO child owned by this bridge."""
        port = traci.getFreeSocketPort()
        process = self._process_factory(
            [*cmd, "--remote-port", str(port)],
            stdout=None,
        )
        self._record_owned_process(process)
        traci.init(port, proc=process)

    def _record_owned_process(self, process: subprocess.Popen | None) -> None:
        self._owned_process = process
        if process is not None:
            self._owned_pid = int(process.pid)

    def _additional_signal_program_actions(
        self,
        tls_ids: set[str],
    ) -> tuple[ControlAction, ...]:
        """Build validated-boundary actions for deterministic variant programs."""
        actions: list[ControlAction] = []
        for path in self.additional_files:
            try:
                root = ET.parse(path).getroot()
            except (OSError, ET.ParseError):
                continue
            for logic in root.findall("tlLogic"):
                candidate_tls_id = logic.get("id", "")
                program_id = logic.get("programID", "")
                if (
                    candidate_tls_id not in tls_ids
                    or not program_id.startswith("variant_")
                ):
                    continue
                actions.append(ControlAction.for_simulation_time(
                    candidate_tls_id,
                    "set_program",
                    {
                        "program_id": program_id,
                        "phases": [
                            {
                                "duration": phase.get("duration"),
                                "state": phase.get("state"),
                            }
                            for phase in logic.findall("phase")
                        ],
                    },
                    "install validated variant signal program",
                    0.0,
                ))
        return tuple(actions)

    def take_startup_actions(self) -> tuple[ControlAction, ...]:
        """Consume signal-program actions discovered during ``start()``."""
        actions = self._pending_startup_actions
        self._pending_startup_actions = ()
        return actions

    def get_startup_state(self, tls_id: str) -> JointState:
        """Read the zero-time signal state used to validate one startup action."""
        if tls_id not in self._tls_ids:
            raise RuntimeError(f"unknown startup tls_id: {tls_id!r}")
        simulation_time = float(traci.simulation.getTime())
        current_phase = int(traci.trafficlight.getPhase(tls_id))
        program = self.get_signal_program(tls_id)
        phase_obj = program.phases[current_phase]
        phase_name = getattr(phase_obj, "name", f"phase_{current_phase}")
        return JointState(
            step=int(round(simulation_time / self.step_length)),
            timestamp=simulation_time,
            tls_id=tls_id,
            current_phase=current_phase,
            current_phase_name=phase_name,
            elapsed_phase_time=float(
                traci.trafficlight.getSpentDuration(tls_id)
            ),
        )

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

    def _network_file_path(self) -> Path | None:
        try:
            root = ET.parse(self.sumo_cfg).getroot()
        except (OSError, ET.ParseError):
            return None
        node = root.find("./input/net-file")
        value = node.get("value") if node is not None else None
        if not value:
            return None
        path = Path(value.split(",", 1)[0])
        return path if path.is_absolute() else (self.sumo_cfg.parent / path).resolve()

    def _load_conflict_definitions(self) -> None:
        """Load network foe pairs and path distances to geometric conflicts."""
        self._conflict_definitions = ()
        if self.tls_id is None:
            return
        path = self._network_file_path()
        if path is None or not path.exists():
            return
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            logger.warning("network conflict data unavailable (%s): %s", path, exc)
            return

        junction = next(
            (
                candidate
                for candidate in root.iter("junction")
                if candidate.get("id") == self.tls_id
            ),
            None,
        )
        if junction is None:
            return
        requests = {
            int(request.get("index", "-1")): request.get("foes", "")
            for request in junction.findall("request")
            if request.get("index", "").isdigit()
        }
        internal_lanes = junction.get("intLanes", "").split()
        lane_shapes = {
            lane.get("id", ""): self._parse_shape(lane.get("shape", ""))
            for lane in root.iter("lane")
            if lane.get("id")
        }
        lane_locations = {
            lane.get("id", ""): (edge.get("id", ""), lane.get("index", ""))
            for edge in root.iter("edge")
            for lane in edge.findall("lane")
            if lane.get("id")
        }
        connections = tuple(root.iter("connection"))
        successors: dict[tuple[str, str], tuple[str, ...]] = {}
        for connection in connections:
            via = connection.get("via", "")
            source = (connection.get("from", ""), connection.get("fromLane", ""))
            if via:
                successors[source] = successors.get(source, ()) + (via,)

        link_shapes: dict[int, tuple[tuple[float, float], ...]] = {}
        link_indices_by_internal_lane: dict[str, set[int]] = {}
        for connection in connections:
            if connection.get("tl") != self.tls_id:
                continue
            raw_index = connection.get("linkIndex", "")
            via = connection.get("via", "")
            if not raw_index.isdigit():
                continue
            link_index = int(raw_index)
            path_lanes = []
            current_lane = via
            while current_lane and current_lane not in path_lanes:
                path_lanes.append(current_lane)
                location = lane_locations.get(current_lane)
                next_lanes = successors.get(location, ()) if location else ()
                current_lane = next_lanes[0] if len(next_lanes) == 1 else ""
            for lane_id in path_lanes:
                link_indices_by_internal_lane.setdefault(lane_id, set()).add(link_index)

            shape = ()
            for lane_id in path_lanes:
                lane_shape = lane_shapes.get(lane_id, ())
                if not lane_shape:
                    continue
                shape += lane_shape[1:] if shape and shape[-1] == lane_shape[0] else lane_shape
            if not shape:
                incoming_lane = (
                    f"{connection.get('from')}_{connection.get('fromLane')}"
                )
                outgoing_lane = (
                    f"{connection.get('to')}_{connection.get('toLane')}"
                )
                incoming_shape = lane_shapes.get(incoming_lane, ())
                outgoing_shape = lane_shapes.get(outgoing_lane, ())
                if incoming_shape and outgoing_shape:
                    shape = (incoming_shape[-1], outgoing_shape[0])
            if shape:
                link_shapes[link_index] = shape

        if internal_lanes:
            request_link_indices = {
                request_index: link_indices_by_internal_lane.get(
                    internal_lanes[request_index], set()
                )
                for request_index in requests
                if request_index < len(internal_lanes)
            }
        else:
            request_link_indices = {
                request_index: {request_index}
                for request_index in requests
                if request_index in link_shapes
            }

        definitions = []
        for first_index, foes in requests.items():
            for second_index in requests:
                if second_index <= first_index:
                    continue
                bit_index = len(foes) - 1 - second_index
                if bit_index < 0 or foes[bit_index] != "1":
                    continue
                for first_link_index in request_link_indices.get(first_index, set()):
                    first_shape = link_shapes.get(first_link_index)
                    if first_shape is None:
                        continue
                    for second_link_index in request_link_indices.get(second_index, set()):
                        second_shape = link_shapes.get(second_link_index)
                        if second_shape is None or first_link_index == second_link_index:
                            continue
                        offsets = self._polyline_intersection_offsets(
                            first_shape,
                            second_shape,
                        )
                        if offsets is None:
                            continue
                        definitions.append(
                            ConflictDefinition(
                                first_link_index,
                                second_link_index,
                                offsets[0],
                                offsets[1],
                            )
                        )
        self._conflict_definitions = tuple(definitions)

    @staticmethod
    def _parse_shape(raw: str) -> tuple[tuple[float, float], ...]:
        points = []
        for token in raw.split():
            try:
                x, y = token.split(",", 1)
                points.append((float(x), float(y)))
            except (TypeError, ValueError):
                return ()
        return tuple(points)

    @staticmethod
    def _polyline_intersection_offsets(
        first: tuple[tuple[float, float], ...],
        second: tuple[tuple[float, float], ...],
    ) -> tuple[float, float] | None:
        first_prefix = 0.0
        closest: tuple[float, float, float] | None = None
        for first_start, first_end in zip(first, first[1:]):
            first_length = math.dist(first_start, first_end)
            second_prefix = 0.0
            for second_start, second_end in zip(second, second[1:]):
                second_length = math.dist(second_start, second_end)
                parameters = TraCIBridge._segment_intersection_parameters(
                    first_start,
                    first_end,
                    second_start,
                    second_end,
                )
                if parameters is not None:
                    first_parameter, second_parameter = parameters
                    return (
                        first_prefix + first_parameter * first_length,
                        second_prefix + second_parameter * second_length,
                    )
                first_parameter, second_parameter, distance_squared = (
                    TraCIBridge._segment_closest_parameters(
                        first_start,
                        first_end,
                        second_start,
                        second_end,
                    )
                )
                candidate = (
                    distance_squared,
                    first_prefix + first_parameter * first_length,
                    second_prefix + second_parameter * second_length,
                )
                if closest is None or candidate < closest:
                    closest = candidate
                second_prefix += second_length
            first_prefix += first_length
        return (closest[1], closest[2]) if closest is not None else None

    @staticmethod
    def _segment_closest_parameters(
        first_start: tuple[float, float],
        first_end: tuple[float, float],
        second_start: tuple[float, float],
        second_end: tuple[float, float],
    ) -> tuple[float, float, float]:
        first = (
            first_end[0] - first_start[0],
            first_end[1] - first_start[1],
        )
        second = (
            second_end[0] - second_start[0],
            second_end[1] - second_start[1],
        )
        delta = (
            first_start[0] - second_start[0],
            first_start[1] - second_start[1],
        )

        def dot(left: tuple[float, float], right: tuple[float, float]) -> float:
            return left[0] * right[0] + left[1] * right[1]

        def clamp(value: float) -> float:
            return min(1.0, max(0.0, value))

        first_length_squared = dot(first, first)
        second_length_squared = dot(second, second)
        if first_length_squared <= 1e-12 and second_length_squared <= 1e-12:
            first_parameter = second_parameter = 0.0
        elif first_length_squared <= 1e-12:
            first_parameter = 0.0
            second_parameter = clamp(dot(second, delta) / second_length_squared)
        else:
            first_delta = dot(first, delta)
            if second_length_squared <= 1e-12:
                second_parameter = 0.0
                first_parameter = clamp(-first_delta / first_length_squared)
            else:
                cross = dot(first, second)
                second_delta = dot(second, delta)
                denominator = (
                    first_length_squared * second_length_squared
                    - cross * cross
                )
                first_parameter = (
                    clamp(
                        (cross * second_delta - first_delta * second_length_squared)
                        / denominator
                    )
                    if abs(denominator) > 1e-12
                    else 0.0
                )
                second_parameter = (
                    cross * first_parameter + second_delta
                ) / second_length_squared
                if second_parameter < 0:
                    second_parameter = 0.0
                    first_parameter = clamp(
                        -first_delta / first_length_squared
                    )
                elif second_parameter > 1:
                    second_parameter = 1.0
                    first_parameter = clamp(
                        (cross - first_delta) / first_length_squared
                    )
        first_point = (
            first_start[0] + first_parameter * first[0],
            first_start[1] + first_parameter * first[1],
        )
        second_point = (
            second_start[0] + second_parameter * second[0],
            second_start[1] + second_parameter * second[1],
        )
        return (
            first_parameter,
            second_parameter,
            (first_point[0] - second_point[0]) ** 2
            + (first_point[1] - second_point[1]) ** 2,
        )

    @staticmethod
    def _segment_intersection_parameters(
        first_start: tuple[float, float],
        first_end: tuple[float, float],
        second_start: tuple[float, float],
        second_end: tuple[float, float],
    ) -> tuple[float, float] | None:
        first_dx = first_end[0] - first_start[0]
        first_dy = first_end[1] - first_start[1]
        second_dx = second_end[0] - second_start[0]
        second_dy = second_end[1] - second_start[1]
        denominator = first_dx * second_dy - first_dy * second_dx
        if abs(denominator) <= 1e-9:
            return None
        delta_x = second_start[0] - first_start[0]
        delta_y = second_start[1] - first_start[1]
        first_parameter = (
            delta_x * second_dy - delta_y * second_dx
        ) / denominator
        second_parameter = (
            delta_x * first_dy - delta_y * first_dx
        ) / denominator
        if (
            -1e-9 <= first_parameter <= 1 + 1e-9
            and -1e-9 <= second_parameter <= 1 + 1e-9
        ):
            return (
                min(1.0, max(0.0, first_parameter)),
                min(1.0, max(0.0, second_parameter)),
            )
        return None

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

    @property
    def conflict_definitions(self) -> tuple[ConflictDefinition, ...]:
        return self._conflict_definitions

    @property
    def process_id(self) -> int | None:
        """Return the exact SUMO child PID most recently owned by this bridge."""
        return self._owned_pid

    def close(self) -> None:
        """Close TraCI and reap only this bridge's recorded SUMO child."""
        process = self._owned_process
        if process is not None and self._owned_pid is None:
            self._owned_pid = int(process.pid)
        close_error: Exception | None = None
        try:
            if traci.isLoaded():
                traci.close(wait=False)
        except Exception as exc:
            close_error = exc
        if process is not None and process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        self._owned_process = None
        if close_error is not None:
            raise close_error

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
        collisions = self._simulation_collisions()
        starting_teleports = self._simulation_vehicle_ids(
            "getStartingTeleportIDList"
        )
        ending_teleports = self._simulation_vehicle_ids(
            "getEndingTeleportIDList"
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
            legal_phase_transitions=self._legal_phase_transitions(program),
            safety_vehicles=safety_vehicles,
            collisions=collisions,
            collision_vehicle_ids=tuple(
                sorted(
                    {
                        vehicle_id
                        for collision in collisions
                        for vehicle_id in (
                            collision.collider_id,
                            collision.victim_id,
                        )
                    }
                )
            ),
            starting_teleport_vehicle_ids=starting_teleports,
            ending_teleport_vehicle_ids=ending_teleports,
            teleport_vehicle_ids=tuple(
                sorted(
                    set(starting_teleports) | set(ending_teleports)
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

    @staticmethod
    def _simulation_collisions() -> tuple[CollisionRecord, ...]:
        try:
            collisions = traci.simulation.getCollisions()
        except (
            AttributeError,
            traci.exceptions.TraCIException,
            traci.exceptions.FatalTraCIError,
        ):
            return ()
        return tuple(
            CollisionRecord(
                collider_id=str(collision.collider),
                victim_id=str(collision.victim),
                collider_type=str(getattr(collision, "colliderType", "")),
                victim_type=str(getattr(collision, "victimType", "")),
                collider_speed_mps=float(collision.colliderSpeed),
                victim_speed_mps=float(collision.victimSpeed),
                collision_type=str(getattr(collision, "collisionType", "")),
                lane_id=str(getattr(collision, "lane", "")),
                position_m=float(collision.pos),
            )
            for collision in collisions
        )

    @staticmethod
    def _legal_phase_transitions(program: object) -> tuple[tuple[int, int], ...]:
        phases = tuple(program.phases)
        if not phases:
            return ()
        transitions = []
        for phase_index, phase in enumerate(phases):
            configured = tuple(getattr(phase, "next", ()) or ())
            targets = (
                tuple(int(target) for target in configured)
                if configured
                else ((phase_index + 1) % len(phases),)
            )
            transitions.extend((phase_index, target) for target in targets)
        return tuple(dict.fromkeys(transitions))

    def _apply_actions(self, actions: List[ControlAction]) -> list[ActionResult]:
        """Write an executor-approved action batch to SUMO.

        This private sink retains domain validation as defense in depth. Production
        callers must enter through :meth:`engine.safety_executor.SafetyExecutor.apply`.

        Args:
            actions: Executor-approved set_phase / set_phase_duration / set_program
                actions.
        """
        results: list[ActionResult] = []
        for action in actions:
            known_tls_ids = self._tls_ids or (
                (self.tls_id,) if self.tls_id is not None else ()
            )
            expected_tls_id = (
                action.tls_id if action.tls_id in known_tls_ids else None
            )
            value, reason_code, error = validate_control_action(
                action,
                expected_tls_id,
            )
            if error is not None:
                results.append(ActionResult(action, False, error, reason_code or ""))
                continue
            active_program = ""
            if action.action_type in {"set_phase", "set_program"}:
                try:
                    (
                        phase_count,
                        program_ids,
                        current_phase,
                        allowed_phase_targets,
                        active_program,
                    ) = self._control_action_domain(action.tls_id)
                except RuntimeError as exc:
                    results.append(
                        ActionResult(
                            action,
                            False,
                            f"control domain unavailable: {exc}",
                            "control_domain_unavailable",
                        )
                    )
                    continue
                if not isinstance(value, dict):
                    value, reason_code, error = validate_control_action(
                        action,
                        action.tls_id,
                        phase_count=phase_count,
                        program_ids=program_ids,
                        current_phase=(
                            current_phase
                            if action.action_type == "set_phase"
                            else None
                        ),
                        allowed_phase_targets=(
                            allowed_phase_targets
                            if action.action_type == "set_phase"
                            else None
                        ),
                    )
                    if error is not None:
                        results.append(
                            ActionResult(action, False, error, reason_code or "")
                        )
                        continue
            if action.action_type == "set_phase":
                traci.trafficlight.setPhase(action.tls_id, value)
            elif action.action_type == "set_phase_duration":
                traci.trafficlight.setPhaseDuration(action.tls_id, value)
            elif action.action_type == "set_program":
                program_id = value["program_id"] if isinstance(value, dict) else value
                if isinstance(value, dict):
                    phases = [
                        traci.trafficlight.Phase(phase["duration"], phase["state"])
                        for phase in value["phases"]
                    ]
                    logic = traci.trafficlight.Logic(program_id, 0, 0, phases)
                    traci.trafficlight.setProgramLogic(action.tls_id, logic)
                traci.trafficlight.setProgram(action.tls_id, program_id)
                try:
                    replacement = MovementStateBuilder(self, action.tls_id)
                except Exception as exc:
                    traci.trafficlight.setProgram(action.tls_id, active_program)
                    results.append(
                        ActionResult(
                            action,
                            False,
                            f"movement topology rebuild failed: {exc}",
                            "topology_rebuild_failed",
                        )
                    )
                    continue
                if action.tls_id == self.tls_id:
                    self._movement_state_builder = replacement
            results.append(ActionResult(action, True, "applied"))
        return results

    def _control_action_domain(
        self,
        tls_id: str,
    ) -> tuple[int, set[str], int, set[int], str]:
        """Return the active phase count and available programs from SUMO."""
        try:
            programs = list(traci.trafficlight.getAllProgramLogics(tls_id))
            if not programs:
                raise RuntimeError("no signal programs returned")
            active_program = traci.trafficlight.getProgram(tls_id)
            current_phase = int(traci.trafficlight.getPhase(tls_id))
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
            current_phase,
            {
                target
                for source, target in self._legal_phase_transitions(active_logic)
                if source == current_phase
            },
            str(active_program),
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
