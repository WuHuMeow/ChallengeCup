"""全项目共享的核心数据类型与接口契约。

所有模块（engine / algorithms / ml / cloud / api）都应导入本文件中的类型，
确保云-边-端接口在数据层面统一。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import csv
import math
from pathlib import Path
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional, Protocol

if TYPE_CHECKING:
    from core.movements import PhaseMovementState


def _require_number(
    name: str,
    value: object,
    *,
    minimum: float | None = None,
    strict_minimum: bool = False,
    maximum: float | None = None,
) -> None:
    """Validate a numeric contract without changing the caller's value."""
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric: {value!r}") from exc
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite: {value!r}")
    if minimum is not None:
        invalid = numeric <= minimum if strict_minimum else numeric < minimum
        if invalid:
            operator = ">" if strict_minimum else ">="
            raise ValueError(f"{name} must be {operator} {minimum}: {value!r}")
    if maximum is not None and numeric > maximum:
        raise ValueError(f"{name} must be <= {maximum}: {value!r}")


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

    def __post_init__(self) -> None:
        _require_number("queue_length", self.queue_length, minimum=0)
        _require_number("waiting_time", self.waiting_time, minimum=0)
        _require_number("vehicle_count", self.vehicle_count, minimum=0)
        _require_number("capacity", self.capacity, minimum=0)


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

    def __post_init__(self) -> None:
        _require_number("phase_index", self.phase_index, minimum=0)
        _require_number(
            "nominal_duration",
            self.nominal_duration,
            minimum=0,
            strict_minimum=True,
        )
        _require_number("incoming_queue", self.incoming_queue, minimum=0)
        _require_number("incoming_capacity", self.incoming_capacity, minimum=0)
        _require_number("outgoing_queue", self.outgoing_queue, minimum=0)
        _require_number("outgoing_capacity", self.outgoing_capacity, minimum=0)
        _require_number(
            "outgoing_occupancy",
            self.outgoing_occupancy,
            minimum=0,
            maximum=1,
        )


@dataclass
class VehicleState:
    """单辆车快照（高流量下按 vehicle_sample_rate 采样）。"""

    vehicle_id: str
    lane_id: str
    speed: float


@dataclass(frozen=True)
class SafetyVehicleState:
    """Run-scoped vehicle observation used only for safety derivation."""

    vehicle_id: str
    lane_id: str
    speed_mps: float
    position_xy: tuple[float, float]
    next_tls_id: str | None = None
    distance_to_tls_m: float | None = None
    next_tls_link_index: int | None = None
    next_tls_state: str | None = None

    def __post_init__(self) -> None:
        _require_number("speed_mps", self.speed_mps, minimum=0)
        if len(self.position_xy) != 2:
            raise ValueError("position_xy must contain x and y")
        for coordinate in self.position_xy:
            _require_number("position_xy", coordinate)
        if self.distance_to_tls_m is not None:
            _require_number("distance_to_tls_m", self.distance_to_tls_m, minimum=0)


@dataclass(frozen=True)
class CollisionRecord:
    """One raw SUMO collision with collider/victim roles preserved."""

    collider_id: str
    victim_id: str
    collider_type: str = ""
    victim_type: str = ""
    collider_speed_mps: float | None = None
    victim_speed_mps: float | None = None
    collision_type: str = ""
    lane_id: str = ""
    position_m: float | None = None

    def __post_init__(self) -> None:
        for name in ("collider_speed_mps", "victim_speed_mps", "position_m"):
            value = getattr(self, name)
            if value is not None:
                _require_number(name, value, minimum=0)


