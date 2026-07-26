"""Serialized orchestration for single, batch, and API simulation runs."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm
from core.run_models import RunRequest, RunResult, RunStatus
from engine.artifacts import RunArtifacts
from engine.edge_channel import EdgeChannel
from engine.runner import SimulationRunner
from scenes.registry import SceneRegistry
from scenes.variant import VariantGenerator


ALGORITHM_FACTORIES = {
    "fixed_time": FixedTimeAlgorithm,
    "actuated": RuleAdaptiveAlgorithm,
    "ca_maxpressure": CAMaxPressureAlgorithm,
}


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
        self._records: dict[str, RunResult] = {}
        self._stops: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def submit(self, request: RunRequest) -> RunResult:
        """Queue a validated request and return its isolated run identity."""
        self._validate(request)
        artifacts = self._create_artifacts(request)
        stop_event = threading.Event()
        queued = RunResult(
            artifacts.run_id,
            RunStatus.QUEUED,
            "",
            artifacts.run_dir,
        )
        with self._lock:
            self._records[artifacts.run_id] = queued
            self._stops[artifacts.run_id] = stop_event
        self._executor.submit(self._execute, request, artifacts, stop_event)
        return queued

    def run_sync(self, request: RunRequest) -> RunResult:
        """Execute one request synchronously through the same internal path."""
        self._validate(request)
        artifacts = self._create_artifacts(request)
        stop_event = threading.Event()
        with self._lock:
            self._stops[artifacts.run_id] = stop_event
        return self._execute(request, artifacts, stop_event)

    def get(self, run_id: str) -> RunResult | None:
        with self._lock:
            return self._records.get(run_id)

    def stop(self, run_id: str) -> bool:
        with self._lock:
            stop_event = self._stops.get(run_id)
        if stop_event is None:
            return False
        stop_event.set()
        return True

    def shutdown(self, wait: bool = True) -> None:
        self._executor.shutdown(wait=wait)

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
        self._store(
            RunResult(
                artifacts.run_id,
                RunStatus.RUNNING,
                "",
                artifacts.run_dir,
            )
        )
        try:
            scene = self.registry.get_scene(request.intersection_id)
            additional_files = []
            if request.flow_multiplier != 1.0:
                additional_files.append(
                    VariantGenerator().generate_scaled(
                        scene.meta,
                        request.flow_multiplier,
                        artifacts.run_dir / "variants",
                    )
                )
            state_channel = None
            if request.edge_delay_steps or request.edge_directions:
                state_channel = EdgeChannel(
                    delay_steps=request.edge_delay_steps,
                    allowed_directions=list(request.edge_directions) or None,
                )
            runner = self.runner_factory(
                scene=scene,
                algorithm=ALGORITHM_FACTORIES[request.algorithm](),
                additional_files=additional_files,
                seed=request.seed,
                artifacts=artifacts,
                state_channel=state_channel,
            )
            runner.run(request.steps, stop_event=stop_event)
        except Exception as exc:
            if not artifacts.metadata.exists():
                now = datetime.now(timezone.utc).isoformat()
                artifacts.write_metadata(
                    RunStatus.FAILED.value,
                    str(exc) or type(exc).__name__,
                    [],
                    started_at=now,
                    ended_at=now,
                    sumo_version="unknown",
                )
        result = self._result_from_artifacts(artifacts)
        self._store(result)
        return result

    def _result_from_artifacts(self, artifacts: RunArtifacts) -> RunResult:
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
        )

    def _store(self, result: RunResult) -> None:
        with self._lock:
            self._records[result.run_id] = result

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
        if request.steps <= 0:
            raise ValueError("steps must be > 0")
        if request.flow_multiplier <= 0:
            raise ValueError("flow_multiplier must be > 0")
        if request.seed < 0:
            raise ValueError("seed must be >= 0")
        if request.edge_delay_steps < 0:
            raise ValueError("edge_delay_steps must be >= 0")
