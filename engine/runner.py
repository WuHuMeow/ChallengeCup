"""Single-run simulation lifecycle."""

from __future__ import annotations

import logging
import json
import re
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Callable, List, Optional

from algorithms.base import BaseControlAlgorithm
from core.config import get_config
from core.run_models import RunResult, RunStatus
from core.timebase import SimulationWindow, seconds_for_steps, steps_for_seconds
from core.types import (
    CONTROL_ACTION_VALIDITY_SECONDS,
    ActionResult,
    ControlAction,
    JointState,
    MetricSummary,
    SafetyEvent,
    Scene,
)
from engine.artifacts import RunArtifacts
from engine.collector import MetricsCollector, StepLogger
from engine.edge_channel import EdgeChannel, EdgeMessage
from engine.events import EventLogger
from engine.safety import SafetyObservationCollector
from engine.safety_executor import SafetyExecutor
from engine.traci_bridge import TraCIBridge, traci
from experiments.metrics import compute_metrics
from experiments.summary import write_run_summary
from experiments.evidence import EvidenceWriter

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
        step_length: float | None = None,
        seal_evidence: bool = True,
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
        self.step_length = (
            float(step_length) if step_length is not None else None
        )
        self.seal_evidence = bool(seal_evidence)
        self.evidence_managed = True

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
        self._channel_run_id = (
            artifacts.run_id if artifacts is not None else f"runner-{id(self)}"
        )
        default_min_green = float(
            get_config().get("algorithms.ca_maxpressure.min_green", 10.0)
        )
        self.safety_executor = SafetyExecutor(
            lambda: getattr(self.algorithm, "min_green", default_min_green),
            yellow_seconds=float(
                get_config().get("algorithms.ca_maxpressure.yellow_duration", 3.0)
            ),
            all_red_seconds=float(
                get_config().get("algorithms.ca_maxpressure.all_red_duration", 1.0)
            ),
        )
        if self.state_channel is not None:
            self.state_channel.bind_contract(self._channel_run_id, ("joint-state.v1",))
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

    def _record_action_results(
        self,
        action_results: Sequence[ActionResult],
        state: JointState,
        *,
        step: int = 0,
    ) -> None:
        if not self.event_logger:
            return
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
                reason=result.reason_code,
                action=result.action,
                accepted=result.accepted,
                simulation_seconds=float(state.timestamp),
                entity_ids=(result.action.tls_id,),
            )

    def _apply_pending_startup_actions(
        self,
        state: JointState | None = None,
        *,
        step: int = 0,
    ) -> bool:
        actions = tuple(
            getattr(self.bridge, "take_startup_actions", lambda: ())()
        )
        if not actions:
            return False
        all_results: list[ActionResult] = []
        for action in actions:
            if state is not None and state.tls_id == action.tls_id:
                startup_state = state
            else:
                get_startup_state = getattr(
                    self.bridge,
                    "get_startup_state",
                    None,
                )
                startup_state = (
                    get_startup_state(action.tls_id)
                    if get_startup_state is not None
                    else self.bridge.get_state()
                )
            results = self.safety_executor.apply(
                [action],
                startup_state,
                self.bridge,
            )
            all_results.extend(results)
            self._record_action_results(results, startup_state, step=step)
        rejected = next(
            (result for result in all_results if not result.accepted),
            None,
        )
        if rejected is not None and self.algorithm.name != "fixed_time":
            raise RuntimeError(
                "startup signal program rejected: "
                f"{rejected.reason_code}: {rejected.detail}"
            )
        return True

    def run(
        self,
        window: SimulationWindow | int | None = None,
        stop_event: Optional[Event] = None,
        frame_sink: Callable[[object], None] | None = None,
        *,
        steps: Optional[int] = None,
    ) -> RunResult | List[dict]:
        """Run for an authoritative seconds window and persist one terminal state.

        The integer form and ``steps=`` keyword remain a narrow compatibility
        adapter for smoke scripts. RunService always supplies SimulationWindow.
        """
        if window is not None and steps is not None:
            raise ValueError("provide either window or steps, not both")
        requested = steps if steps is not None else window
        seconds_authoritative = (
            isinstance(requested, SimulationWindow)
            and requested.explicit_steps is None
        )
        legacy_return = not isinstance(requested, SimulationWindow)
        resolved_window, target_steps = self._resolve_window(requested)
        target_seconds = resolved_window.duration_seconds
        self.collector = MetricsCollector(self.output_csv)
        self.metrics_history = []
        self._previous_safety_state = None
        started_at = datetime.now(timezone.utc).isoformat()
        status = RunStatus.RUNNING
        reason = ""
        body_exception = False
        last_step = 0

        if self.artifacts is not None:
            self.artifacts.write_manifest({
                "requested_seconds": target_seconds,
                "warmup_seconds": resolved_window.warmup_seconds,
                "derived_steps": target_steps,
                "step_length": self._effective_step_length(),
                "sumo_pid": None,
            })

        try:
            if stop_event is not None and stop_event.is_set():
                status = RunStatus.INTERRUPTED
                reason = "stop requested"
            else:
                self.algorithm.init(self.scene)
                self.bridge.start()
                if self.artifacts is not None:
                    self.artifacts.write_manifest({
                        "sumo_pid": getattr(self.bridge, "process_id", None),
                    })
            if status is RunStatus.INTERRUPTED:
                pass
            else:
                self.safety_collector.set_conflict_definitions(
                    getattr(self.bridge, "conflict_definitions", ())
                )
                self._sumo_version_value = self._sumo_version()
                if self.event_logger:
                    self.event_logger.log(
                        0,
                        "run_start",
                        f"intersection={self.scene.meta.intersection_id}"
                        f" algorithm={self.algorithm.name}",
                    )
                self._apply_pending_startup_actions()
                for step in range(target_steps):
                    last_step = step
                    if stop_event is not None and stop_event.is_set():
                        status = RunStatus.INTERRUPTED
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
                        if (
                            seconds_authoritative
                            and self._last_simulation_time < target_seconds
                        ) or (
                            not seconds_authoritative and step + 1 < target_steps
                        ):
                            status = RunStatus.ENDED_EARLY
                            reason = "SUMO exhausted before requested seconds"
                        else:
                            status = RunStatus.COMPLETED
                        break
                else:
                    status = RunStatus.COMPLETED
                if status is not RunStatus.DISCONNECTED:
                    self._flush_final_safety_observation()
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
        except BaseException as exc:
            status = RunStatus.FAILED
            reason = str(exc) or type(exc).__name__
            body_exception = True
            raise
        finally:
            cleanup_errors: list[Exception] = []
            metric_summary: MetricSummary | None = None
            evidence_writer = None
            if (
                self.artifacts is not None
                and self.artifacts.provenance.exists()
            ):
                evidence_writer = EvidenceWriter(self.artifacts.run_dir)
            for save in (
                self.collector.save if self.collector else None,
                self.step_logger.save if self.step_logger else None,
            ):
                if save is None:
                    continue
                try:
                    save()
                except BaseException as exc:
                    cleanup_errors.append(exc)
            try:
                self.bridge.close()
            except BaseException as exc:
                cleanup_errors.append(exc)

            if cleanup_errors and not body_exception:
                status = RunStatus.FAILED
                reason = str(cleanup_errors[0]) or type(cleanup_errors[0]).__name__

            if self.event_logger:
                try:
                    self.event_logger.save()
                except BaseException as exc:
                    cleanup_errors.append(exc)
                    if not body_exception:
                        status = RunStatus.FAILED
                        reason = str(exc) or type(exc).__name__

            if self.artifacts is not None:
                publishable = status in (RunStatus.COMPLETED, RunStatus.ENDED_EARLY)
                try:
                    if evidence_writer is not None:
                        algorithm_manifest = dict(self.algorithm.manifest)
                        evidence_writer.update_runtime(
                            parameters=algorithm_manifest,
                            prediction_enabled=bool(
                                algorithm_manifest.get("prediction_enabled", False)
                            ),
                        )
                        if publishable and not cleanup_errors:
                            required_pre_summary = (
                                self.artifacts.metrics,
                                self.artifacts.step_log,
                                self.artifacts.events,
                                self.artifacts.tripinfo,
                                self.artifacts.stats,
                                self.artifacts.trajectory,
                                self.artifacts.collisions,
                            )
                            missing = [
                                path.name
                                for path in required_pre_summary
                                if not path.exists() or path.stat().st_size <= 0
                            ]
                            if missing:
                                raise ValueError(
                                    f"completed evidence missing outputs: {missing}"
                                )
                            metric_summary = MetricSummary.from_raw_outputs(
                                self.artifacts.run_dir,
                                resolved_window.warmup_seconds,
                            )
                            evidence_writer.finalize(status, metric_summary)
                        else:
                            evidence_writer.finalize(status, None)
                    elif publishable and not cleanup_errors:
                        core_outputs = (
                            self.artifacts.tripinfo,
                            self.artifacts.stats,
                            self.artifacts.trajectory,
                            self.artifacts.collisions,
                        )
                        if all(
                            path.exists() and path.stat().st_size > 0
                            for path in core_outputs
                        ):
                            write_run_summary(
                                self.artifacts,
                                warmup_seconds=resolved_window.warmup_seconds,
                            )
                except BaseException as exc:
                    cleanup_errors.append(exc)
                    if not body_exception:
                        status = RunStatus.FAILED
                        reason = str(exc) or type(exc).__name__
                    if evidence_writer is not None:
                        try:
                            evidence_writer.finalize(status, None)
                        except BaseException as finalize_exc:
                            cleanup_errors.append(finalize_exc)

            if self.event_logger:
                try:
                    self.event_logger.log(last_step, "terminal", status.value)
                    self.event_logger.save()
                except BaseException as exc:
                    cleanup_errors.append(exc)
                    if not body_exception:
                        status = RunStatus.FAILED
                        reason = str(exc) or type(exc).__name__
                    if evidence_writer is not None:
                        try:
                            if self.artifacts is not None:
                                self.artifacts.summary.unlink(missing_ok=True)
                            evidence_writer.finalize(status, None)
                            metric_summary = None
                        except BaseException as finalize_exc:
                            cleanup_errors.append(finalize_exc)

            if self.artifacts is not None:
                generated_files = [
                    self.artifacts.metrics,
                    self.artifacts.step_log,
                    self.artifacts.events,
                    self.artifacts.tripinfo,
                    self.artifacts.stats,
                    self.artifacts.trajectory,
                    self.artifacts.collisions,
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
                        requested_steps=target_steps,
                        requested_seconds=target_seconds,
                        warmup_seconds=resolved_window.warmup_seconds,
                        final_simulation_time=self._last_simulation_time,
                        step_length=self._effective_step_length(),
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
                        algorithm_manifest=self.algorithm.manifest,
                        sumo_pid=getattr(self.bridge, "process_id", None),
                    )
                except BaseException as exc:
                    cleanup_errors.append(exc)
                    if not body_exception:
                        status = RunStatus.FAILED
                        reason = str(exc) or type(exc).__name__
                    committed_status = None
                    try:
                        committed_status = RunStatus(
                            self.artifacts.read_status()["status"]
                        )
                    except BaseException:
                        committed_status = None
                    if committed_status not in (
                        RunStatus.COMPLETED,
                        RunStatus.ENDED_EARLY,
                    ):
                        self.artifacts.summary.unlink(missing_ok=True)
                        try:
                            if self.artifacts.metadata.exists():
                                metadata = json.loads(
                                    self.artifacts.metadata.read_text(
                                        encoding="utf-8"
                                    )
                                )
                                if metadata.get("status") in (
                                    RunStatus.COMPLETED.value,
                                    RunStatus.ENDED_EARLY.value,
                                ):
                                    self.artifacts.metadata.unlink(missing_ok=True)
                        except (OSError, TypeError, ValueError):
                            self.artifacts.metadata.unlink(missing_ok=True)
                        if evidence_writer is not None:
                            try:
                                evidence_writer.finalize(RunStatus.FAILED, None)
                                metric_summary = None
                            except BaseException as finalize_exc:
                                cleanup_errors.append(finalize_exc)
                if evidence_writer is not None and self.seal_evidence:
                    try:
                        evidence_writer.seal()
                    except BaseException as exc:
                        logger.error(
                            "Evidence seal failed for run %s: %s",
                            self.artifacts.run_id,
                            exc,
                        )
                        try:
                            evidence_writer.record_error(str(exc))
                        except BaseException:
                            logger.exception("Could not record evidence seal error")
                        if not cleanup_errors and not body_exception:
                            reason = f"evidence seal failed: {exc}"
            if cleanup_errors and not body_exception:
                raise cleanup_errors[0]

        if legacy_return:
            return self.metrics_history
        run_dir = self.artifacts.run_dir if self.artifacts is not None else self.output_csv.parent
        run_id = self.artifacts.run_id if self.artifacts is not None else ""
        summary = None
        if self.artifacts is not None and self.artifacts.summary.exists():
            summary = json.loads(self.artifacts.summary.read_text(encoding="utf-8"))
        return RunResult(
            run_id,
            status,
            reason,
            run_dir,
            summary,
            self.algorithm.name,
        )

    def _resolve_window(
        self,
        requested: SimulationWindow | int | None,
    ) -> tuple[SimulationWindow, int]:
        step_length = self._effective_step_length()
        if isinstance(requested, SimulationWindow):
            target_steps = (
                requested.explicit_steps
                if requested.explicit_steps is not None
                else steps_for_seconds(requested.duration_seconds, step_length)
            )
            return requested, target_steps
        if requested is None:
            requested = int(get_config().get("sumo.default_simulation_steps", 36000))
        if isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0:
            raise ValueError("legacy steps must be an integer > 0")
        return SimulationWindow(seconds_for_steps(requested, step_length), 0.0), requested

    def _effective_step_length(self) -> float:
        if self.step_length is not None:
            return self.step_length
        return float(getattr(self.bridge, "step_length", 1.0))

    def _tick(self, step: int) -> str:
        """Advance one step and return continue, exhausted, or disconnected."""
        try:
            raw_state = self.bridge.get_state()
            if self._apply_pending_startup_actions(raw_state, step=step):
                raw_state = self.bridge.get_state()
            control_state = raw_state
            if self.state_channel is not None:
                simulation_time = float(raw_state.timestamp)
                self.state_channel.send(EdgeMessage(
                    run_id=self._channel_run_id,
                    simulation_time=simulation_time,
                    sent_at=simulation_time,
                    expires_at=simulation_time + CONTROL_ACTION_VALIDITY_SECONDS,
                    payload_version="joint-state.v1",
                    payload=raw_state,
                ))
                message = self.state_channel.receive(now=simulation_time)
                control_state = message.payload if message is not None else None
                if self.event_logger:
                    for event in self.state_channel.events:
                        self.event_logger.log(
                            step,
                            event.event_type,
                            event.detail,
                            simulation_seconds=event.simulation_time,
                        )
                    self.state_channel.events.clear()
            if control_state is None:
                actions: List[ControlAction] = []
                if self.event_logger:
                    self.event_logger.log(
                        step, "channel_wait", "delayed state unavailable"
                    )
            else:
                actions = self.algorithm.step(control_state)
            action_results = self.safety_executor.apply(
                actions,
                raw_state,
                self.bridge,
            )
            if (
                control_state is not None
                and self.event_logger
                and hasattr(self.algorithm, "audit_record")
            ):
                self.event_logger.log(
                    step,
                    "algorithm_audit",
                    json.dumps(
                        self.algorithm.audit_record(control_state, action_results),
                        sort_keys=True,
                    ),
                )
            self._record_action_results(action_results, raw_state, step=step)
            safety_events = self.safety_collector.observe(
                self._previous_safety_state, raw_state, tuple(action_results)
            )
            self._previous_safety_state = raw_state
            self._log_safety_events(safety_events)
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

    def _flush_final_safety_observation(self) -> None:
        final_state = self.bridge.get_state()
        safety_events = self.safety_collector.observe(
            self._previous_safety_state,
            final_state,
            (),
        )
        self._previous_safety_state = final_state
        self._log_safety_events(safety_events)

    def _log_safety_events(
        self,
        safety_events: tuple[SafetyEvent, ...],
    ) -> None:
        if self.event_logger:
            for safety_event in safety_events:
                self.event_logger.log_safety(safety_event)

    def _sumo_version(self) -> str:
        version = getattr(self.bridge, "sumo_version", None)
        if version:
            raw = str(version)
        else:
            try:
                response = traci.getVersion()
                raw = (
                    response[1]
                    if isinstance(response, tuple) and len(response) > 1
                    else response[0]
                    if isinstance(response, tuple)
                    else response
                )
            except Exception:
                raw = getattr(traci, "__version__", None) or "unknown"
        match = re.search(r"\d+(?:\.\d+)+", str(raw))
        return match.group(0) if match else str(raw)

    def __enter__(self) -> "SimulationRunner":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.bridge.close()
