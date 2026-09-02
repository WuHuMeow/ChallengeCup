"""Instantaneous metrics available from the current TraCI state."""

from __future__ import annotations

from core.types import JointState, SimulationMetrics


def compute_metrics(
    step: int,
    state: JointState,
    arrived: int | None = None,
) -> SimulationMetrics:
    """根据当前 JointState 计算单步指标。

    Args:
        step: 当前仿真步。
        state: 当前联合状态。
        arrived: 本次运行累计到达目的地的车辆数；省略时读取 JointState。
    """
    queue_lengths = [q.queue_length for q in state.queues]
    waiting_times = [q.waiting_time for q in state.queues]

    avg_queue = sum(queue_lengths) / len(queue_lengths) if queue_lengths else 0.0
    max_queue = max(queue_lengths) if queue_lengths else 0.0
    avg_delay = sum(waiting_times) / len(waiting_times) if waiting_times else 0.0

    return SimulationMetrics(
        step=step,
        avg_queue_length=avg_queue,
        max_queue_length=max_queue,
        avg_delay=avg_delay,
        total_throughput=(
            state.completed_vehicle_count if arrived is None else arrived
        ),
        avg_travel_time=None,
        total_stops=None,
        fuel_consumption=None,
    )
