"""Traceable fixed-time baseline."""

from __future__ import annotations

from algorithms.base import BaseControlAlgorithm
from algorithms.fixed_time_plan import FixedTimePlanResolver, ResolvedTimingPlan
from core.types import ControlAction, JointState, Scene


class FixedTimeAlgorithm(BaseControlAlgorithm):
    """Freeze one source-addressable fixed plan before each run."""

    def __init__(self, use_excel_timing: bool = False) -> None:
        # Kept only for call-site compatibility; source precedence is fixed.
        self.use_excel_timing = use_excel_timing
        self.scene: Scene | None = None
        self.resolved_timing_plan: ResolvedTimingPlan | None = None
        self._program_applied = False
        self._resolver = FixedTimePlanResolver()

    def init(self, scene: Scene) -> None:
        self.scene = scene
        self.resolved_timing_plan = self._resolver.resolve(scene)
        self._program_applied = False

    def step(self, state: JointState) -> list[ControlAction]:
        """Install the frozen plan once through the shared action channel."""
        if self.resolved_timing_plan is None or self._program_applied:
            return []
        self._program_applied = True
        return [
            ControlAction(
                tls_id=state.tls_id,
                action_type="set_program",
                value={
                    "program_id": self.resolved_timing_plan.program_id,
                    "phases": [
                        {"duration": phase.duration, "state": phase.state}
                        for phase in self.resolved_timing_plan.phases
                    ],
                },
                reason="install frozen fixed-time plan",
            )
        ]

    def reset(self) -> None:
        self.scene = None
        self.resolved_timing_plan = None
        self._program_applied = False

    @property
    def name(self) -> str:
        return "fixed_time"

    @property
    def manifest(self) -> dict[str, object]:
        payload = super().manifest
        payload["timing_plan"] = (
            self.resolved_timing_plan.as_manifest()
            if self.resolved_timing_plan is not None
            else None
        )
        return payload
