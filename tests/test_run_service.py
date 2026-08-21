import csv
import json
import threading
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.base import BaseControlAlgorithm
from algorithms.registry import AlgorithmRegistry, AlgorithmSpec
from core.run_models import RunRequest, RunStatus, VariantSpec
from core.timebase import SimulationWindow
from core.types import Scene
from scenes.models import SceneManifest
from scenes.registry import SceneRegistry
from engine.run_service import RunService
from engine.runner import SimulationRunner
from engine.mock_bridge import MockBridge
from engine.traci_bridge import TraCIBridge, traci


class RecordingRunner:
    calls = []
    run_steps = []

    def __init__(self, **kwargs):
        self.artifacts = kwargs["artifacts"]
        type(self).calls.append(kwargs)

    def run(self, window, stop_event=None, frame_sink=None):
        type(self).run_steps.append(window)
        status = "interrupted" if stop_event and stop_event.is_set() else "completed"
        self.artifacts.metrics.write_text("step\n0\n", encoding="utf-8")
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            status,
            "stop requested" if status == "interrupted" else "",
            [self.artifacts.metrics],
            started_at=now,
            ended_at=now,
            sumo_version="test",
        )
        return []


class ValidatedRegistry:
    def __init__(self, scene, manifest):
        self.scene = scene
        self.manifest = manifest

    def get_scene(self, intersection_id):
        assert intersection_id == self.scene.meta.intersection_id
        return self.scene

    def list_scenes(self, formal_only=False):
        return () if self.manifest is None else (self.manifest,)


class EdgeMappingRunner(SimulationRunner):
    instances = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        type(self).instances.append(self)

    def run(self, steps, stop_event=None):
        controlled_lanes = ["-E1_0", "-E1_1", "E0_0"]
        controlled_links = ((('-E1_0', 'E1_0', ':via'),),)
        program = SimpleNamespace(
            programID="0",
            phases=(SimpleNamespace(state="G", duration=30.0),),
        )
        with (
            patch.object(TraCIBridge, "_start_owned_connection"),
            patch.object(traci.trafficlight, "getIDList", return_value=["tls"]),
            patch.object(
                traci.trafficlight,
                "getControlledLanes",
                return_value=controlled_lanes,
            ),
            patch.object(
                traci.trafficlight,
                "getControlledLinks",
                return_value=controlled_links,
            ),
            patch.object(
                traci.trafficlight, "getAllProgramLogics", return_value=[program]
            ),
            patch.object(traci.trafficlight, "getProgram", return_value="0"),
            patch.object(traci.trafficlight, "setProgram"),
        ):
            self.bridge.start()
        self.artifacts.metrics.write_text("step\n0\n", encoding="utf-8")
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            "completed",
            "",
            [self.artifacts.metrics],
            started_at=now,
            ended_at=now,
            sumo_version="test",
        )
        return []


class TickRecordingAlgorithm(BaseControlAlgorithm):
    def __init__(self):
        self.steps = []

    def init(self, scene):
        self.scene = scene

    def step(self, state):
        self.steps.append(state.step)
        return []

    def reset(self):
        self.steps = []

    @property
    def name(self):
        return "fixed_time"


class EffectiveStepRunner(SimulationRunner):
    instances = []

    def __init__(self, **kwargs):
        self.runtime_cfg = kwargs["sumo_cfg"]
        step_length = float(
            ET.parse(self.runtime_cfg).getroot().find("./time/step-length").get("value")
        )
        super().__init__(bridge=MockBridge(step_length=step_length), **kwargs)
        type(self).instances.append(self)


class CorruptStatusRunner(RecordingRunner):
    def run(self, window, stop_event=None, frame_sink=None):
        self.artifacts.status.write_text("{not-json", encoding="utf-8")
        raise RuntimeError("runner failure after status corruption")


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
    assert RecordingRunner.run_steps[-1] == SimulationWindow(3600, 600)


def test_run_service_derives_steps_from_one_second_step_length(tmp_path):
    base_registry = SceneRegistry()
    base_scene = base_registry.get_scene("1")
    custom_cfg = tmp_path / "one-second.sumocfg"
    custom_cfg.write_text(
        "<configuration><time><step-length value='1.0'/></time></configuration>",
        encoding="utf-8",
    )

    RecordingRunner.run_steps = []
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=RecordingRunner,
        registry=ValidatedRegistry(
            Scene(meta=replace(base_scene.meta, sumo_cfg=custom_cfg)),
            SceneManifest(
                scene_id="1", step_length=1.0, validation_status="pass"
            ),
        ),
    )

    result = service.run_sync(RunRequest("1", "fixed_time"))

    assert result.status is RunStatus.COMPLETED
    assert RecordingRunner.run_steps[-1] == SimulationWindow(3600, 600)


