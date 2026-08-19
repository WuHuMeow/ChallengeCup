"""全项目共享的核心数据类型与接口契约。

所有模块（engine / algorithms / ml / cloud / api）都应导入本文件中的类型，
确保云-边-端接口在数据层面统一。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Protocol


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
    flows: Dict[str, float] = field(default_factory=dict)  # 方向 ->  vehicles / hour
    detector_values: Dict[str, float] = field(default_factory=dict)
    vehicles: List[VehicleState] = field(default_factory=list)  # 采样后的车辆快照
    arrival_history: List[int] = field(default_factory=list)  # 最近 300 步每步进入路网车辆数
    phase_states: List[PhaseTrafficState] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_number("step", self.step, minimum=0)
        _require_number("timestamp", self.timestamp, minimum=0)
        _require_number("current_phase", self.current_phase, minimum=0)
        _require_number("elapsed_phase_time", self.elapsed_phase_time, minimum=0)


@dataclass
class ControlAction:
    """控制动作，由算法输出，经 engine/traci_bridge 写入 SUMO。"""

    tls_id: str
    action_type: str  # "set_phase" / "set_phase_duration" / "set_program"
    value: Any
    reason: str = ""

    ALLOWED_ACTION_TYPES: ClassVar[frozenset[str]] = frozenset({
        "set_phase",
        "set_phase_duration",
        "set_program",
    })


@dataclass(frozen=True)
class ActionResult:
    """Outcome for one attempted control action."""

    action: ControlAction
    accepted: bool
    detail: str


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


# 用于需要函数式接口的扩展点（如指标回调）。
class MetricsCallback(Protocol):
    def __call__(self, step: int, state: JointState, metrics: SimulationMetrics) -> None:
        ...
