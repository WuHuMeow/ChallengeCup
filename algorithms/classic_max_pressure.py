"""Independent classic MaxPressure baseline."""

from __future__ import annotations

from algorithms.base import BaseControlAlgorithm
from core.types import ControlAction, JointState, Scene

# 经典基线的动作窗口：issued 后 60 仿真秒内有效（安全执行器可据此拒绝过期动作）。
ACTION_WINDOW_SECONDS = 60.0


class ClassicMaxPressureAlgorithm(BaseControlAlgorithm):
    """Classic unnormalised movement pressure with deterministic tie-breaking."""

    def __init__(self) -> None:
        self.scene: Scene | None = None
        self.current_target_phase: int | None = None
        self.decision_history: list[int] = []

    def init(self, scene: Scene) -> None:
        self.scene = scene

    def step(self, state: JointState) -> list[ControlAction]:
        green_phases = [
            phase
            for phase in state.phase_movements
            if any(signal in phase.signal_state for signal in "Gg")
        ]
        if not green_phases:
            return []
        pressures = self.score_breakdown(state)
        target = max(
            green_phases,
            key=lambda phase: (
                pressures[phase.phase_index],
                phase.phase_index == state.current_phase,
                -phase.phase_index,
            ),
        ).phase_index
        self.current_target_phase = target
        self.decision_history.append(target)
        if target == state.current_phase:
            return []
        return [
            ControlAction.for_simulation_time(
                state.tls_id,
                "set_phase",
                target,
                f"classic_maxpressure target={target} pressure={pressures[target]:g}",
                state.timestamp,
                expires_at=state.timestamp + ACTION_WINDOW_SECONDS,
            )
        ]

    def score_breakdown(self, state: JointState) -> dict[int, float]:
        """Return the original unnormalised movement pressure for each green phase."""
        return {
            phase.phase_index: sum(
                movement.saturation_rate
                * (movement.queue_vehicles - movement.downstream_queue_vehicles)
                for movement in phase.movements
            )
            for phase in state.phase_movements
            if any(signal in phase.signal_state for signal in "Gg")
        }

    def reset(self) -> None:
        self.current_target_phase = None
        self.decision_history.clear()

    @property
    def name(self) -> str:
        return "classic_maxpressure"

    @property
    def manifest(self) -> dict[str, object]:
        """Classic baseline carries no capacity-aware enhancement flags."""
        return {"name": self.name}
