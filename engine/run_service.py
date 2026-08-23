"""Thread-safe orchestration for isolated simulation runs."""

from __future__ import annotations

import hashlib
import inspect
import json
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from algorithms.registry import AlgorithmRegistry, get_algorithm_registry
from api.realtime import RealtimeHub
from core.run_models import RunRequest, RunResult, RunStatus
from core.timebase import SimulationWindow, seconds_for_steps, steps_for_seconds
from engine.artifacts import CorruptStatusArtifactError, RunArtifacts
from engine.edge_channel import EdgeChannel
from engine.run_state import RunStateMachine, TERMINAL_STATUSES
from engine.runner import SimulationRunner
from experiments.evidence import (
    EvidenceReader,
    EvidenceWriter,
    RunManifest,
    canonical_mapping_sha256,
    resolve_code_commit,
    runtime_python_version,
)
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator
from visualization.frame_publisher import FramePublisher, FrameRecord


class RunService:
    """Serialize TraCI ownership while exposing run-scoped lifecycle control."""

    def __init__(
        self,
        output_root: Path = Path("output/runs"),
        runner_factory: Callable[..., object] = SimulationRunner,
        registry: SceneRegistry | None = None,
        algorithm_registry: AlgorithmRegistry | None = None,
        frame_publisher: FramePublisher | None = None,
        realtime_hub: RealtimeHub | None = None,
    ) -> None:
        self.output_root = Path(output_root)
        self.runner_factory = runner_factory
        self.registry = registry or SceneRegistry()
        self.algorithm_registry = algorithm_registry or get_algorithm_registry()
        self.max_workers = 1
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._states = RunStateMachine()
        self._stops: dict[str, threading.Event] = {}
        self._done: dict[str, threading.Event] = {}
        self._futures: dict[str, Future[RunResult]] = {}
        self._runners: dict[str, object] = {}
        self._artifacts: dict[str, RunArtifacts] = {}
        self._terminal_events: set[str] = set()
        self._lock = threading.RLock()
        self.frame_publisher = frame_publisher or FramePublisher()
        self.realtime_hub = realtime_hub or RealtimeHub()

    def submit(self, request: RunRequest) -> RunResult:
        """Queue a validated request and return its isolated run identity."""
        request, artifacts, stop_event, queued = self._prepare(request)
        future = self._executor.submit(self._execute, request, artifacts, stop_event)
        with self._lock:
            self._futures[queued.run_id] = future
        return queued

    def run_sync(self, request: RunRequest) -> RunResult:
        """Execute one request synchronously through the same lifecycle path."""
        request, artifacts, stop_event, _ = self._prepare(request)
        return self._execute(request, artifacts, stop_event)

    def get(self, run_id: str) -> RunResult | None:
        return self._states.get(run_id)

    def stop(self, run_id: str) -> bool:
        """Request one run to stop and wait for that run's owned work to finish."""
        current = self._states.get(run_id)
        if current is None:
            return False
        if current.status in TERMINAL_STATUSES:
            self._wait_until_done(run_id)
            return False
        if current.status is RunStatus.STOPPING:
            self._wait_until_done(run_id)
            return False

        with self._lock:
            stop_event = self._stops.get(run_id)
            done_event = self._done.get(run_id)
            future = self._futures.get(run_id)
            artifacts = self._artifacts.get(run_id)
        if stop_event is None or done_event is None or artifacts is None:
            return False

        stop_event.set()
        terminal_event_seen = False
        try:
            with self._lock:
                terminal_event_seen = run_id in self._terminal_events
                if not terminal_event_seen:
                    self._states.transition(run_id, RunStatus.STOPPING, "stop requested")
                    self._publish_status(run_id, RunStatus.STOPPING, "stop requested")
        except ValueError:
            raced = self._states.get(run_id)
            if raced is not None and (
                raced.status is RunStatus.STOPPING
                or raced.status in TERMINAL_STATUSES
            ):
                self._wait_until_done(run_id)
                return False
            if self._artifact_status(artifacts) in TERMINAL_STATUSES:
                self._wait_until_done(run_id)
                return False
            raise
        if terminal_event_seen:
            self._wait_until_done(run_id)
            return False

        if future is not None and future.cancel():
            try:
                status, reason = self._terminalize_partial_evidence(
                    artifacts,
                    RunStatus.INTERRUPTED,
                    "stop requested before start",
                )
                self._states.transition(
                    run_id,
                    status,
                    reason,
                    persist_artifact=False,
                )
                self._publish_status(run_id, status, reason)
                return True
            finally:
                done_event.set()

        if future is not None:
            future.result()
        else:
            done_event.wait()
        return True

    def _wait_until_done(self, run_id: str) -> None:
        with self._lock:
            done_event = self._done.get(run_id)
        if done_event is not None:
            done_event.wait()

    @staticmethod
    def _artifact_status(artifacts: RunArtifacts) -> RunStatus | None:
        try:
            payload = artifacts.read_status()
            return RunStatus(payload["status"])
        except BaseException:
            return None

    def switch_scene(
        self,
        run_id: str,
        request: RunRequest,
    ) -> tuple[RunResult, RunResult]:
        """Finish the old run before allocating and queuing the replacement."""
        if self.get(run_id) is None:
            raise KeyError(run_id)
        self.stop(run_id)
        old = self.get(run_id)
        if old is not None and old.status is RunStatus.STOPPING:
            with self._lock:
                done_event = self._done[run_id]
            done_event.wait()
            old = self.get(run_id)
        assert old is not None
        new = self.submit(request)
        return old, new

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)
        self.realtime_hub.close()
        self.frame_publisher.clear_all()

    def _publish_status(
        self,
        run_id: str,
        status: RunStatus,
        reason: str = "",
        simulation_time: float | None = None,
    ) -> None:
        self.realtime_hub.publish_status(
            run_id,
            status.value,
            reason,
            simulation_time,
        )

    def _publish_frame(self, run_id: str, record: object) -> bool:
        if not isinstance(record, FrameRecord) or record.run_id != run_id:
            return False
        return self.frame_publisher.publish(record)

    def _publish_runtime_event(
        self,
        run_id: str,
        message: dict[str, object],
    ) -> None:
        if message.get("type") != "terminal":
            self.realtime_hub.publish(run_id, message)
            return
        with self._lock:
            self.realtime_hub.publish(run_id, message)
            self._terminal_events.add(run_id)

    @staticmethod
    def _runner_accepts_argument(runner: object, name: str) -> bool:
        try:
            return name in inspect.signature(runner.run).parameters
        except (TypeError, ValueError):
            return False

    def _create_artifacts(self, request: RunRequest) -> RunArtifacts:
        root = request.output_root or self.output_root
        for _ in range(5):
            try:
                return RunArtifacts.create(
                    root,
                    request.intersection_id,
                    request.algorithm,
                    request.flow_multiplier,
                    request.seed,
                )
            except FileExistsError:
                continue
        raise FileExistsError("could not allocate a collision-free run directory")

    def _prepare(
        self,
        request: RunRequest,
    ) -> tuple[RunRequest, RunArtifacts, threading.Event, RunResult]:
        self._validate(request)
        artifacts = self._create_artifacts(request)
        stop_event = threading.Event()
        done_event = threading.Event()
        queued = RunResult(
            artifacts.run_id,
            RunStatus.QUEUED,
            "",
            artifacts.run_dir,
            algorithm=request.algorithm,
        )
        artifacts.write_manifest({
            "requested_seconds": request.duration_seconds,
            "warmup_seconds": request.warmup_seconds,
            "requested_steps": request.steps,
            "steps_origin": request.steps_origin,
            "step_length_override": request.step_length_override,
            "edge_delay_steps": request.edge_delay_steps,
            "edge_directions": list(request.edge_directions),
            "variant": asdict(request.variant),
            "algorithm_params": dict(request.algorithm_params),
        })
        EvidenceWriter(artifacts.run_dir).begin(
            self._run_manifest(
                request,
                artifacts,
                scene_source_sha256={},
                scene_manifest_sha256="unknown",
                derived_steps=(
                    int(request.steps) if request.steps is not None else None
                ),
                step_length=request.step_length_override,
            )
        )
        self._states.register(queued, artifacts)
        self._publish_status(artifacts.run_id, RunStatus.QUEUED)
        with self._lock:
            self._stops[artifacts.run_id] = stop_event
            self._done[artifacts.run_id] = done_event
            self._artifacts[artifacts.run_id] = artifacts
        return request, artifacts, stop_event, queued

    def _execute(
        self,
        request: RunRequest,
        artifacts: RunArtifacts,
        stop_event: threading.Event,
    ) -> RunResult:
        run_id = artifacts.run_id
        with self._lock:
            done_event = self._done[run_id]
        try:
            current = self._states.get(run_id)
            if current is not None and current.status is RunStatus.STOPPING:
                return self._finish_interrupted_before_start(artifacts)
            try:
                self._states.transition(run_id, RunStatus.STARTING, "")
                self._publish_status(run_id, RunStatus.STARTING)
            except ValueError:
                raced = self._states.get(run_id)
                if raced is not None and raced.status is RunStatus.STOPPING:
                    return self._finish_interrupted_before_start(artifacts)
                raise

            manifest = next(
                (
                    candidate
                    for candidate in self.registry.list_scenes(formal_only=True)
                    if candidate.scene_id == request.intersection_id
                    and candidate.validation_status == "pass"
                ),
                None,
            )
            if manifest is None:
                raise ValueError(
                    "validated scene manifest unavailable or failed for "
                    f"scene {request.intersection_id}"
                )
            scene = self.registry.get_scene(request.intersection_id)
            self._verify_scene_identity(manifest, scene)
            step_length = self._step_length(request, manifest.step_length)
            window = self._window(request, step_length)
            derived_steps = (
                window.explicit_steps
                if window.explicit_steps is not None
                else steps_for_seconds(window.duration_seconds, step_length)
            )
            artifacts.write_manifest({
                "requested_seconds": window.duration_seconds,
                "warmup_seconds": window.warmup_seconds,
                "derived_steps": derived_steps,
                "step_length": step_length,
                "scene_sumo_cfg": str(scene.meta.sumo_cfg),
            })
            scene_source_sha256 = {
                str(name): str(digest).lower()
                for name, digest in dict(manifest.sha256).items()
            }
            EvidenceWriter(artifacts.run_dir).begin(
                self._run_manifest(
                    request,
                    artifacts,
                    scene_source_sha256=scene_source_sha256,
                    scene_manifest_sha256=canonical_mapping_sha256(
                        scene_source_sha256
                    ),
                    derived_steps=derived_steps,
                    step_length=step_length,
                    requested_seconds=window.duration_seconds,
                    warmup_seconds=window.warmup_seconds,
                )
            )
            bundle = VariantGenerator().generate_bundle(
                scene.meta,
                request.flow_multiplier,
                request.variant,
                artifacts.run_dir / "variants",
                step_length_override=step_length,
            )
            state_channel = None
            if request.edge_delay_steps or request.edge_directions:
                state_channel = EdgeChannel(
                    delay_seconds=seconds_for_steps(
                        request.edge_delay_steps, step_length
                    ),
                    allowed_directions=list(request.edge_directions) or None,
                    expected_run_id=artifacts.run_id,
                    accepted_payload_versions=("joint-state.v1",),
                )
            runner = self.runner_factory(
                scene=scene,
                algorithm=self.algorithm_registry.get(request.algorithm).factory(
                    **request.algorithm_params
                ),
                additional_files=list(bundle.additional_files),
                sumo_cfg=bundle.sumo_cfg,
                seed=request.seed,
                artifacts=artifacts,
                state_channel=state_channel,
                step_length=step_length,
            )
            if isinstance(runner, SimulationRunner):
                runner.seal_evidence = False
                runner.event_sink = lambda message: self._publish_runtime_event(
                    run_id, message
                )
            with self._lock:
                self._runners[run_id] = runner

            current = self._states.get(run_id)
            if current is not None and current.status is RunStatus.STOPPING:
                return self._finish_interrupted_before_start(artifacts)
            try:
                self._states.transition(run_id, RunStatus.RUNNING, "")
                self._publish_status(run_id, RunStatus.RUNNING)
            except ValueError:
                raced = self._states.get(run_id)
                if raced is not None and raced.status is RunStatus.STOPPING:
                    return self._finish_interrupted_before_start(artifacts)
                raise
            run_kwargs: dict[str, object] = {"stop_event": stop_event}
            if self._runner_accepts_argument(runner, "frame_sink"):
                run_kwargs["frame_sink"] = (
                    lambda record: self._publish_frame(run_id, record)
                )
            if self._runner_accepts_argument(runner, "frame_ready"):
                run_kwargs["frame_ready"] = (
                    lambda: self.frame_publisher.can_capture(run_id)
                )
            returned = runner.run(window, **run_kwargs)
            result = (
                returned
                if isinstance(returned, RunResult)
                else self._result_from_artifacts(artifacts)
            )
            result = self._canonical_result(result)
            # RunStatus describes lifecycle completion. Only an explicitly
            # evidence-managed runner may publish hashes; strict consumers use
            # EvidenceReader/is_complete, so legacy injected runners remain
            # lifecycle-compatible without becoming publishable evidence.
            if getattr(runner, "evidence_managed", False):
                try:
                    EvidenceWriter(artifacts.run_dir).seal()
                except Exception as seal_exc:
                    try:
                        EvidenceWriter(artifacts.run_dir).record_error(str(seal_exc))
                    except Exception:
                        pass
                    result = RunResult(
                        result.run_id,
                        result.status,
                        f"evidence seal failed: {seal_exc}",
                        result.run_dir,
                        None,
                        result.algorithm,
                    )
                else:
                    result = RunResult(
                        result.run_id,
                        result.status,
                        result.reason,
                        result.run_dir,
                        EvidenceReader.load_summary(artifacts.run_dir),
                        result.algorithm,
                    )
            with self._lock:
                current = self._states.get(run_id)
                if current is not None and current.status not in TERMINAL_STATUSES:
                    result = self._states.transition(
                        run_id,
                        result.status,
                        result.reason,
                        summary=result.summary,
                    )
                    self._publish_status(run_id, result.status, result.reason)
            return result
        except Exception as exc:
            reason = str(exc) or type(exc).__name__
            current = self._states.get(run_id)
            if current is not None and current.status in TERMINAL_STATUSES:
                self._publish_status(run_id, current.status, current.reason)
                return current
            artifact_status = self._artifact_status(artifacts)
            if artifact_status in TERMINAL_STATUSES:
                seal_reason = self._seal_existing_terminal(artifacts)
                terminal_reason = self._metadata_reason(artifacts, reason)
                if seal_reason:
                    terminal_reason = f"{terminal_reason}; {seal_reason}"
                result = self._states.transition(
                    run_id,
                    artifact_status,
                    terminal_reason,
                    summary=self._read_summary(artifacts),
                )
                self._publish_status(run_id, result.status, result.reason)
                return result
            status, terminal_reason = self._terminalize_partial_evidence(
                artifacts,
                RunStatus.FAILED,
                reason,
                requested_steps=(
                    derived_steps if "derived_steps" in locals() else None
                ),
                window=window if "window" in locals() else None,
                step_length=step_length if "step_length" in locals() else None,
            )
            result = self._states.transition(
                run_id,
                status,
                terminal_reason,
                persist_artifact=False,
            )
            self._publish_status(run_id, result.status, result.reason)
            return result
        except KeyboardInterrupt as exc:
            reason = str(exc) or type(exc).__name__
            artifact_status = self._artifact_status(artifacts)
            if artifact_status in TERMINAL_STATUSES:
                seal_reason = self._seal_existing_terminal(artifacts)
                terminal_reason = self._metadata_reason(artifacts, "")
                if seal_reason:
                    terminal_reason = (
                        f"{terminal_reason}; {seal_reason}"
                        if terminal_reason
                        else seal_reason
                    )
                current = self._states.get(run_id)
                if current is not None and current.status not in TERMINAL_STATUSES:
                    result = self._states.transition(
                        run_id,
                        artifact_status,
                        terminal_reason,
                        summary=self._read_summary(artifacts),
                    )
                    self._publish_status(run_id, result.status, result.reason)
                elif current is not None:
                    self._publish_status(run_id, current.status, current.reason)
                raise
            else:
                status, terminal_reason = self._terminalize_partial_evidence(
                    artifacts,
                    RunStatus.INTERRUPTED,
                    reason,
                    requested_steps=(
                        derived_steps if "derived_steps" in locals() else None
                    ),
                    window=window if "window" in locals() else None,
                    step_length=step_length if "step_length" in locals() else None,
                )
            current = self._states.get(run_id)
            if current is not None and current.status not in TERMINAL_STATUSES:
                result = self._states.transition(
                    run_id,
                    status,
                    terminal_reason,
                    persist_artifact=False,
                )
                self._publish_status(run_id, result.status, result.reason)
            elif current is not None:
                self._publish_status(run_id, current.status, current.reason)
            raise
        except BaseException as exc:
            reason = str(exc) or type(exc).__name__
            current = self._states.get(run_id)
            if current is None or current.status not in TERMINAL_STATUSES:
                status, terminal_reason = self._terminalize_partial_evidence(
                    artifacts,
                    RunStatus.FAILED,
                    reason,
                    requested_steps=(
                        derived_steps if "derived_steps" in locals() else None
                    ),
                    window=window if "window" in locals() else None,
                    step_length=step_length if "step_length" in locals() else None,
                )
                result = self._states.transition(
                    run_id,
                    status,
                    terminal_reason,
                    persist_artifact=False,
                )
                self._publish_status(run_id, result.status, result.reason)
            elif current is not None:
                self._publish_status(run_id, current.status, current.reason)
            raise
        finally:
            with self._lock:
                self._runners.pop(run_id, None)
                self._terminal_events.discard(run_id)
            done_event.set()

    def _finish_interrupted_before_start(self, artifacts: RunArtifacts) -> RunResult:
        status, reason = self._terminalize_partial_evidence(
            artifacts,
            RunStatus.INTERRUPTED,
            "stop requested before SUMO start",
        )
        result = self._states.transition(
            artifacts.run_id,
            status,
            reason,
            persist_artifact=False,
        )
        self._publish_status(result.run_id, result.status, result.reason)
        return result

    def _terminalize_partial_evidence(
        self,
        artifacts: RunArtifacts,
        status: RunStatus,
        reason: str,
        *,
        requested_steps: int | None = None,
        window: SimulationWindow | None = None,
        step_length: float | None = None,
    ) -> tuple[RunStatus, str]:
        """Best-effort terminal commit that never replaces the primary failure."""
        secondary: list[str] = []
        resolved_status = status
        writer = EvidenceWriter(artifacts.run_dir)

        try:
            writer.finalize(resolved_status, None)
        except BaseException as exc:
            secondary.append(f"evidence finalize failed: {exc}")

        try:
            self._write_terminal_metadata(
                artifacts,
                resolved_status,
                reason,
                requested_steps=requested_steps,
                window=window,
                step_length=step_length,
            )
        except CorruptStatusArtifactError as exc:
            secondary.append(f"status artifact corruption: {exc}")
            resolved_status = RunStatus.FAILED
            corruption_reason = f"status artifact corruption: {exc}; {reason}"
            try:
                artifacts.recover_corrupt_status(corruption_reason)
                artifacts.metadata.unlink(missing_ok=True)
                self._write_terminal_metadata(
                    artifacts,
                    resolved_status,
                    corruption_reason,
                    requested_steps=requested_steps,
                    window=window,
                    step_length=step_length,
                )
            except BaseException as recovery_exc:
                secondary.append(
                    f"status corruption recovery failed: {recovery_exc}"
                )
        except BaseException as exc:
            secondary.append(f"terminal metadata failed: {exc}")

        disk_status = self._artifact_status(artifacts)
        if disk_status not in TERMINAL_STATUSES:
            try:
                artifacts.write_status(resolved_status.value, reason)
            except CorruptStatusArtifactError as exc:
                resolved_status = RunStatus.FAILED
                recovery_reason = f"status artifact corruption: {exc}; {reason}"
                try:
                    artifacts.recover_corrupt_status(recovery_reason)
                except BaseException as recovery_exc:
                    secondary.append(
                        f"status recovery failed: {recovery_exc}"
                    )
            except BaseException as exc:
                secondary.append(f"terminal status failed: {exc}")
            disk_status = self._artifact_status(artifacts)

        if disk_status in TERMINAL_STATUSES:
            resolved_status = disk_status

        if secondary:
            try:
                writer.record_error("; ".join(secondary))
            except BaseException as exc:
                secondary.append(f"evidence error recording failed: {exc}")
        elif disk_status in TERMINAL_STATUSES:
            seal_reason = self._seal_existing_terminal(artifacts)
            if seal_reason:
                secondary.append(seal_reason)

        combined_reason = reason
        if secondary:
            combined_reason = f"{reason}; {'; '.join(secondary)}"
        return resolved_status, combined_reason

    @staticmethod
    def _write_terminal_metadata(
        artifacts: RunArtifacts,
        status: RunStatus,
        reason: str,
        *,
        requested_steps: int | None = None,
        window: SimulationWindow | None = None,
        step_length: float | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        artifacts.write_metadata(
            status.value,
            reason,
            [],
            started_at=now,
            ended_at=now,
            sumo_version="unknown",
            requested_steps=requested_steps,
            requested_seconds=window.duration_seconds if window else None,
            warmup_seconds=window.warmup_seconds if window else None,
            step_length=step_length,
        )

    @staticmethod
    def _read_summary(artifacts: RunArtifacts) -> dict[str, object] | None:
        return EvidenceReader.load_summary(artifacts.run_dir)

    @staticmethod
    def _metadata_reason(artifacts: RunArtifacts, fallback: str) -> str:
        try:
            payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
        except BaseException:
            return fallback
        return str(payload.get("reason") or fallback)

    @staticmethod
    def _seal_existing_terminal(artifacts: RunArtifacts) -> str:
        try:
            EvidenceWriter(artifacts.run_dir).seal()
        except BaseException as exc:
            try:
                EvidenceWriter(artifacts.run_dir).record_error(str(exc))
            except BaseException:
                pass
            return f"evidence seal failed: {exc}"
        return ""

    @staticmethod
    def _run_manifest(
        request: RunRequest,
        artifacts: RunArtifacts,
        *,
        scene_source_sha256: dict[str, str],
        scene_manifest_sha256: str,
        derived_steps: int | None,
        step_length: float | None,
        requested_seconds: float | None = None,
        warmup_seconds: float | None = None,
    ) -> RunManifest:
        variant = asdict(request.variant)
        return RunManifest(
            run_id=artifacts.run_id,
            code_commit=resolve_code_commit(),
            scene_manifest_sha256=scene_manifest_sha256,
            algorithm=request.algorithm,
            parameters=dict(request.algorithm_params),
            flow_multiplier=request.flow_multiplier,
            seed=request.seed,
            duration_seconds=(
                float(requested_seconds)
                if requested_seconds is not None
                else request.duration_seconds
            ),
            warmup_seconds=(
                float(warmup_seconds)
                if warmup_seconds is not None
                else request.warmup_seconds
            ),
            derived_steps=derived_steps,
            sumo_version="unknown",
            python_version=runtime_python_version(),
            prediction_enabled=bool(
                request.algorithm_params.get("prediction_weight", 0.0)
            ),
            scene_id=request.intersection_id,
            scene_source_sha256=scene_source_sha256,
            step_length=step_length,
            requested_seconds=(
                float(requested_seconds)
                if requested_seconds is not None
                else request.duration_seconds
            ),
            request_dimensions={
                "variant": variant,
                "disturbance": (
                    asdict(request.disturbance)
                    if request.disturbance is not None
                    else None
                ),
                "edge_delay_steps": request.edge_delay_steps,
                "edge_directions": list(request.edge_directions),
                "steps_origin": request.steps_origin,
                "requested_steps": (
                    int(request.steps) if request.steps is not None else None
                ),
                "duration_seconds": request.duration_seconds,
                "warmup_seconds": request.warmup_seconds,
                "step_length_override": request.step_length_override,
                "algorithm_params": dict(request.algorithm_params),
            },
        )

    @staticmethod
    def _window(request: RunRequest, step_length: float) -> SimulationWindow:
        if request.steps is not None and request._steps_explicit:
            return SimulationWindow(
                seconds_for_steps(request.steps, step_length),
                request.warmup_seconds,
                explicit_steps=request.steps,
            )
        return SimulationWindow(request.duration_seconds, request.warmup_seconds)

    def _verify_scene_identity(self, manifest, scene) -> None:
        """Reject a mutable runtime scene that differs from its validated source."""
        source_files = dict(getattr(manifest, "source_files", {}) or {})
        hashes = dict(getattr(manifest, "sha256", {}) or {})
        if not source_files and not hashes:
            return
        attributes = {
            "net": "sumo_net",
            "route": "sumo_rou",
            "flow": "sumo_flow",
            "turn": "sumo_turn",
            "sumocfg": "sumo_cfg",
            "timing": "timing_xlsx",
            "map": "map_png",
        }
        data_root = getattr(self.registry, "data_root", None)
        roots = [Path.cwd()]
        if data_root is not None:
            try:
                roots.insert(0, Path(data_root).resolve().parents[1])
            except (IndexError, OSError):
                pass
        for key in source_files.keys() | hashes.keys():
            attribute = attributes.get(key)
            runtime = getattr(scene.meta, attribute, None) if attribute else None
            if runtime is None:
                raise ValueError(f"validated scene identity mismatch for {key}")
            runtime_path = Path(runtime).resolve()
            source_file = source_files.get(key)
            if source_file is not None:
                expected = Path(str(source_file))
                expected_paths = (
                    (expected.resolve(),)
                    if expected.is_absolute()
                    else tuple((root / expected).resolve() for root in roots)
                )
                if runtime_path not in expected_paths:
                    raise ValueError(f"validated scene identity mismatch for {key}")
            expected_hash = hashes.get(key)
            if expected_hash:
                digest = hashlib.sha256()
                with runtime_path.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest().lower() != str(expected_hash).lower():
                    raise ValueError(f"validated scene identity mismatch for {key} hash")

    @staticmethod
    def _step_length(request: RunRequest, validated_step_length: float) -> float:
        if request.step_length_override is not None:
            return float(request.step_length_override)
        return validated_step_length

    def _result_from_artifacts(self, artifacts: RunArtifacts) -> RunResult:
        payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
        summary = None
        if artifacts.summary.exists():
            summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
        status = RunStatus(payload["status"])
        if status is RunStatus.STOPPED:
            status = RunStatus.INTERRUPTED
        return RunResult(
            artifacts.run_id,
            status,
            payload.get("reason", ""),
            artifacts.run_dir,
            summary,
            artifacts.algorithm,
        )

    @staticmethod
    def _canonical_result(result: RunResult) -> RunResult:
        if result.status is not RunStatus.STOPPED:
            return result
        return RunResult(
            result.run_id,
            RunStatus.INTERRUPTED,
            result.reason,
            result.run_dir,
            result.summary,
            result.algorithm,
        )

    @staticmethod
    def _validate(request: RunRequest) -> None:
        request.__post_init__()