@dataclass
class JointState:
    """云-边-端协同的联合状态，作为算法 step() 的输入。

    云端预测服务、边缘控制算法、车端/灯端执行均围绕该状态交互。
    """

    step: int
    timestamp: float  # Simulation seconds.
    tls_id: str
    current_phase: int
    current_phase_name: str
    elapsed_phase_time: float
    queues: List[QueueState] = field(default_factory=list)
    flows: Dict[str, float] = field(default_factory=dict)  # 方向 ->  vehicles / hour
    detector_values: Dict[str, float] = field(default_factory=dict)
    vehicles: List[VehicleState] = field(default_factory=list)  # 采样后的车辆快照
    arrival_history: List[int] = field(default_factory=list)  # 最近 300 步每步进入路网车辆数
    completed_vehicle_count: int = 0  # 本次运行累计完成行程的车辆数
    phase_states: List[PhaseTrafficState] = field(default_factory=list)
    phase_movements: tuple[PhaseMovementState, ...] = ()
    legal_phase_transitions: tuple[tuple[int, int], ...] = ()
    safety_vehicles: tuple[SafetyVehicleState, ...] = ()
    collisions: tuple[CollisionRecord, ...] = ()
    collision_vehicle_ids: tuple[str, ...] = ()
    starting_teleport_vehicle_ids: tuple[str, ...] = ()
    ending_teleport_vehicle_ids: tuple[str, ...] = ()
    teleport_vehicle_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_number("step", self.step, minimum=0)
        _require_number("timestamp", self.timestamp, minimum=0)
        _require_number("current_phase", self.current_phase, minimum=0)
        _require_number("elapsed_phase_time", self.elapsed_phase_time, minimum=0)
        _require_number(
            "completed_vehicle_count",
            self.completed_vehicle_count,
            minimum=0,
        )
        from core.movements import PhaseMovementState

        try:
            phase_movements = tuple(self.phase_movements)
        except TypeError as exc:
            raise ValueError(
                "phase_movements must be an iterable of PhaseMovementState"
            ) from exc
        if not all(
            isinstance(phase, PhaseMovementState) for phase in phase_movements
        ):
            raise ValueError(
                "phase_movements must contain only PhaseMovementState values"
            )
        self.phase_movements = phase_movements
        try:
            legal_phase_transitions = tuple(
                tuple(transition) for transition in self.legal_phase_transitions
            )
        except TypeError as exc:
            raise ValueError("legal_phase_transitions must be iterable") from exc
        if not all(
            len(transition) == 2
            and all(
                isinstance(phase_index, int)
                and not isinstance(phase_index, bool)
                and phase_index >= 0
                for phase_index in transition
            )
            for transition in legal_phase_transitions
        ):
            raise ValueError(
                "legal_phase_transitions must contain non-negative integer pairs"
            )
        self.legal_phase_transitions = legal_phase_transitions
        try:
            safety_vehicles = tuple(self.safety_vehicles)
        except TypeError as exc:
            raise ValueError("safety_vehicles must be iterable") from exc
        if not all(
            isinstance(vehicle, SafetyVehicleState)
            for vehicle in safety_vehicles
        ):
            raise ValueError(
                "safety_vehicles must contain only SafetyVehicleState values"
            )
        self.safety_vehicles = safety_vehicles
        try:
            collisions = tuple(self.collisions)
        except TypeError as exc:
            raise ValueError("collisions must be iterable") from exc
        if not all(isinstance(collision, CollisionRecord) for collision in collisions):
            raise ValueError("collisions must contain only CollisionRecord values")
        self.collisions = collisions
        self.collision_vehicle_ids = tuple(self.collision_vehicle_ids)
        self.starting_teleport_vehicle_ids = tuple(
            self.starting_teleport_vehicle_ids
        )
        self.ending_teleport_vehicle_ids = tuple(self.ending_teleport_vehicle_ids)
        self.teleport_vehicle_ids = tuple(self.teleport_vehicle_ids)


CONTROL_ACTION_VALIDITY_SECONDS = 60.0


@dataclass
class ControlAction:
    """控制动作，由算法输出，经 engine/traci_bridge 写入 SUMO。"""

    tls_id: str
    action_type: str  # "set_phase" / "set_phase_duration" / "set_program"
    value: Any
    reason: str = ""
    issued_at: float | None = None
    expires_at: float | None = None

    ALLOWED_ACTION_TYPES: ClassVar[frozenset[str]] = frozenset({
        "set_phase",
        "set_phase_duration",
        "set_program",
    })

    @classmethod
    def for_simulation_time(
        cls,
        tls_id: str,
        action_type: str,
        value: Any,
        reason: str,
        simulation_seconds: float,
    ) -> "ControlAction":
        issued_at = float(simulation_seconds)
        return cls(
            tls_id,
            action_type,
            value,
            reason,
            issued_at=issued_at,
            expires_at=issued_at + CONTROL_ACTION_VALIDITY_SECONDS,
        )


@dataclass(frozen=True)
class ActionResult:
    """Outcome for one attempted control action."""

    action: ControlAction
    accepted: bool
    detail: str
    reason_code: str = ""


