"""Thread-safe orchestration for isolated simulation runs."""

from __future__ import annotations

import json
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from algorithms.registry import AlgorithmRegistry, get_algorithm_registry
from core.run_models import RunRequest, RunResult, RunStatus
from core.timebase import SimulationWindow, seconds_for_steps, steps_for_seconds
from engine.artifacts import RunArtifacts
from engine.edge_channel import EdgeChannel
from engine.run_state import RunStateMachine, TERMINAL_STATUSES
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator


class RunService:
    """Serialize TraCI ownership while exposing run-scoped lifecycle control."""

    def __init__(
        self,
        output_root: Path = Path("output/runs"),
        runner_factory: Callable[..., object] = SimulationRunner,
        registry: SceneRegistry | None = None,
        algorithm_registry: AlgorithmRegistry | None = None,
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
        self._lock = threading.RLock()

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
        try:
            self._states.transition(run_id, RunStatus.STOPPING, "stop requested")
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

        if future is not None and future.cancel():
            self._write_terminal_metadata(
                artifacts,
                RunStatus.INTERRUPTED,
                "stop requested before start",
            )
            self._states.transition(
                run_id,
                RunStatus.INTERRUPTED,
                "stop requested before start",
            )
            done_event.set()
            return True

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
            payload = json.loads(artifacts.status.read_text(encoding="utf-8"))
            return RunStatus(payload["status"])
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
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
            "step_length_override": request.step_length_override,
            "edge_delay_steps": request.edge_delay_steps,
            "edge_directions": list(request.edge_directions),
            "variant": asdict(request.variant),
            "algorithm_params": dict(request.algorithm_params),
        })
        self._states.register(queued, artifacts)
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
            except ValueError:
                raced = self._states.get(run_id)
                if raced is not None and raced.status is RunStatus.STOPPING:
                    return self._finish_interrupted_before_start(artifacts)
                raise

            scene = self.registry.get_scene(request.intersection_id)
            step_length = self._step_length(request, scene.meta.sumo_cfg)
            window = self._window(request, step_length)
            derived_steps = steps_for_seconds(window.duration_seconds, step_length)
            artifacts.write_manifest({
                "requested_seconds": window.duration_seconds,
                "warmup_seconds": window.warmup_seconds,
                "derived_steps": derived_steps,
                "step_length": step_length,
                "scene_sumo_cfg": str(scene.meta.sumo_cfg),
            })
            bundle = VariantGenerator().generate_bundle(
                scene.meta,
                request.flow_multiplier,
                request.variant,
                artifacts.run_dir / "variants",
                step_length_override=request.step_length_override,
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
            )
            with self._lock:
                self._runners[run_id] = runner

            current = self._states.get(run_id)
            if current is not None and current.status is RunStatus.STOPPING:
                return self._finish_interrupted_before_start(artifacts)
            try:
                self._states.transition(run_id, RunStatus.RUNNING, "")
            except ValueError:
                raced = self._states.get(run_id)
                if raced is not None and raced.status is RunStatus.STOPPING:
                    return self._finish_interrupted_before_start(artifacts)
                raise
            returned = runner.run(window, stop_event=stop_event)
            result = (
                returned
                if isinstance(returned, RunResult)
                else self._result_from_artifacts(artifacts)
            )
            result = self._canonical_result(result)
            current = self._states.get(run_id)
            if current is not None and current.status not in TERMINAL_STATUSES:
                result = self._states.transition(
                    run_id,
                    result.status,
                    result.reason,
                    summary=result.summary,
                )
            return result
        except Exception as exc:
            reason = str(exc) or type(exc).__name__
            current = self._states.get(run_id)
            if current is not None and current.status in TERMINAL_STATUSES:
                return current
            self._write_terminal_metadata(
                artifacts,
                RunStatus.FAILED,
                reason,
                requested_steps=(
                    derived_steps if "derived_steps" in locals() else None
                ),
                window=window if "window" in locals() else None,
                step_length=step_length if "step_length" in locals() else None,
            )
            return self._states.transition(run_id, RunStatus.FAILED, reason)
        finally:
            with self._lock:
                self._runners.pop(run_id, None)
            done_event.set()

    def _finish_interrupted_before_start(self, artifacts: RunArtifacts) -> RunResult:
        reason = "stop requested before SUMO start"
        self._write_terminal_metadata(artifacts, RunStatus.INTERRUPTED, reason)
        return self._states.transition(
            artifacts.run_id,
            RunStatus.INTERRUPTED,
            reason,
        )

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
    def _window(request: RunRequest, step_length: float) -> SimulationWindow:
        if request.steps is not None:
            return SimulationWindow(
                seconds_for_steps(request.steps, step_length),
                0.0,
            )
        return SimulationWindow(request.duration_seconds, request.warmup_seconds)

    @staticmethod
    def _step_length(request: RunRequest, sumo_cfg: Path) -> float:
        if request.step_length_override is not None:
            return float(request.step_length_override)
        try:
            root = ET.parse(sumo_cfg).getroot()
            element = root.find("./time/step-length")
            return float(element.get("value")) if element is not None else 1.0
        except (OSError, ET.ParseError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid SUMO step-length in {sumo_cfg}") from exc

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
