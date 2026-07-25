"""全项目共享的核心数据类型与接口契约。

所有模块（engine / algorithms / ml / cloud / api）都应导入本文件中的类型，
确保云-边-端接口在数据层面统一。
"""

from __future__ import annotations

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
    queues: List[QueueState]
    flows: Dict[str, float]  # 方向 ->  vehicles / hour
    detector_values: Dict[str, float] = field(default_factory=dict)
    vehicles: List[VehicleState] = field(default_factory=list)  # 采样后的车辆快照
    arrival_history: List[int] = field(default_factory=list)  # 最近 300 步每步进入路网车辆数


@dataclass
class ControlAction:
    """控制动作，由算法输出，经 engine/traci_bridge 写入 SUMO。"""

    tls_id: str
    action_type: str  # "set_phase" / "set_phase_duration" / "set_program"
    value: Any
    reason: str = ""


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
    avg_travel_time: float
    total_stops: int
    fuel_consumption: float


# 用于需要函数式接口的扩展点（如指标回调）。
class MetricsCallback(Protocol):
    def __call__(self, step: int, state: JointState, metrics: SimulationMetrics) -> None:
        ...
