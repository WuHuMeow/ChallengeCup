"""全项目共享的核心数据类型与接口契约。

所有模块（engine / algorithms / ml / cloud / api）都应导入本文件中的类型，
确保云-边-端接口在数据层面统一。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


class TrafficLevel(str, Enum):
    """流量等级，用于场景变体生成。"""

    LOW = "low"        # 0.5x
    NORMAL = "normal"  # 1.0x
    HIGH = "high"      # 1.5x


@dataclass
class SceneMeta:
    """路口场景元数据，描述一个 SUMO 工程的所有输入文件。"""

    intersection_id: str
    name: str
    sumo_net: Path
    sumo_rou: Path
    sumo_flow: Path
    sumo_turn: Path
    sumo_cfg: Path
    timing_xlsx: Path
    map_png: Optional[Path] = None
    description: str = ""

    @property
    def scene_id(self) -> str:
        """Alias used by the strict matrix/evidence contract."""
        return self.intersection_id

    @property
    def lane_ids(self) -> tuple[str, ...]:
        """Lane ids parsed lazily from the SUMO network (preflight parity)."""
        try:
            from defusedxml import ElementTree as DefusedET

            root = DefusedET.parse(self.sumo_net).getroot()
            return tuple(
                lane.get("id")
                for lane in root.findall(".//lane")
                if lane.get("id")
            )
        except Exception:  # noqa: BLE001 - 无路网/损坏时扰动目标选择 fail-closed
            return ()


@dataclass
class Scene:
    """运行时场景对象，包含元数据和附加配置。"""

    meta: SceneMeta
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseInfo:
    """单个信号相位参数。"""

    phase_index: int
    phase_name: str
    green_time: float
    yellow_time: float
    red_time: float


@dataclass
class TimingPlan:
    """一个路口的完整信号配时方案。"""

    cycle_length: float
    phases: List[PhaseInfo]


@dataclass
class QueueState:
    """某进口道的排队状态。"""

    direction: str  # 例如 "north", "south", "east", "west"
    queue_length: float
    waiting_time: float
    vehicle_count: int
    capacity: float = 0.0  # 车道容量（辆）= 车道长度 / 7.5m；0 表示未知


@dataclass(frozen=True)
class PhaseTrafficState:
    """Traffic measurements associated with one legal SUMO signal phase."""

    phase_index: int
    signal_state: str
    nominal_duration: float
    incoming_lanes: tuple[str, ...]
    outgoing_lanes: tuple[str, ...]
    incoming_queue: float
    incoming_capacity: float
    outgoing_queue: float
    outgoing_capacity: float
    outgoing_occupancy: float


@dataclass
class VehicleState:
    """单辆车快照（高流量下按 vehicle_sample_rate 采样）。"""

    vehicle_id: str
    lane_id: str
    speed: float


def _require_number(
    name: str,
    value: Any,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    strict_minimum: bool = False,
    strict_maximum: bool = False,
) -> float:
    """Validate one numeric contract field and return it as a float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    if minimum is not None:
        if strict_minimum:
            if number <= minimum:
                raise ValueError(f"{name} must be > {minimum}")
        elif number < minimum:
            raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None:
        if strict_maximum:
            if number >= maximum:
                raise ValueError(f"{name} must be < {maximum}")
        elif number > maximum:
            raise ValueError(f"{name} must be <= {maximum}")
    return number


@dataclass
class JointState:
    """云-边-端协同的联合状态，作为算法 step() 的输入。

    云端预测服务、边缘控制算法、车端/灯端执行均围绕该状态交互。
    """

    step: int
    timestamp: float
    tls_id: str
    current_phase: int
    current_phase_name: str
    elapsed_phase_time: float
    queues: List[QueueState] = field(default_factory=list)
    flows: Dict[str, float] = field(default_factory=dict)  # 方向 -> vehicles / hour
    detector_values: Dict[str, float] = field(default_factory=dict)
    vehicles: List[VehicleState] = field(default_factory=list)  # 采样后的车辆快照
    arrival_history: List[int] = field(default_factory=list)  # 最近 300 步每步进入路网车辆数
    phase_states: List[PhaseTrafficState] = field(default_factory=list)
    # Movement-level view (core.movements.PhaseMovementState, kept as a loose
    # tuple to avoid a circular import); empty for legacy phase-state scenes.
    phase_movements: tuple = ()
    # Legal (source_phase, target_phase) transitions for the active program.
    legal_phase_transitions: tuple = ()