def test_run_service_uses_validated_manifest_timebase_instead_of_raw_xml(tmp_path):
    base_scene = SceneRegistry().get_scene("1")
    raw_cfg = tmp_path / "raw-one-second.sumocfg"
    raw_cfg.write_text(
        "<configuration><time><step-length value='1.0'/></time></configuration>",
        encoding="utf-8",
    )
    registry = ValidatedRegistry(
        Scene(meta=replace(base_scene.meta, sumo_cfg=raw_cfg)),
        SceneManifest(scene_id="1", step_length=0.25, validation_status="pass"),
    )
    RecordingRunner.calls = []
    RecordingRunner.run_steps = []
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=RecordingRunner,
        registry=registry,
    )

    result = service.run_sync(
        RunRequest(
            "1", "fixed_time", duration_seconds=1, warmup_seconds=0
        )
    )

    manifest = json.loads((result.run_dir / "manifest.json").read_text())
    assert result.status is RunStatus.COMPLETED
    assert manifest["step_length"] == 0.25
    assert manifest["derived_steps"] == 4
    assert RecordingRunner.run_steps == [SimulationWindow(1, 0)]


def test_runner_keeps_validated_step_length_authoritative_over_bridge(tmp_path):
    base_scene = SceneRegistry().get_scene("1")
    registry = ValidatedRegistry(
        base_scene,
        SceneManifest(scene_id="1", step_length=0.25, validation_status="pass"),
    )

    class AuthoritativeRunner(SimulationRunner):
        instances = []

        def __init__(self, **kwargs):
            self.runtime_cfg = kwargs["sumo_cfg"]
            super().__init__(bridge=MockBridge(step_length=1.0), **kwargs)
            type(self).instances.append(self)

    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=AuthoritativeRunner,
        registry=registry,
    )
    result = service.run_sync(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )

    manifest = json.loads((result.run_dir / "manifest.json").read_text())
    metadata = json.loads(
        (result.run_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert result.status is RunStatus.COMPLETED
    assert manifest["step_length"] == 0.25
    assert manifest["derived_steps"] == 4
    assert AuthoritativeRunner.instances[-1].bridge._current_step == 4
    assert float(
        ET.parse(AuthoritativeRunner.instances[-1].runtime_cfg)
        .getroot()
        .find("./time/step-length")
        .get("value")
    ) == 0.25
    assert metadata["step_length"] == 0.25


def test_formal_override_retains_declared_warmup(tmp_path):
    RecordingRunner.run_steps = []
    service = RunService(output_root=tmp_path, runner_factory=RecordingRunner)

    result = service.run_sync(
        RunRequest(
            "1",
            "fixed_time",
            duration_seconds=3600,
            warmup_seconds=600,
            step_length_override=0.1,
        )
    )

    assert result.status is RunStatus.COMPLETED
    assert RecordingRunner.run_steps[-1] == SimulationWindow(3600, 600)


def test_manifest_runtime_scene_identity_mismatch_fails_closed(tmp_path):
    base_scene = SceneRegistry().get_scene("1")
    raw_cfg = tmp_path / "runtime.sumocfg"
    raw_cfg.write_text("<configuration />", encoding="utf-8")
    registry = ValidatedRegistry(
        Scene(meta=replace(base_scene.meta, sumo_cfg=raw_cfg)),
        SceneManifest(
            scene_id="1",
            step_length=1.0,
            validation_status="pass",
            source_files={"sumocfg": "different.sumocfg"},
            sha256={"sumocfg": "deadbeef"},
        ),
    )
    RecordingRunner.calls = []
    service = RunService(
        output_root=tmp_path / "runs", runner_factory=RecordingRunner, registry=registry
    )

    result = service.run_sync(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )

    assert result.status is RunStatus.FAILED
    assert "identity" in result.reason.lower()
    assert RecordingRunner.calls == []


def test_corrupt_status_artifact_still_reaches_terminal_failed_result(tmp_path):
    service = RunService(output_root=tmp_path, runner_factory=CorruptStatusRunner)

    queued = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )
    service.shutdown(wait=True)
    result = service.get(queued.run_id)

    assert result is not None
    assert result.status is RunStatus.FAILED
    assert "status artifact" in result.reason.lower()
    assert "runner failure after status corruption" in result.reason
    assert json.loads(
        (result.run_dir / "status.json").read_text(encoding="utf-8")
    )["status"] == "failed"
    assert service.stop(queued.run_id) is False


@pytest.mark.parametrize(
    "manifest",
    [
        None,
        SceneManifest(
            scene_id="1",
            step_length=0.25,
            validation_status="fail",
            warnings=("invalid step-length",),
        ),
    ],
    ids=("missing", "failed"),
)
def test_run_service_rejects_scene_without_passing_validated_manifest(
    tmp_path, manifest
):
    base_scene = SceneRegistry().get_scene("1")
    raw_cfg = tmp_path / "runnable.sumocfg"
    raw_cfg.write_text(
        "<configuration><time><step-length value='1.0'/></time></configuration>",
        encoding="utf-8",
    )
    RecordingRunner.calls = []
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=RecordingRunner,
        registry=ValidatedRegistry(
            Scene(meta=replace(base_scene.meta, sumo_cfg=raw_cfg)), manifest
        ),
    )

    result = service.run_sync(
        RunRequest(
            "1", "fixed_time", duration_seconds=1, warmup_seconds=0
        )
    )

    assert result.status is RunStatus.FAILED
    assert "validated scene" in result.reason.lower()
    assert RecordingRunner.calls == []


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
                closed_lanes=("E0_0",),
                closure_begin=10,
                closure_end=20,
            ),
        )
    )

    additional_files = RecordingRunner.calls[0]["additional_files"]
    assert result.status is RunStatus.COMPLETED
    assert len(additional_files) == 2
    assert RecordingRunner.calls[0]["sumo_cfg"].name == "demo_1_variant.sumocfg"
    assert (result.run_dir / "variants" / "variant_manifest.json").is_file()


