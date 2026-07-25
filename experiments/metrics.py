"""仿真指标计算。

基于 TraCI 实时状态计算评分所需的效率、安全、能耗指标。
精确指标（如行程时间、燃油消耗）建议结合 SUMO tripinfo 输出二次校准。
"""

from __future__ import annotations

from core.types import JointState, SimulationMetrics


def compute_metrics(step: int, state: JointState, arrived: int = 0) -> SimulationMetrics:
    """根据当前 JointState 计算单步指标。

    Args:
        step: 当前仿真步。
        state: 当前联合状态。
        arrived: 本步到达目的地的车辆数（用于估算吞吐量）。
    """
    queue_lengths = [q.queue_length for q in state.queues]
    waiting_times = [q.waiting_time for q in state.queues]

    avg_queue = sum(queue_lengths) / len(queue_lengths) if queue_lengths else 0.0
    max_queue = max(queue_lengths) if queue_lengths else 0.0
    avg_delay = sum(waiting_times) / len(waiting_times) if waiting_times else 0.0

    total_vehicles = sum(q.vehicle_count for q in state.queues)
    # 停车次数近似：排队车辆数（后续可用 tripinfo 中的 stops 校准）
    total_stops = int(sum(queue_lengths))
    # 燃油消耗近似：与车辆数和等待时间正相关（后续可用 tripinfo 中的 fuelAbs 校准）
    fuel_consumption = total_vehicles * 0.01 + avg_delay * 0.001

    return SimulationMetrics(
        step=step,
        avg_queue_length=avg_queue,
        max_queue_length=max_queue,
        avg_delay=avg_delay,
        total_throughput=arrived,
        avg_travel_time=0.0,  # 需 tripinfo 输出
        total_stops=total_stops,
        fuel_consumption=fuel_consumption,
    )
