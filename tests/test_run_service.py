import json
import threading
from dataclasses import replace
from datetime import datetime, timezone

from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.registry import AlgorithmRegistry, AlgorithmSpec
from core.run_models import RunRequest, RunStatus, VariantSpec
from core.types import Scene
from scenes.registry import SceneRegistry
from engine.run_service import RunService


class RecordingRunner:
    calls = []
    run_steps = []

    def __init__(self, **kwargs):
        self.artifacts = kwargs["artifacts"]
        type(self).calls.append(kwargs)

    def run(self, steps, stop_event=None):
        type(self).run_steps.append(steps)
        status = "stopped" if stop_event and stop_event.is_set() else "completed"
        self.artifacts.metrics.write_text("step\n0\n", encoding="utf-8")
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            status,
            "stop requested" if status == "stopped" else "",
            [self.artifacts.metrics],
            started_at=now,
            ended_at=now,
            sumo_version="test",
        )
        return []


def test_run_sync_returns_completed_result_with_isolated_artifacts(tmp_path):
    RecordingRunner.calls = []
    RecordingRunner.run_steps = []
    service = RunService(output_root=tmp_path, runner_factory=RecordingRunner)

    result = service.run_sync(RunRequest("1", "fixed_time", steps=2))

    assert result.status is RunStatus.COMPLETED
    assert result.run_dir.name == result.run_id
    assert json.loads((result.run_dir / "run_metadata.json").read_text())[
        "status"
    ] == "completed"
    assert len(RecordingRunner.calls) == 1


def test_run_service_derives_steps_from_tenth_second_scene_window(tmp_path):
    RecordingRunner.run_steps = []
    service = RunService(output_root=tmp_path, runner_factory=RecordingRunner)

    result = service.run_sync(RunRequest("12", "fixed_time"))

    assert result.status is RunStatus.COMPLETED
    assert RecordingRunner.run_steps[-1] == 36000


def test_run_service_derives_steps_from_one_second_step_length(tmp_path):
    base_registry = SceneRegistry()
    base_scene = base_registry.get_scene("1")
    custom_cfg = tmp_path / "one-second.sumocfg"
    custom_cfg.write_text(
        "<configuration><time><step-length value='1.0'/></time></configuration>",
        encoding="utf-8",
    )

    class CustomRegistry:
        def get_scene(self, intersection_id):
            return Scene(meta=replace(base_scene.meta, sumo_cfg=custom_cfg))

    RecordingRunner.run_steps = []
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=RecordingRunner,
        registry=CustomRegistry(),
    )

    result = service.run_sync(RunRequest("1", "fixed_time"))

    assert result.status is RunStatus.COMPLETED
    assert RecordingRunner.run_steps[-1] == 3600


def test_run_service_passes_complete_variant_bundle_to_runner(tmp_path):
    RecordingRunner.calls = []
    service = RunService(output_root=tmp_path, runner_factory=RecordingRunner)

    result = service.run_sync(
        RunRequest(
            "1",
            "fixed_time",
            steps=2,
            flow_multiplier=1.5,
            variant=VariantSpec(
                signal_duration_scale=1.1,
                closed_lanes=("edge_0_0",),
                closure_begin=10,
                closure_end=20,
            ),
        )
    )

    additional_files = RecordingRunner.calls[0]["additional_files"]
    assert result.status is RunStatus.COMPLETED
    assert len(additional_files) == 2
    assert RecordingRunner.calls[0]["sumo_cfg"].name == "variant.sumocfg"
    assert (result.run_dir / "variants" / "variant_manifest.json").is_file()


def test_run_service_injects_frozen_ca_mp_parameters(tmp_path):
    RecordingRunner.calls = []
    service = RunService(output_root=tmp_path, runner_factory=RecordingRunner)

    result = service.run_sync(
        RunRequest(
            "1",
            "capacity_aware_maxpressure",
            steps=2,
            algorithm_params={
                "overflow_occupancy_threshold": 0.85,
                "prediction_weight": 0.0,
                "base_green": 45.0,
            },
        )
    )

    algorithm = RecordingRunner.calls[0]["algorithm"]
    assert result.status is RunStatus.COMPLETED
    assert algorithm.overflow_threshold == 0.85
    assert algorithm.prediction_weight == 0.0
    assert algorithm.base_green == 45.0


def test_run_service_constructs_algorithms_through_injected_registry(tmp_path):
    constructed = []

    def factory():
        algorithm = FixedTimeAlgorithm()
        constructed.append(algorithm)
        return algorithm

    algorithm_registry = AlgorithmRegistry()
    algorithm_registry.register(
        AlgorithmSpec("fixed_time", "Fixed Time", factory, True, ())
    )
    RecordingRunner.calls = []
    service = RunService(
        output_root=tmp_path,
        runner_factory=RecordingRunner,
        algorithm_registry=algorithm_registry,
    )

    result = service.run_sync(RunRequest("1", "fixed_time", steps=2))

    assert result.status is RunStatus.COMPLETED
    assert RecordingRunner.calls[0]["algorithm"] is constructed[0]


class BlockingRunner(RecordingRunner):
    release = threading.Event()
    started = threading.Event()

    def run(self, steps, stop_event=None):
        type(self).started.set()
        type(self).release.wait(timeout=5)
        return super().run(steps, stop_event=stop_event)


def test_concurrent_submissions_are_queued_with_unique_run_ids(tmp_path):
    BlockingRunner.release.clear()
    BlockingRunner.started.clear()
    service = RunService(output_root=tmp_path, runner_factory=BlockingRunner)

    first = service.submit(RunRequest("1", "fixed_time", steps=1))
    second = service.submit(RunRequest("1", "fixed_time", steps=1))

    assert first.status is RunStatus.QUEUED
    assert second.status is RunStatus.QUEUED
    assert first.run_id != second.run_id
    assert first.run_dir != second.run_dir
    assert service.max_workers == 1

    BlockingRunner.release.set()
    service.shutdown(wait=True)


def test_stop_sets_the_matching_run_event(tmp_path):
    BlockingRunner.release.clear()
    BlockingRunner.started.clear()
    service = RunService(output_root=tmp_path, runner_factory=BlockingRunner)
    queued = service.submit(RunRequest("1", "fixed_time", steps=10))
    assert BlockingRunner.started.wait(timeout=2)

    assert service.stop(queued.run_id) is True
    BlockingRunner.release.set()
    service.shutdown(wait=True)

    assert service.get(queued.run_id).status is RunStatus.STOPPED
    assert service.stop("missing") is False
