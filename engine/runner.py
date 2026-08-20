"""Single-run simulation lifecycle."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import List, Optional

from algorithms.base import BaseControlAlgorithm
from core.config import get_config
from core.run_models import RunStatus
from core.types import ControlAction, Scene
from engine.artifacts import RunArtifacts
from engine.collector import MetricsCollector, StepLogger
from engine.edge_channel import EdgeChannel
from engine.events import EventLogger
from engine.safety import SafetyObservationCollector
from engine.traci_bridge import TraCIBridge, traci
from experiments.metrics import compute_metrics
from experiments.summary import write_run_summary

logger = logging.getLogger(__name__)


class SimulationRunner:
    """Run one SUMO simulation and persist its outputs."""

    def __init__(
        self,
        scene: Scene,
        algorithm: BaseControlAlgorithm,
        sumo_binary: Optional[str] = None,
        output_csv: Optional[Path] = None,
        snapshot_interval: Optional[int] = None,
        additional_files: Optional[List[Path]] = None,
        sumo_cfg: Optional[Path] = None,
        bridge: Optional[object] = None,
        seed: Optional[int] = None,
        step_log_csv: Optional[Path] = None,
        events_csv: Optional[Path] = None,
        artifacts: Optional[RunArtifacts] = None,
        state_channel: Optional[EdgeChannel] = None,
    ) -> None:
        self.scene = scene
        self.algorithm = algorithm
        self.seed = seed
        self.sumo_binary = sumo_binary or get_config().get("sumo.binary", "sumo")
        self.snapshot_interval = snapshot_interval or get_config().get(
            "metrics.snapshot_interval", 60
        )
        self.additional_files = additional_files or []
        self.artifacts = artifacts
        self.state_channel = state_channel

        if artifacts is not None:
            output_csv = artifacts.metrics
            step_log_csv = artifacts.step_log
            events_csv = artifacts.events
        if output_csv is None:
            output_root = Path(get_config().get("paths.output_root", "./output"))
            output_csv = (
                output_root
                / "csv"
                / f"{scene.meta.intersection_id}_{algorithm.name}.csv"
            )
        self.output_csv = output_csv
        self.collector: Optional[MetricsCollector] = None
        self.metrics_history: List[dict] = []
        self.step_logger = StepLogger(step_log_csv) if step_log_csv else None
        self.event_logger = (
            EventLogger(
                events_csv,
                run_id=artifacts.run_id if artifacts is not None else "",
                intersection_id=scene.meta.intersection_id,
                algorithm=algorithm.name,
            )
            if events_csv
            else None
        )
        self._terminal_reason = ""
        self._sumo_version_value = "unknown"
        self._last_simulation_time = 0.0
        self.safety_collector = SafetyObservationCollector(
            artifacts.run_id if artifacts is not None else ""
        )
        self._previous_safety_state = None

        if bridge is not None:
            self.bridge = bridge
            self.bridge.event_callback = self._record_bridge_event
        else:
            cfg = Path(sumo_cfg) if sumo_cfg is not None else scene.meta.sumo_cfg
            enhanced = (
                Path(__file__).resolve().parent
                / "configs"
                / f"demo_{scene.meta.intersection_id}.sumocfg"
            )
            if sumo_cfg is None and enhanced.exists():
                cfg = enhanced
            self.bridge = TraCIBridge(
                cfg,
                binary=self.sumo_binary,
                additional_files=self.additional_files,
                artifacts=artifacts,
                seed=self.seed,
                event_callback=self._record_bridge_event,
            )

    def _record_bridge_event(self, event_type: str, detail: str) -> None:
        if self.event_logger:
            self.event_logger.log(len(self.metrics_history), event_type, detail)

    def run(
        self,
        steps: Optional[int] = None,
        stop_event: Optional[Event] = None,
    ) -> List[dict]:
        """Run the simulation and persist one truthful terminal state."""
        steps = steps or get_config().get("sumo.default_simulation_steps", 36000)
        self.collector = MetricsCollector(self.output_csv)
        self.metrics_history = []
        self._previous_safety_state = None
        started_at = datetime.now(timezone.utc).isoformat()
        status = RunStatus.RUNNING
        reason = ""
        body_exception = False
        last_step = 0

        try:
            self.bridge.start()
            self._sumo_version_value = self._sumo_version()
            self.algorithm.init(self.scene)
            if self.event_logger:
                self.event_logger.log(
                    0,
                    "run_start",
                    f"intersection={self.scene.meta.intersection_id}"
                    f" algorithm={self.algorithm.name}",
                )
            for step in range(steps):
                last_step = step
                if stop_event is not None and stop_event.is_set():
                    status = RunStatus.STOPPED
                    reason = "stop requested"
                    break
                tick_outcome = self._tick(step)
                if tick_outcome == "disconnected":
                    status = RunStatus.DISCONNECTED
                    reason = self._terminal_reason
                    break
                if tick_outcome == "configured_end":
                    status = RunStatus.COMPLETED
                    break
                if tick_outcome == "exhausted":
                    if step + 1 < steps:
                        status = RunStatus.ENDED_EARLY
                        reason = "SUMO exhausted before target steps"
                    else:
                        status = RunStatus.COMPLETED
                    break
            else:
                status = RunStatus.COMPLETED
        except KeyboardInterrupt:
            status = RunStatus.INTERRUPTED
            reason = "KeyboardInterrupt"
            body_exception = True
            raise
        except Exception as exc:
            status = RunStatus.FAILED
            reason = str(exc) or type(exc).__name__
            body_exception = True
            raise
        finally:
            cleanup_errors: list[Exception] = []
            for save in (
                self.collector.save if self.collector else None,
                self.step_logger.save if self.step_logger else None,
            ):
                if save is None:
                    continue
                try:
                    save()
                except Exception as exc:
                    cleanup_errors.append(exc)
            try:
                self.bridge.close()
            except Exception as exc:
                cleanup_errors.append(exc)

            if (
                not cleanup_errors
                and self.artifacts is not None
                and status in (RunStatus.COMPLETED, RunStatus.ENDED_EARLY)
            ):
                core_outputs = (
                    self.artifacts.tripinfo,
                    self.artifacts.stats,
                    self.artifacts.trajectory,
                )
                if all(
                    path.exists() and path.stat().st_size > 0
                    for path in core_outputs
                ):
                    try:
                        write_run_summary(self.artifacts)
                    except Exception as exc:
                        cleanup_errors.append(exc)

            if cleanup_errors and not body_exception:
                status = RunStatus.FAILED
                reason = str(cleanup_errors[0]) or type(cleanup_errors[0]).__name__

            if self.event_logger:
                try:
                    self.event_logger.log(last_step, "terminal", status.value)
                    self.event_logger.save()
                except Exception as exc:
                    cleanup_errors.append(exc)
                    if not body_exception:
                        status = RunStatus.FAILED
                        reason = str(exc) or type(exc).__name__

            if self.artifacts is not None:
                generated_files = [
                    self.artifacts.metrics,
                    self.artifacts.step_log,
                    self.artifacts.events,
                    self.artifacts.tripinfo,
                    self.artifacts.stats,
                    self.artifacts.trajectory,
                    self.artifacts.queues,
                    self.artifacts.summary,
                ]
                try:
                    self.artifacts.write_metadata(
                        status.value,
                        reason,
                        generated_files,
                        started_at=started_at,
                        ended_at=datetime.now(timezone.utc).isoformat(),
                        sumo_version=self._sumo_version_value,
                        requested_steps=steps,
                        final_simulation_time=self._last_simulation_time,
                        step_length=getattr(self.bridge, "step_length", None),
                        configured_end_time=getattr(
                            self.bridge,
                            "configured_end_time",
                            None,
                        ),
                        movement_capacity_inputs=getattr(
                            self.bridge,
                            "movement_capacity_inputs",
                            None,
                        ),
                    )
                except Exception as exc:
                    cleanup_errors.append(exc)
                    if not body_exception:
                        status = RunStatus.FAILED
                        reason = str(exc) or type(exc).__name__
            if cleanup_errors and not body_exception:
                raise cleanup_errors[0]

        return self.metrics_history

    def _tick(self, step: int) -> str:
        """Advance one step and return continue, exhausted, or disconnected."""
        try:
            raw_state = self.bridge.get_state()
            control_state = raw_state
            if self.state_channel is not None:
                self.state_channel.send(raw_state)
                control_state = self.state_channel.receive()
            if control_state is None:
                actions: List[ControlAction] = []
                if self.event_logger:
                    self.event_logger.log(
                        step, "channel_wait", "delayed state unavailable"
                    )
            else:
                actions = self.algorithm.step(control_state)
            action_results = self.bridge.apply_actions(actions) or []
            if self.event_logger:
                for result in action_results:
                    event_type = (
                        "action_applied" if result.accepted else "action_rejected"
                    )
                    self.event_logger.log(
                        step,
                        event_type,
                        (
                            f"type={result.action.action_type} "
                            f"value={result.action.value!r} "
                            f"reason={result.action.reason!r} "
                            f"detail={result.detail}"
                        ),
                    )
            safety_events = self.safety_collector.observe(
                self._previous_safety_state,
                raw_state,
                tuple(action_results),
            )
            self._previous_safety_state = raw_state
            if self.event_logger:
                for safety_event in safety_events:
                    self.event_logger.log_safety(safety_event)
            sim_time = self.bridge.step()
        except traci.exceptions.FatalTraCIError as exc:
            logger.error("TraCI connection closed: %s; closing gracefully", exc)
            self._terminal_reason = "fatal TraCI error"
            return "disconnected"
        if sim_time is None:
            logger.warning("Simulation stopped at step %d", step)
            self._terminal_reason = "bridge returned no simulation time"
            return "disconnected"
        self._last_simulation_time = float(sim_time)

        if self.step_logger:
            self.step_logger.record(step, raw_state)
        if step % self.snapshot_interval == 0:
            metrics = compute_metrics(step, raw_state)
            self.collector.record(step, raw_state, metrics)
            self.metrics_history.append(
                {
                    "step": step,
                    "avg_queue_length": metrics.avg_queue_length,
                    "max_queue_length": metrics.max_queue_length,
                    "avg_delay": metrics.avg_delay,
                    "total_throughput": metrics.total_throughput,
                }
            )
        if self.bridge.is_exhausted():
            configured_end = getattr(self.bridge, "configured_end_time", None)
            if configured_end is not None:
                if sim_time >= configured_end:
                    return "configured_end"
                return "continue"
            return "exhausted"
        return "continue"

    def _sumo_version(self) -> str:
        version = getattr(self.bridge, "sumo_version", None)
        if version:
            raw = str(version)
        else:
            try:
                response = traci.getVersion()
                raw = response[0] if isinstance(response, tuple) else response
            except Exception:
                raw = getattr(traci, "__version__", None) or "unknown"
        match = re.search(r"\d+(?:\.\d+)+", str(raw))
        return match.group(0) if match else str(raw)

    def __enter__(self) -> "SimulationRunner":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.bridge.close()