@dataclass
class ControlAction:
    """控制动作，由算法输出，经 engine/traci_bridge 写入 SUMO。"""

    tls_id: str
    action_type: str  # "set_phase" / "set_phase_duration" / "set_program"
    value: Any
    reason: str = ""
    issued_at: float | None = None  # 仿真秒；动作产生时刻
    expires_at: float | None = None  # 仿真秒；动作失效时刻（含）

    @classmethod
    def for_simulation_time(
        cls,
        tls_id: str,
        action_type: str,
        value: Any,
        reason: str = "",
        simulation_seconds: float | None = None,
        expires_at: float | None = None,
    ) -> "ControlAction":
        """Create an action stamped with the current simulation time."""
        return cls(
            tls_id,
            action_type,
            value,
            reason,
            issued_at=simulation_seconds,
            expires_at=expires_at,
        )


@dataclass(frozen=True)
class ActionResult:
    """Outcome for one attempted control action."""

    action: ControlAction
    accepted: bool
    detail: str
    reason_code: str = ""


@dataclass
class PredictionResult:
    """云端流量预测结果。"""

    horizon_steps: int
    horizon_seconds: float
    predicted_flows: Dict[str, float]  # 方向 -> 预测 horizon 内车辆数


@dataclass
class SimulationMetrics:
    """单步或多步汇总指标，对应 PDF 评分中的效率、安全、能耗维度。"""

    step: int
    avg_queue_length: float
    max_queue_length: float
    avg_delay: float
    total_throughput: int
    avg_travel_time: Optional[float]
    total_stops: Optional[int]
    fuel_consumption: Optional[float]


# 用于需要函数式接口的扩展点（如指标回调）。
class MetricsCallback(Protocol):
    def __call__(self, step: int, state: JointState, metrics: SimulationMetrics) -> None:
        ...


SAFETY_EVENT_TYPES = (
    "collision",
    "red_light",
    "illegal_transition",
    "harsh_braking",
    "teleport",
    "potential_conflict",
)


@dataclass(frozen=True)
class SafetyEvent:
    """One timestamped safety observation bound to its owning run."""

    run_id: str
    step: int
    simulation_seconds: float
    event_type: str
    entity_ids: tuple[str, ...] = ()
    source: str = ""
    confidence: float = 1.0
    detail: str = ""


