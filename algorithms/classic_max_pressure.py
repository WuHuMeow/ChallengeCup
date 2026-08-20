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
        pressures = {
            phase.phase_index: sum(
                movement.saturation_rate
                * (movement.queue_vehicles - movement.downstream_queue_vehicles)
                for movement in phase.movements
            )
            for phase in green_phases
        }
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
        legal_targets = {
            candidate
            for source, candidate in state.legal_phase_transitions
            if source == state.current_phase
        }
        if target not in legal_targets:
            return []
        current = next(
            (
                phase
                for phase in state.phase_movements
                if phase.phase_index == state.current_phase
            ),
            None,
        )
        if current is None or state.elapsed_phase_time < current.nominal_duration:
            return []
        return [
            ControlAction(
                tls_id=state.tls_id,
                action_type="set_phase",
                value=target,
                reason=f"classic_maxpressure target={target} pressure={pressures[target]:g}",
            )
        ]

    def reset(self) -> None:
        self.current_target_phase = None
        self.decision_history.clear()

    @property
    def name(self) -> str:
        return "classic_maxpressure"
