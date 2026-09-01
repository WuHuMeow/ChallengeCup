"""Serialized orchestration for single, batch, and API simulation runs."""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from core.run_models import RunRequest, RunResult, RunStatus
from core.timebase import SimulationWindow
from engine.artifacts import RunArtifacts
from engine.edge_channel import EdgeChannel
from engine.runner import SimulationRunner
from engine.run_state import RunStateMachine
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator


ALGORITHM_FACTORIES = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,
    "ca_maxpressure": CAMaxPressureAlgorithm,
}

_log = logging.getLogger(__name__)


class EvidenceWriter:
    """Persist the immutable evidence record for one finished run."""

    def __init__(self, artifacts: RunArtifacts) -> None:
        self.artifacts = artifacts

    def finalize(self, result: RunResult) -> dict[str, object]:
        """Write the evidence manifest listing required core outputs."""
        payload: dict[str, object] = {
            "run_id": self.artifacts.run_id,
            "algorithm": self.artifacts.algorithm,
            "status": result.status.value,
            "required_outputs": list(RunArtifacts.required_output_names()),
            "present_outputs": [
                path.name
                for path in (
                    self.artifacts.metrics,
                    self.artifacts.step_log,
                    self.artifacts.events,
                    self.artifacts.summary,
                )
                if path.exists()
            ],
            "finalized_at": datetime.now(timezone.utc).isoformat(),
        }
        target = self.artifacts.run_dir / "evidence_manifest.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return payload

    def seal(self, result: RunResult) -> dict[str, str]:
        """Record SHA-256 digests of the present evidence files."""
        digests: dict[str, str] = {}
        for path in (
            self.artifacts.metrics,
            self.artifacts.step_log,
            self.artifacts.events,
            self.artifacts.summary,
            self.artifacts.metadata,
        ):
            if not path.is_file():
                continue
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    digest.update(chunk)
            digests[path.name] = digest.hexdigest()
        target = self.artifacts.run_dir / "evidence_seal.json"
        target.write_text(
            json.dumps(digests, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return digests


class RunService:
    """Run simulations through one worker to protect the global TraCI client."""

    def __init__(
        self,
        output_root: Path = Path("output/runs"),
        runner_factory: Callable[..., object] = SimulationRunner,
        registry: SceneRegistry | None = None,
    ) -> None:
        self.output_root = Path(output_root)
        self.runner_factory = runner_factory
        self.registry = registry or SceneRegistry()
        self.max_workers = 1
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self._states = RunStateMachine()
        self._stops: dict[str, threading.Event] = {}
        self._done: dict[str, threading.Event] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._artifacts: dict[str, RunArtifacts] = {}
        self._lock = threading.Lock()

    def submit(self, request: RunRequest) -> RunResult:
        """Queue a validated request and return its isolated run identity."""
        self._validate(request)
        artifacts = self._create_artifacts(request)
        run_id = artifacts.run_id
        stop_event = threading.Event()
        queued = RunResult(
            run_id,
            RunStatus.QUEUED,
            "",
            artifacts.run_dir,
            algorithm=artifacts.algorithm,
        )
        with self._lock:
            self._stops[run_id] = stop_event
            self._done[run_id] = threading.Event()
            self._locks[run_id] = threading.Lock()
            self._artifacts[run_id] = artifacts
        self._states.register(queued, artifacts)
        self._executor.submit(self._execute, request, artifacts, stop_event)
        return queued

    def run_sync(self, request: RunRequest) -> RunResult:
        """Execute one request synchronously through the same internal path."""
        self._validate(request)
        artifacts = self._create_artifacts(request)
        run_id = artifacts.run_id
        stop_event = threading.Event()
        with self._lock:
            self._stops[run_id] = stop_event
            self._done[run_id] = threading.Event()
            self._locks[run_id] = threading.Lock()
            self._artifacts[run_id] = artifacts
        self._states.register(
            RunResult(
                run_id,
                RunStatus.QUEUED,
                "",
                artifacts.run_dir,
                algorithm=artifacts.algorithm,
            ),
            artifacts,
        )
        try:
            return self._execute(request, artifacts, stop_event)
        finally:
            self._mark_done(run_id)

    def get(self, run_id: str) -> RunResult | None:
        return self._states.get(run_id)

    def list(self) -> tuple[RunResult, ...]:
        return self._states.list()

    def stop(self, run_id: str) -> bool:
        """Request a stop; returns True when this call initiated the stop."""
        with self._lock:
            run_lock = self._locks.get(run_id)
            stop_event = self._stops.get(run_id)
        if run_lock is None or stop_event is None:
            return False
        initiated = False
        with run_lock:
            result = self._states.get(run_id)
            if result is None:
                return False
            if result.status is RunStatus.QUEUED:
                stop_event.set()
                self._states.transition(run_id, RunStatus.STOPPING, "stop requested")
                initiated = True
                self._finalize_cancelled_queued(run_id, "stop requested")
            elif result.status in (RunStatus.STARTING, RunStatus.RUNNING):
                self._states.transition(run_id, RunStatus.STOPPING, "stop requested")
                stop_event.set()
                initiated = True
        self._wait_until_done(run_id)
        if not initiated:
            return False
        # The stop only "took" if the run actually terminalized as
        # interrupted; a runner that finishes COMPLETED anyway reports False.
        final = self.get(run_id)
        return final is not None and final.status in (
            RunStatus.INTERRUPTED,
            RunStatus.STOPPED,
        )

    def switch_scene(
        self,
        run_id: str,
        replacement: RunRequest,
    ) -> tuple[RunResult, RunResult]:
        """Stop the active run, wait for it to finish, then queue the new one."""
        self.stop(run_id)
        old = self.get(run_id)
        new = self.submit(replacement)
        return old, new

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

    def _wait_until_done(self, run_id: str) -> None:
        with self._lock:
            done = self._done.get(run_id)
        if done is not None:
            done.wait()

    def _mark_done(self, run_id: str) -> None:
        with self._lock:
            done = self._done.get(run_id)
        if done is not None:
            done.set()

    def _create_artifacts(self, request: RunRequest) -> RunArtifacts:
        return RunArtifacts.create(
            request.output_root or self.output_root,
            request.intersection_id,
            request.algorithm,
            request.flow_multiplier,
            request.seed,
        )

    def _execute(
        self,
        request: RunRequest,
        artifacts: RunArtifacts,
        stop_event: threading.Event,
    ) -> RunResult:
        run_id = artifacts.run_id
        try:
            self._states.transition(run_id, RunStatus.STARTING, "")
        except ValueError:
            # Terminalized by stop() before the worker picked it up.
            return self.get(run_id)
        try:
            self._states.transition(run_id, RunStatus.RUNNING, "")
            scene = self.registry.get_scene(request.intersection_id)
            window = SimulationWindow(
                request.duration_seconds,
                request.warmup_seconds,
                explicit_steps=request.steps,
            )
            bundle = VariantGenerator().generate_bundle(
                scene.meta,
                request.flow_multiplier,
                request.variant,
                artifacts.run_dir / "variants",
            )
            state_channel = None
            if request.edge_delay_steps or request.edge_directions:
                state_channel = EdgeChannel(
                    delay_steps=request.edge_delay_steps,
                    allowed_directions=list(request.edge_directions) or None,
                )
            runner = self.runner_factory(
                scene=scene,
                algorithm=ALGORITHM_FACTORIES[request.algorithm](
                    **request.algorithm_params
                ),
                additional_files=list(bundle.additional_files),
                seed=request.seed,
                artifacts=artifacts,
                state_channel=state_channel,
            )
            outcome = runner.run(window, stop_event=stop_event)
            if isinstance(outcome, RunResult):
                result = outcome
            else:
                # Legacy runners return their metrics history; the terminal
                # state lives in the run metadata they just wrote.
                result = self._result_from_artifacts(artifacts)
            try:
                self._states.transition(
                    run_id,
                    result.status,
                    result.reason,
                    summary=result.summary,
                )
            except OSError:
                self._states.force_terminal(
                    run_id, result.status, result.reason, summary=result.summary
                )
            return self.get(run_id)
        except BaseException as exc:
            status = (
                RunStatus.INTERRUPTED
                if isinstance(exc, KeyboardInterrupt)
                else RunStatus.FAILED
            )
            reason = str(exc) or type(exc).__name__
            try:
                self._states.transition(run_id, status, reason)
            except (ValueError, OSError):
                self._states.force_terminal(run_id, status, reason)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            return self.get(run_id)
        finally:
            self._mark_done(run_id)

    def _finalize_cancelled_queued(self, run_id: str, reason: str) -> None:
        """Terminalize a never-started run; evidence failures never stick."""
        artifacts = self._artifacts.get(run_id)
        if artifacts is not None:
            try:
                self._write_terminal_metadata(artifacts, RunStatus.INTERRUPTED, reason)
            except Exception as exc:  # noqa: BLE001 - 终态化优先于证据完整性
                _log.warning("terminal metadata write failed for %s: %s", run_id, exc)
            writer = EvidenceWriter(artifacts)
            result = self._states.get(run_id)
            for step in (writer.finalize, writer.seal):
                try:
                    step(result)
                except Exception as exc:  # noqa: BLE001
                    _log.warning("evidence write failed for %s: %s", run_id, exc)
        try:
            self._states.transition(run_id, RunStatus.INTERRUPTED, reason)
        except OSError:
            self._states.force_terminal(run_id, RunStatus.INTERRUPTED, reason)
        except ValueError:
            pass
        self._mark_done(run_id)

    def _write_terminal_metadata(
        self,
        artifacts: RunArtifacts,
        status: RunStatus,
        reason: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if artifacts.metadata.exists():
            return
        artifacts.write_metadata(
            status.value,
            reason,
            [],
            started_at=now,
            ended_at=now,
            sumo_version="unknown",
        )

    def _result_from_artifacts(self, artifacts: RunArtifacts) -> RunResult:
        """Read the terminal state a legacy runner wrote into run metadata."""
        payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
        summary = None
        if artifacts.summary.exists():
            summary = json.loads(artifacts.summary.read_text(encoding="utf-8"))
        return RunResult(
            artifacts.run_id,
            RunStatus(payload["status"]),
            payload.get("reason", ""),
            artifacts.run_dir,
            summary,
            algorithm=artifacts.algorithm,
        )

    def _store(self, result: RunResult) -> None:
        self._states.register(result)

    @staticmethod
    def _validate(request: RunRequest) -> None:
        try:
            intersection = int(request.intersection_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("intersection_id must be an integer in 1..20") from exc
        if not 1 <= intersection <= 20:
            raise ValueError("intersection_id must be in 1..20")
        if request.algorithm not in ALGORITHM_FACTORIES:
            raise ValueError(f"unknown algorithm: {request.algorithm}")
        if request.steps is not None and request.steps <= 0:
            raise ValueError("steps must be > 0")
        if request.duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        if request.warmup_seconds < 0:
            raise ValueError("warmup_seconds must be >= 0")
        if request.warmup_seconds >= request.duration_seconds:
            raise ValueError("warmup_seconds must be less than duration_seconds")
        if request.flow_multiplier <= 0:
            raise ValueError("flow_multiplier must be > 0")
        if request.seed < 0:
            raise ValueError("seed must be >= 0")
        if request.edge_delay_steps < 0:
            raise ValueError("edge_delay_steps must be >= 0")
        if request.algorithm_params and request.algorithm != "ca_maxpressure":
            raise ValueError("algorithm_params are supported only for ca_maxpressure")
        allowed_params = {
            "overflow_occupancy_threshold",
            "prediction_weight",
            "base_green",
        }
        unknown_params = set(request.algorithm_params) - allowed_params
        if unknown_params:
            raise ValueError(
                f"unknown CA-MP parameters: {sorted(unknown_params)}"
            )
