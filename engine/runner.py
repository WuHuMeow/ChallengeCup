"""Single-run simulation lifecycle."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from algorithms.base import BaseControlAlgorithm
from core.config import get_config
from core.types import ControlAction, Scene
from engine.artifacts import RunArtifacts
from engine.collector import MetricsCollector, StepLogger
from engine.edge_channel import EdgeChannel
from engine.events import EventLogger
from engine.traci_bridge import TraCIBridge, traci
from experiments.metrics import compute_metrics

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

        if bridge is not None:
            self.bridge = bridge
        else:
            cfg = scene.meta.sumo_cfg
            enhanced = (
                Path(__file__).resolve().parent
                / "configs"
                / f"demo_{scene.meta.intersection_id}.sumocfg"
            )
            if enhanced.exists():
                cfg = enhanced
            self.bridge = TraCIBridge(
                cfg,
                binary=self.sumo_binary,
                additional_files=self.additional_files,
                artifacts=artifacts,
                seed=self.seed,
            )
        self.collector: Optional[MetricsCollector] = None
        self.metrics_history: List[dict] = []
        self.step_logger = StepLogger(step_log_csv) if step_log_csv else None
        self.event_logger = EventLogger(events_csv) if events_csv else None
        self._terminal_reason = ""
        self._sumo_version_value = "unknown"

    def run(self, steps: Optional[int] = None) -> List[dict]:
        """Run the simulation and return snapshot metrics."""
        steps = steps or get_config().get("sumo.default_simulation_steps", 36000)
        self.collector = MetricsCollector(self.output_csv)
        self.metrics_history = []
        started_at = datetime.now(timezone.utc).isoformat()
        status = "completed"
        reason = ""
        body_exception = False

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
                if not self._tick(step):
                    status = "disconnected"
                    reason = self._terminal_reason
                    break
        except KeyboardInterrupt:
            status = "interrupted"
            reason = "KeyboardInterrupt"
            body_exception = True
            raise
        except Exception as exc:
            status = "failed"
            reason = str(exc) or type(exc).__name__
            body_exception = True
            raise
        finally:
            cleanup_errors: list[Exception] = []
            try:
                if self.collector:
                    self.collector.save()
            except Exception as exc:
                cleanup_errors.append(exc)
            try:
                if self.step_logger:
                    self.step_logger.save()
            except Exception as exc:
                cleanup_errors.append(exc)
            try:
                if self.event_logger:
                    self.event_logger.log(
                        len(self.metrics_history),
                        "run_end",
                        f"snapshots={len(self.metrics_history)}",
                    )
                    self.event_logger.save()
            except Exception as exc:
                cleanup_errors.append(exc)
            try:
                self.bridge.close()
            except Exception as exc:
                cleanup_errors.append(exc)

            if cleanup_errors and not body_exception:
                status = "failed"
                reason = str(cleanup_errors[0]) or type(cleanup_errors[0]).__name__
            if self.artifacts is not None:
                generated_files = [
                    self.artifacts.metrics,
                    self.artifacts.step_log,
                    self.artifacts.events,
                    self.artifacts.tripinfo,
                    self.artifacts.stats,
                    self.artifacts.trajectory,
                    self.artifacts.queues,
                ]
                try:
                    self.artifacts.write_metadata(
                        status,
                        reason,
                        generated_files,
                        started_at=started_at,
                        ended_at=datetime.now(timezone.utc).isoformat(),
                        sumo_version=self._sumo_version_value,
                    )
                except Exception as exc:
                    cleanup_errors.append(exc)
                    if not body_exception:
                        status = "failed"
                        reason = str(exc) or type(exc).__name__
            if cleanup_errors and not body_exception:
                raise cleanup_errors[0]

        return self.metrics_history

    def _tick(self, step: int) -> bool:
        """Advance one simulation step; return False after disconnection."""
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
            for detail in self.bridge.apply_actions(actions) or []:
                if self.event_logger:
                    self.event_logger.log(step, "invalid_action", detail)
            if self.event_logger:
                for action in actions:
                    self.event_logger.log(
                        step, action.action_type, action.reason or str(action.value)
                    )
            sim_time = self.bridge.step()
        except traci.exceptions.FatalTraCIError as exc:
            logger.error("TraCI connection closed: %s; closing gracefully", exc)
            self._terminal_reason = "fatal TraCI error"
            return False
        if sim_time is None:
            logger.warning("Simulation stopped at step %d", step)
            self._terminal_reason = "bridge returned no simulation time"
            return False

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
        return True

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
