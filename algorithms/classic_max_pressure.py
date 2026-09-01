"""Independent classic MaxPressure baseline."""

from __future__ import annotations

from algorithms.base import BaseControlAlgorithm
from core.types import ControlAction, JointState, Scene


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