def test_run_service_variant_applies_edge_mapping_through_real_runner(tmp_path):
    EdgeMappingRunner.instances = []
    service = RunService(output_root=tmp_path, runner_factory=EdgeMappingRunner)

    result = service.run_sync(RunRequest("1", "fixed_time", steps=1))

    bridge = EdgeMappingRunner.instances[0].bridge
    assert result.status is RunStatus.COMPLETED
    assert bridge._inbound_lanes == ["-E1_0", "-E1_1", "E0_0"]
    assert bridge.lane_directions == {
        "-E1_0": "东",
        "-E1_1": "东",
        "E0_0": "西",
    }


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


def test_run_service_converts_edge_delay_steps_to_scene_seconds(tmp_path):
    """Two 0.5-second ticks must delay an edge state until simulation time 1.0."""
    base_scene = SceneRegistry().get_scene("1")
    custom_cfg = tmp_path / "half-second.sumocfg"
    custom_cfg.write_text(
        "<configuration><time><step-length value='0.5'/></time></configuration>",
        encoding="utf-8",
    )

    RecordingRunner.calls = []
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=RecordingRunner,
        registry=ValidatedRegistry(
            Scene(meta=replace(base_scene.meta, sumo_cfg=custom_cfg)),
            SceneManifest(
                scene_id="1", step_length=0.5, validation_status="pass"
            ),
        ),
    )

    result = service.run_sync(RunRequest("1", "fixed_time", steps=5, edge_delay_steps=2))

    channel = RecordingRunner.calls[-1]["state_channel"]
    assert result.status is RunStatus.COMPLETED
    assert channel.delay_seconds == 1.0


def test_step_override_drives_effective_sumo_ticks_and_edge_delay(tmp_path):
    """A 0.5-second override must change both SUMO ticks and two-step delivery."""
    base_scene = SceneRegistry().get_scene("1")
    source_cfg = tmp_path / "source-one-second.sumocfg"
    source_cfg.write_text(
        "<configuration><time><step-length value='1.0'/></time></configuration>",
        encoding="utf-8",
    )

    algorithm = TickRecordingAlgorithm()
    algorithms = AlgorithmRegistry()
    algorithms.register(
        AlgorithmSpec("fixed_time", "Fixed Time", lambda: algorithm, True, ())
    )
    EffectiveStepRunner.instances = []
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=EffectiveStepRunner,
        registry=ValidatedRegistry(
            Scene(meta=replace(base_scene.meta, sumo_cfg=source_cfg)),
            SceneManifest(
                scene_id="1", step_length=1.0, validation_status="pass"
            ),
        ),
        algorithm_registry=algorithms,
    )

    result = service.run_sync(RunRequest(
        "1", "fixed_time", steps=5, step_length_override=0.5, edge_delay_steps=2
    ))

    runner = EffectiveStepRunner.instances[-1]
    events = list(csv.DictReader(runner.artifacts.events.open(encoding="utf-8")))
    assert result.status is RunStatus.COMPLETED
    assert float(
        ET.parse(runner.runtime_cfg).getroot().find("./time/step-length").get("value")
    ) == 0.5
    assert runner.bridge.step_length == 0.5
    assert algorithm.steps == [0, 1, 2]
    assert [row["type"] for row in events].count("channel_wait") == 2


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

    def run(self, window, stop_event=None, frame_sink=None):
        type(self).started.set()
        while not type(self).release.wait(timeout=0.01):
            if stop_event is not None and stop_event.is_set():
                break
        return super().run(window, stop_event=stop_event)


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

    assert service.get(queued.run_id).status is RunStatus.INTERRUPTED
    assert service.stop("missing") is False