@dataclass(frozen=True)
class MetricSummary:
    """Exact post-warmup run metrics derived from raw SUMO artifacts.

    All values are computed from completed vehicles only; unfinished trips are
    counted separately and never averaged into efficiency metrics.
    """

    completed_vehicle_count: int
    unfinished_vehicle_count: int
    throughput: int
    avg_travel_time_seconds: float | None = None
    avg_delay_seconds: float | None = None
    total_stops: int | None = None
    fuel_ml: float | None = None
    co2_g: float | None = None
    fuel_ml_per_completed: float | None = None
    co2_g_per_completed: float | None = None
    avg_queue_length_vehicles: float | None = None
    max_queue_length_vehicles: float | None = None
    safety_counts: dict[str, int] = field(
        default_factory=lambda: {name: 0 for name in SAFETY_EVENT_TYPES}
    )

    @classmethod
    def from_raw_outputs(
        cls,
        run_dir: Path | str,
        warmup_seconds: float,
    ) -> "MetricSummary":
        """Parse tripinfo/metrics/events exactly; warmup rows are excluded."""
        from defusedxml import ElementTree as DefusedET

        run_dir = Path(run_dir)
        warmup = float(warmup_seconds)

        completed_durations: list[float] = []
        completed_delays: list[float] = []
        completed_stops: list[float] = []
        completed_fuel: list[float] = []
        completed_co2: list[float] = []
        unfinished = 0
        tripinfo_path = run_dir / "tripinfo.xml"
        if tripinfo_path.is_file():
            root = DefusedET.parse(tripinfo_path).getroot()
            for trip in root.iter("tripinfo"):
                def _strict_time(attribute: str) -> float:
                    raw = trip.get(attribute)
                    if raw is None:
                        raise ValueError(
                            f"tripinfo row is missing {attribute}"
                        )
                    try:
                        value = float(raw)
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            f"tripinfo {attribute} is not a time: {raw!r}"
                        ) from exc
                    if value != value or value in (
                        float("inf"),
                        float("-inf"),
                    ):
                        raise ValueError(
                            f"tripinfo {attribute} is not finite: {raw!r}"
                        )
                    return value

                depart = _strict_time("depart")
                arrival = _strict_time("arrival")
                if depart < warmup:
                    continue
                if arrival < 0:
                    unfinished += 1
                    continue
                completed_durations.append(float(trip.get("duration", "nan")))
                completed_delays.append(float(trip.get("timeLoss", "nan")))
                completed_stops.append(float(trip.get("waitingCount", "0")))
                fuel_raw = trip.get("fuel_abs")
                co2_raw = trip.get("CO2_abs")
                emissions = trip.find("emissions")
                if fuel_raw is None and emissions is not None:
                    fuel_raw = emissions.get("fuel_abs")
                if co2_raw is None and emissions is not None:
                    co2_raw = emissions.get("CO2_abs")
                completed_fuel.append(float(fuel_raw) if fuel_raw is not None else 0.0)
                completed_co2.append(float(co2_raw) if co2_raw is not None else 0.0)
        completed = len(completed_durations)

        def _mean(values: list[float]) -> float | None:
            return sum(values) / len(values) if values else None

        avg_travel = _mean(completed_durations)
        avg_delay = _mean(completed_delays)
        total_stops = (
            int(sum(completed_stops)) if completed_stops else None
        )
        fuel_ml = sum(completed_fuel) if completed_fuel else None
        co2_g = sum(completed_co2) / 1000.0 if completed_co2 else None
        fuel_per = fuel_ml / completed if fuel_ml is not None and completed else None
        co2_per = co2_g / completed if co2_g is not None and completed else None

        avg_queue: float | None = None
        max_queue: float | None = None
        metrics_path = run_dir / "metrics.csv"
        if metrics_path.is_file():
            with metrics_path.open("r", encoding="utf-8", newline="") as handle:
                queue_rows = [
                    row
                    for row in csv.DictReader(handle)
                    if float(row.get("timestamp", "nan")) >= warmup
                ]
            avg_values = [
                float(row["avg_queue_length"])
                for row in queue_rows
                if row.get("avg_queue_length") not in (None, "")
            ]
            max_values = [
                float(row["max_queue_length"])
                for row in queue_rows
                if row.get("max_queue_length") not in (None, "")
            ]
            avg_queue = _mean(avg_values)
            max_queue = max(max_values) if max_values else None

        safety_counts: dict[str, int] = {
            name: 0 for name in SAFETY_EVENT_TYPES
        }
        events_path = run_dir / "events.csv"
        if events_path.is_file():
            with events_path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    seconds = row.get("simulation_seconds")
                    try:
                        if seconds is None or float(seconds) < warmup:
                            continue
                    except ValueError:
                        continue
                    event_type = row.get("type", "")
                    if event_type in safety_counts:
                        safety_counts[event_type] += 1

        return cls(
            completed_vehicle_count=completed,
            unfinished_vehicle_count=unfinished,
            throughput=completed,
            avg_travel_time_seconds=avg_travel,
            avg_delay_seconds=avg_delay,
            total_stops=total_stops,
            fuel_ml=fuel_ml,
            co2_g=co2_g,
            fuel_ml_per_completed=fuel_per,
            co2_g_per_completed=co2_per,
            avg_queue_length_vehicles=avg_queue,
            max_queue_length_vehicles=max_queue,
            safety_counts=safety_counts,
        )