@dataclass(frozen=True)
class SafetyEvent:
    """One run-scoped observed or derived safety event."""

    run_id: str
    step: int
    simulation_seconds: float
    event_type: str
    entity_ids: tuple[str, ...]
    source: str
    confidence: float
    detail: str = ""

    def __post_init__(self) -> None:
        _require_number("step", self.step, minimum=0)
        _require_number("simulation_seconds", self.simulation_seconds, minimum=0)
        _require_number("confidence", self.confidence, minimum=0, maximum=1)
        object.__setattr__(self, "entity_ids", tuple(self.entity_ids))


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
    avg_queue_length: Optional[float]
    max_queue_length: Optional[float]
    avg_delay: Optional[float]
    total_throughput: Optional[int]
    avg_travel_time: Optional[float] = None
    total_stops: Optional[int] = None
    fuel_consumption: Optional[float] = None

    def __post_init__(self) -> None:
        _require_number("step", self.step, minimum=0)
        for name in (
            "avg_queue_length",
            "max_queue_length",
            "avg_delay",
            "total_throughput",
            "avg_travel_time",
            "total_stops",
            "fuel_consumption",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_number(name, value, minimum=0)


@dataclass(frozen=True)
class MetricSummary:
    """Completed and unfinished vehicle metrics with explicit units."""

    completed_vehicle_count: int
    unfinished_vehicle_count: int
    throughput: int
    avg_travel_time_seconds: float | None
    avg_delay_seconds: float | None
    total_stops: int | None
    fuel_ml: float | None
    co2_g: float | None
    fuel_ml_per_completed: float | None
    co2_g_per_completed: float | None
    avg_queue_length_vehicles: float | None = None
    max_queue_length_vehicles: float | None = None
    collision_count: int = 0
    red_light_count: int = 0
    illegal_transition_count: int = 0
    harsh_braking_count: int = 0
    teleport_count: int = 0
    potential_conflict_count: int = 0

    @property
    def safety_counts(self) -> dict[str, int]:
        """Return the six frozen safety counters without unit ambiguity."""
        return {
            "collision": self.collision_count,
            "red_light": self.red_light_count,
            "illegal_transition": self.illegal_transition_count,
            "harsh_braking": self.harsh_braking_count,
            "teleport": self.teleport_count,
            "potential_conflict": self.potential_conflict_count,
        }

    @classmethod
    def from_tripinfo(
        cls,
        completed: Iterable[Mapping[str, object]],
        unfinished: Iterable[Mapping[str, object]],
    ) -> "MetricSummary":
        completed_rows = list(completed)
        unfinished_rows = list(unfinished)
        count = len(completed_rows)

        def values(attribute: str) -> list[float] | None:
            result = []
            for row in completed_rows:
                raw = row.get(attribute)
                if raw is None:
                    return None
                try:
                    numeric = float(raw)
                except (TypeError, ValueError):
                    return None
                if not math.isfinite(numeric) or numeric < 0:
                    return None
                result.append(numeric)
            return result or None

        def emission_values(attribute: str) -> list[float] | None:
            result = []
            for row in completed_rows:
                raw = row.get(attribute)
                emissions = row.get("emissions")
                if raw is None and isinstance(emissions, Mapping):
                    raw = emissions.get(attribute)
                if raw is None:
                    return None
                try:
                    numeric = float(raw)
                except (TypeError, ValueError):
                    return None
                if not math.isfinite(numeric) or numeric < 0:
                    return None
                result.append(numeric)
            return result or None

        durations = values("duration")
        delays = values("timeLoss")
        stops = values("waitingCount")
        fuels = emission_values("fuel_abs")
        co2_mg = emission_values("CO2_abs")
        fuel_ml = sum(fuels) if fuels is not None else None
        co2_g = sum(co2_mg) / 1000.0 if co2_mg is not None else None
        return cls(
            completed_vehicle_count=count,
            unfinished_vehicle_count=len(unfinished_rows),
            throughput=count,
            avg_travel_time_seconds=(
                sum(durations) / count if durations is not None else None
            ),
            avg_delay_seconds=(
                sum(delays) / count if delays is not None else None
            ),
            total_stops=int(sum(stops)) if stops is not None else None,
            fuel_ml=fuel_ml,
            co2_g=co2_g,
            fuel_ml_per_completed=(fuel_ml / count if fuel_ml is not None else None),
            co2_g_per_completed=(co2_g / count if co2_g is not None else None),
        )

    @classmethod
    def from_raw_outputs(
        cls,
        run_dir: Path,
        warmup_seconds: float,
    ) -> "MetricSummary":
        """Derive the frozen metric contract from one run's raw outputs.

        SUMO marks tripinfo rows still present at shutdown with ``arrival < 0``.
        Both completed and unfinished counts use the same depart-time exposure
        boundary. Time-series and event samples use their simulation timestamp.
        """
        _require_number("warmup_seconds", warmup_seconds, minimum=0)
        warmup = float(warmup_seconds)
        run_dir = Path(run_dir)

        from defusedxml import ElementTree as ET

        root = ET.parse(run_dir / "tripinfo.xml").getroot()
        completed: list[dict[str, object]] = []
        unfinished: list[dict[str, object]] = []
        for element in root.iter("tripinfo"):
            depart_raw = element.get("depart")
            if depart_raw is None:
                raise ValueError("tripinfo depart is required")
            try:
                depart = float(depart_raw)
            except ValueError as exc:
                raise ValueError("tripinfo depart must be numeric") from exc
            if not math.isfinite(depart) or depart < 0:
                raise ValueError("tripinfo depart must be finite and non-negative")
            if depart < warmup:
                continue
            row: dict[str, object] = dict(element.attrib)
            emissions = element.find("emissions")
            if emissions is not None:
                row["emissions"] = dict(emissions.attrib)
            arrival_raw = element.get("arrival")
            if arrival_raw is None:
                raise ValueError("tripinfo arrival is required")
            try:
                arrival = float(arrival_raw)
            except ValueError as exc:
                raise ValueError("tripinfo arrival must be numeric") from exc
            if not math.isfinite(arrival):
                raise ValueError("tripinfo arrival must be finite")
            is_unfinished = arrival < 0
            (unfinished if is_unfinished else completed).append(row)

        base = cls.from_tripinfo(completed, unfinished)

        averages: list[float] = []
        maximums: list[float] = []
        metrics_path = run_dir / "metrics.csv"
        if metrics_path.exists() and metrics_path.stat().st_size > 0:
            with metrics_path.open(newline="", encoding="utf-8") as source:
                for row in csv.DictReader(source):
                    timestamp_raw = row.get("timestamp")
                    if timestamp_raw in (None, ""):
                        raise ValueError("metrics timestamp is required")
                    try:
                        timestamp = float(timestamp_raw)
                    except ValueError as exc:
                        raise ValueError("metrics timestamp must be numeric") from exc
                    if not math.isfinite(timestamp) or timestamp < 0:
                        raise ValueError("metrics timestamp must be finite and non-negative")
                    if timestamp < warmup:
                        continue
                    try:
                        average_raw = row.get("avg_queue_length")
                        maximum_raw = row.get("max_queue_length")
                        if average_raw not in (None, ""):
                            average = float(average_raw)
                            if math.isfinite(average) and average >= 0:
                                averages.append(average)
                        if maximum_raw not in (None, ""):
                            maximum = float(maximum_raw)
                            if math.isfinite(maximum) and maximum >= 0:
                                maximums.append(maximum)
                    except ValueError:
                        continue

        safety = {name: 0 for name in (
            "collision",
            "red_light",
            "illegal_transition",
            "harsh_braking",
            "teleport",
            "potential_conflict",
        )}
        events_path = run_dir / "events.csv"
        if events_path.exists() and events_path.stat().st_size > 0:
            with events_path.open(newline="", encoding="utf-8") as source:
                for row in csv.DictReader(source):
                    event_type = row.get("type", "")
                    if event_type not in safety:
                        continue
                    try:
                        timestamp = float(row.get("simulation_seconds", ""))
                    except (TypeError, ValueError) as exc:
                        raise ValueError(
                            "safety simulation_seconds must be numeric"
                        ) from exc
                    if not math.isfinite(timestamp) or timestamp < 0:
                        raise ValueError(
                            "safety simulation_seconds must be finite and non-negative"
                        )
                    if timestamp >= warmup:
                        safety[event_type] += 1

        return cls(
            completed_vehicle_count=base.completed_vehicle_count,
            unfinished_vehicle_count=base.unfinished_vehicle_count,
            throughput=base.throughput,
            avg_travel_time_seconds=base.avg_travel_time_seconds,
            avg_delay_seconds=base.avg_delay_seconds,
            total_stops=base.total_stops,
            fuel_ml=base.fuel_ml,
            co2_g=base.co2_g,
            fuel_ml_per_completed=base.fuel_ml_per_completed,
            co2_g_per_completed=base.co2_g_per_completed,
            avg_queue_length_vehicles=(
                sum(averages) / len(averages) if averages else None
            ),
            max_queue_length_vehicles=max(maximums) if maximums else None,
            collision_count=safety["collision"],
            red_light_count=safety["red_light"],
            illegal_transition_count=safety["illegal_transition"],
            harsh_braking_count=safety["harsh_braking"],
            teleport_count=safety["teleport"],
            potential_conflict_count=safety["potential_conflict"],
        )


# 用于需要函数式接口的扩展点（如指标回调）。
class MetricsCallback(Protocol):
    def __call__(self, step: int, state: JointState, metrics: SimulationMetrics) -> None:
        ...
