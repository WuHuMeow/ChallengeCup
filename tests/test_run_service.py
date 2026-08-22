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
from api.realtime import RealtimeHub
from core.run_models import RunRequest, RunStatus, VariantSpec
from core.timebase import SimulationWindow, seconds_for_steps
from core.types import Scene
from scenes.models import SceneManifest
from scenes.registry import SceneRegistry
from engine.artifacts import RunArtifacts
from engine.run_service import RunService
from engine.runner import SimulationRunner
from engine.mock_bridge import MockBridge
from engine.traci_bridge import TraCIBridge, traci
from experiments.evidence import EvidenceReader, EvidenceWriter
from scripts.run_pdf_matrix import build_profile_matrix, is_complete, parse_matrix_args
from visualization.frame_publisher import FramePublisher


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
        super().__init__(
            bridge=_ServiceOutputBridge(
                kwargs["artifacts"], step_length=step_length
            ),
            **kwargs,
        )
        type(self).instances.append(self)


class CorruptStatusRunner(RecordingRunner):
    def run(self, window, stop_event=None, frame_sink=None):
        self.artifacts.status.write_text("{not-json", encoding="utf-8")
        raise RuntimeError("runner failure after status corruption")


class MalformedStatusRecordRunner(RecordingRunner):
    def run(self, window, stop_event=None, frame_sink=None):
        self.artifacts.status.write_text("[]", encoding="utf-8")
        raise RuntimeError("runner failure after malformed status record")


class _ServiceOutputBridge(MockBridge):
    def __init__(self, artifacts, *, step_length=0.1):
        super().__init__(step_length=step_length)
        self.artifacts = artifacts
        self.sumo_version = "1.27.1"

    def close(self):
        self.artifacts.tripinfo.write_text(
            '<tripinfos><tripinfo id="v0" depart="0" arrival="1" '
            'duration="1" timeLoss="0" waitingCount="0">'
            '<emissions fuel_abs="0.1" CO2_abs="100"/></tripinfo></tripinfos>',
            encoding="utf-8",
        )
        self.artifacts.stats.write_text(
            '<summary><step time="1"/></summary>', encoding="utf-8"
        )
        self.artifacts.trajectory.write_text("<fcd-export/>", encoding="utf-8")
        self.artifacts.collisions.write_text("<collisions/>", encoding="utf-8")
        super().close()


def _evidence_runner_factory(**kwargs):
    return SimulationRunner(
        bridge=_ServiceOutputBridge(kwargs["artifacts"]),
        **kwargs,
    )


def _smoke_evidence_runner_factory(**kwargs):
    return SimulationRunner(
        bridge=_ServiceOutputBridge(
            kwargs["artifacts"],
            step_length=float(kwargs["step_length"]),
        ),
        **kwargs,
    )


class SpoofingEvidenceRunner(SimulationRunner):
    def run(self, window, stop_event=None, frame_sink=None):
        result = super().run(window, stop_event=stop_event, frame_sink=frame_sink)
        return replace(
            result,
            summary={"metrics": {"throughput": 999999}},
        )


def _spoofing_evidence_runner_factory(**kwargs):
    return SpoofingEvidenceRunner(
        bridge=_ServiceOutputBridge(kwargs["artifacts"]),
        **kwargs,
    )


class TerminalThenInterruptEvidenceRunner(SimulationRunner):
    error = KeyboardInterrupt("interrupt after terminal evidence")

    def run(self, window, stop_event=None, frame_sink=None):
        super().run(window, stop_event=stop_event, frame_sink=frame_sink)
        raise type(self).error


def _terminal_then_interrupt_evidence_runner_factory(**kwargs):
    return TerminalThenInterruptEvidenceRunner(
        bridge=_ServiceOutputBridge(kwargs["artifacts"]),
        **kwargs,
    )


class InterruptingRunner:
    error = KeyboardInterrupt("operator interrupt")

    def __init__(self, **kwargs):
        self.artifacts = kwargs["artifacts"]

    def run(self, window, stop_event=None, frame_sink=None):
        raise type(self).error


class ExitingRunner:
    error = SystemExit("runner requested process exit")

    def __init__(self, **kwargs):
        self.artifacts = kwargs["artifacts"]

    def run(self, window, stop_event=None, frame_sink=None):
        raise type(self).error


class FailingRunner:
    error = RuntimeError("runner body failed")

    def __init__(self, **kwargs):
        self.artifacts = kwargs["artifacts"]

    def run(self, window, stop_event=None, frame_sink=None):
        raise type(self).error


class TerminalThenInterruptRunner:
    error = KeyboardInterrupt("interrupt after terminal commit")

    def __init__(self, **kwargs):
        self.artifacts = kwargs["artifacts"]

    def run(self, window, stop_event=None, frame_sink=None):
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            "completed",
            "",
            [],
            started_at=now,
            ended_at=now,
            sumo_version="test",
            requested_steps=1,
            requested_seconds=1.0,
            warmup_seconds=0.0,
            final_simulation_time=1.0,
            step_length=1.0,
        )
        raise type(self).error


class StrictSignatureRunner:
    constructed = False

    def __init__(
        self,
        scene,
        algorithm,
        additional_files,
        sumo_cfg,
        seed,
        artifacts,
        state_channel,
        step_length,
    ):
        type(self).constructed = True
        self.artifacts = artifacts

    def run(self, window, stop_event=None, frame_sink=None):
        now = datetime.now(timezone.utc).isoformat()
        self.artifacts.write_metadata(
            "completed",
            "",
            [],
            started_at=now,
            ended_at=now,
            sumo_version="test",
            requested_steps=1,
            requested_seconds=1.0,
            warmup_seconds=0.0,
            final_simulation_time=1.0,
            step_length=1.0,
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


@pytest.mark.parametrize("step_length", [1.0, 81 / 997])
def test_explicit_steps_survive_service_window_without_float_roundtrip(
    step_length,
):
    """Catch explicit steps being reconstructed with a seconds-first ceiling."""
    request = RunRequest("1", "fixed_time", steps=100)

    window = RunService._window(request, step_length)

    assert window.duration_seconds == seconds_for_steps(100, step_length)
    assert window.warmup_seconds == 0
    assert window.explicit_steps == 100


def test_explicit_steps_preserve_a_valid_warmup_window():
    request = RunRequest(
        "1",
        "fixed_time",
        steps=100,
        duration_seconds=200,
        warmup_seconds=25,
    )

    window = RunService._window(request, 1.0)

    assert window.duration_seconds == 100
    assert window.warmup_seconds == 25
    assert window.explicit_steps == 100


def test_explicit_steps_reject_warmup_that_exceeds_actual_window():
    request = RunRequest(
        "1",
        "fixed_time",
        steps=100,
        duration_seconds=200,
        warmup_seconds=100,
    )

    with pytest.raises(ValueError, match="warmup_seconds"):
        RunService._window(request, 1.0)


def test_run_service_derives_steps_from_tenth_second_scene_window(tmp_path):
    RecordingRunner.run_steps = []
    service = RunService(output_root=tmp_path, runner_factory=RecordingRunner)

    result = service.run_sync(RunRequest("12", "fixed_time"))

    assert result.status is RunStatus.COMPLETED
    assert RecordingRunner.run_steps[-1] == SimulationWindow(3600, 600)


def test_default_smoke_flows_through_service_to_sealed_evidence(tmp_path):
    args = parse_matrix_args([
        "--profile", "smoke", "--output-root", str(tmp_path / "matrix")
    ])
    spec = build_profile_matrix(args)[0]
    request = spec.to_request(tmp_path / "runs")
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=_smoke_evidence_runner_factory,
    )

    result = service.run_sync(request)

    manifest = json.loads(
        (result.run_dir / "manifest.json").read_text(encoding="utf-8")
    )
    metadata = json.loads(
        (result.run_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert request.steps == 100
    assert request.duration_seconds == 100
    assert result.status is RunStatus.COMPLETED
    assert manifest["derived_steps"] == 100
    assert manifest["requested_seconds"] == 100
    assert metadata["requested_steps"] == 100
    assert metadata["requested_seconds"] == 100
    assert EvidenceReader.validate(result.run_dir) == []
    assert is_complete(result.run_dir, request) is True


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
            super().__init__(
                bridge=_ServiceOutputBridge(
                    kwargs["artifacts"], step_length=1.0
                ),
                **kwargs,
            )
            type(self).instances.append(self)

    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=AuthoritativeRunner,
        registry=registry,
    )
    result = service.run_sync(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )

    manifest = json.loads(
        (result.run_dir / "manifest.json").read_text(encoding="utf-8")
    )
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


@pytest.mark.parametrize(
    ("steps", "expected_origin"),
    [(None, "compatibility"), (36000, "explicit")],
)
def test_run_manifest_records_request_steps_origin(
    tmp_path, steps, expected_origin
):
    service = RunService(output_root=tmp_path, runner_factory=RecordingRunner)

    result = service.run_sync(
        RunRequest(
            "1",
            "fixed_time",
            steps=steps,
            duration_seconds=3600,
            warmup_seconds=600,
            step_length_override=0.1,
        )
    )

    manifest = json.loads((result.run_dir / "manifest.json").read_text())
    assert manifest["steps_origin"] == expected_origin


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


def test_malformed_status_record_still_completes_future_as_failed(tmp_path):
    service = RunService(output_root=tmp_path, runner_factory=MalformedStatusRecordRunner)
    queued = service.submit(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )

    try:
        result = service._futures[queued.run_id].result(timeout=2)
    finally:
        service.shutdown(wait=True)

    status = json.loads((result.run_dir / "status.json").read_text(encoding="utf-8"))
    metadata = json.loads(
        (result.run_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert result.status is RunStatus.FAILED
    assert "status artifact corruption" in result.reason.lower()
    assert "runner failure after malformed status record" in result.reason
    assert status["status"] == "failed"
    assert "corrupt" in status["reason"].lower()
    assert metadata["status"] == "failed"
    assert "corrupt" in metadata["reason"].lower()
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
    assert not (result.run_dir / "summary.json").exists()
    assert EvidenceReader.validate(result.run_dir) == []


def test_run_service_completed_path_produces_reader_valid_evidence(tmp_path):
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=_evidence_runner_factory,
    )

    result = service.run_sync(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )

    assert result.status is RunStatus.COMPLETED
    assert EvidenceReader.validate(result.run_dir) == []


def test_real_evidence_runner_result_matches_its_current_matrix_request(tmp_path):
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=_evidence_runner_factory,
    )
    request = RunRequest("1", "fixed_time", steps=1)

    result = service.run_sync(request)

    manifest = json.loads(
        (result.run_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["parameters"]
    assert manifest["request_dimensions"]["algorithm_params"] == {}
    assert is_complete(result.run_dir, request) is True


def test_run_service_replaces_evidence_runner_memory_summary_with_sealed_disk(
    tmp_path,
):
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=_spoofing_evidence_runner_factory,
    )

    result = service.run_sync(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )

    assert result.summary["metrics"]["throughput"] == 1
    assert service.get(result.run_id).summary["metrics"]["throughput"] == 1


def test_run_service_keyboard_interrupt_preserves_primary_and_terminalizes_evidence(
    tmp_path,
):
    InterruptingRunner.error = KeyboardInterrupt("operator interrupt")
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=InterruptingRunner,
    )

    with pytest.raises(KeyboardInterrupt) as caught:
        service.run_sync(
            RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
        )

    assert caught.value is InterruptingRunner.error
    status_path = next((tmp_path / "runs").rglob("status.json"))
    run_dir = status_path.parent
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == (
        "interrupted"
    )
    assert service.get(run_dir.name).status is RunStatus.INTERRUPTED
    assert EvidenceReader.validate(run_dir) == []


def test_run_service_system_exit_preserves_primary_and_terminalizes_failed_evidence(
    tmp_path,
):
    ExitingRunner.error = SystemExit("runner requested process exit")
    service = RunService(output_root=tmp_path / "runs", runner_factory=ExitingRunner)

    with pytest.raises(SystemExit) as caught:
        service.run_sync(
            RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
        )

    assert caught.value is ExitingRunner.error
    status_path = next((tmp_path / "runs").rglob("status.json"))
    run_dir = status_path.parent
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == "failed"
    assert service.get(run_dir.name).status is RunStatus.FAILED
    assert service._done[run_dir.name].is_set()
    assert EvidenceReader.validate(run_dir) == []


@pytest.mark.parametrize("secondary", ["finalize", "seal"])
def test_run_service_body_failure_remains_primary_when_evidence_commit_fails(
    tmp_path,
    secondary,
):
    FailingRunner.error = RuntimeError("runner body failed")
    service = RunService(output_root=tmp_path / "runs", runner_factory=FailingRunner)

    with patch.object(
        EvidenceWriter,
        secondary,
        side_effect=OSError(f"{secondary} unavailable"),
    ):
        result = service.run_sync(
            RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
        )

    assert result.status is RunStatus.FAILED
    assert "runner body failed" in result.reason
    assert service.get(result.run_id).status is RunStatus.FAILED
    assert service._done[result.run_id].is_set()
    status = json.loads(
        (result.run_dir / "status.json").read_text(encoding="utf-8")
    )
    assert status["status"] == "failed"


def test_secondary_error_can_never_be_sealed_clean_when_error_recording_fails(
    tmp_path,
):
    FailingRunner.error = RuntimeError("runner body failed")
    service = RunService(output_root=tmp_path / "runs", runner_factory=FailingRunner)

    with (
        patch.object(
            EvidenceWriter,
            "finalize",
            side_effect=OSError("finalize unavailable"),
        ),
        patch.object(
            EvidenceWriter,
            "record_error",
            side_effect=OSError("error record unavailable"),
        ),
    ):
        result = service.run_sync(
            RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
        )

    assert result.status is RunStatus.FAILED
    assert "runner body failed" in result.reason
    assert "finalize unavailable" in result.reason
    assert not (result.run_dir / "hashes.json").exists()
    assert EvidenceReader.validate(result.run_dir)


@pytest.mark.parametrize("secondary", ["finalize", "metadata"])
def test_keyboard_interrupt_identity_survives_terminalization_failure(
    tmp_path,
    secondary,
):
    InterruptingRunner.error = KeyboardInterrupt("operator interrupt")
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=InterruptingRunner,
    )
    target = (
        patch.object(
            EvidenceWriter,
            "finalize",
            side_effect=OSError("finalize unavailable"),
        )
        if secondary == "finalize"
        else patch.object(
            service,
            "_write_terminal_metadata",
            side_effect=OSError("metadata unavailable"),
        )
    )

    with target:
        with pytest.raises(KeyboardInterrupt) as caught:
            service.run_sync(
                RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
            )

    assert caught.value is InterruptingRunner.error
    run_id = next(iter(service._done))
    assert service.get(run_id).status is RunStatus.INTERRUPTED
    assert service._done[run_id].is_set()


def test_primary_keyboard_interrupt_survives_cleanup_base_exception(tmp_path):
    InterruptingRunner.error = KeyboardInterrupt("primary operator interrupt")
    cleanup_interrupt = KeyboardInterrupt("cleanup interrupt")
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=InterruptingRunner,
    )

    with patch.object(
        EvidenceWriter,
        "finalize",
        side_effect=cleanup_interrupt,
    ):
        with pytest.raises(KeyboardInterrupt) as caught:
            service.run_sync(
                RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
            )

    assert caught.value is InterruptingRunner.error
    run_id = next(iter(service._done))
    assert service.get(run_id).status is RunStatus.INTERRUPTED
    assert service._done[run_id].is_set()


def test_primary_keyboard_interrupt_survives_persistent_status_storage_failure(
    tmp_path,
):
    InterruptingRunner.error = KeyboardInterrupt("primary operator interrupt")
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=InterruptingRunner,
    )
    original_write_status = RunArtifacts.write_status

    def fail_terminal_status(artifacts, status, reason, **kwargs):
        if status in {
            RunStatus.COMPLETED.value,
            RunStatus.ENDED_EARLY.value,
            RunStatus.DISCONNECTED.value,
            RunStatus.INTERRUPTED.value,
            RunStatus.FAILED.value,
        }:
            raise OSError("status storage unavailable")
        return original_write_status(artifacts, status, reason, **kwargs)

    with patch.object(RunArtifacts, "write_status", new=fail_terminal_status):
        with pytest.raises(KeyboardInterrupt) as caught:
            service.run_sync(
                RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
            )

    assert caught.value is InterruptingRunner.error
    run_id = next(iter(service._done))
    assert service.get(run_id).status is RunStatus.INTERRUPTED
    assert service._done[run_id].is_set()


def test_keyboard_interrupt_after_terminal_commit_never_overwrites_or_masks_primary(
    tmp_path,
):
    TerminalThenInterruptRunner.error = KeyboardInterrupt(
        "interrupt after terminal commit"
    )
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=TerminalThenInterruptRunner,
    )

    with pytest.raises(KeyboardInterrupt) as caught:
        service.run_sync(
            RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
        )

    assert caught.value is TerminalThenInterruptRunner.error
    status_path = next((tmp_path / "runs").rglob("status.json"))
    run_id = status_path.parent.name
    assert json.loads(status_path.read_text(encoding="utf-8"))["status"] == (
        "completed"
    )
    assert service.get(run_id).status is RunStatus.COMPLETED


def test_terminal_interrupt_with_seal_failure_never_exposes_raw_summary(tmp_path):
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=_terminal_then_interrupt_evidence_runner_factory,
    )

    with patch(
        "engine.run_service.EvidenceWriter.seal",
        side_effect=RuntimeError("hash storage unavailable"),
    ):
        with pytest.raises(KeyboardInterrupt) as caught:
            service.run_sync(
                RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
            )

    assert caught.value is TerminalThenInterruptEvidenceRunner.error
    run_id = next(iter(service._done))
    assert service.get(run_id).status is RunStatus.COMPLETED
    assert service.get(run_id).summary is None


def test_run_service_preserves_runner_factory_signature_compatibility(tmp_path):
    StrictSignatureRunner.constructed = False
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=StrictSignatureRunner,
    )

    result = service.run_sync(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )

    assert StrictSignatureRunner.constructed is True
    assert result.status is RunStatus.COMPLETED
    # Lifecycle completion is not evidence publication. Injected legacy runners
    # without evidence_managed remain compatible but can never pass the strict
    # matrix/release gate.
    assert is_complete(result.run_dir) is False
    assert EvidenceReader.validate(result.run_dir)


def test_service_seal_failure_records_invalid_evidence_without_terminal_rewrite(
    tmp_path,
):
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=_evidence_runner_factory,
    )

    with patch(
        "engine.run_service.EvidenceWriter.seal",
        side_effect=RuntimeError("hash storage unavailable"),
    ):
        result = service.run_sync(
            RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
        )

    manifest = json.loads(
        (result.run_dir / "manifest.json").read_text(encoding="utf-8")
    )
    status = json.loads(
        (result.run_dir / "status.json").read_text(encoding="utf-8")
    )
    assert result.status is RunStatus.COMPLETED
    assert service.get(result.run_id).status is RunStatus.COMPLETED
    assert result.summary is None
    assert service.get(result.run_id).summary is None
    assert status["status"] == "completed"
    assert "hash storage unavailable" in result.reason
    assert manifest["evidence_error"] == "hash storage unavailable"
    assert not (result.run_dir / "hashes.json").exists()
    assert is_complete(result.run_dir) is False


def test_run_service_publishes_failed_status_when_runner_raises(tmp_path):
    hub = RealtimeHub()
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=FailingRunner,
        realtime_hub=hub,
    )

    result = service.run_sync(
        RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
    )

    run_id = result.run_id
    assert result.status is RunStatus.FAILED
    assert hub.latest(run_id)["status"] == "failed"
    assert hub.latest(run_id)["reason"] == "runner body failed"


def test_run_service_publishes_interrupted_status_before_reraising(tmp_path):
    InterruptingRunner.error = KeyboardInterrupt("operator interrupt")
    hub = RealtimeHub()
    service = RunService(
        output_root=tmp_path / "runs",
        runner_factory=InterruptingRunner,
        realtime_hub=hub,
    )

    with pytest.raises(KeyboardInterrupt, match="operator interrupt"):
        service.run_sync(
            RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
        )

    run_id = next(iter(service._done))
    assert hub.latest(run_id)["status"] == "interrupted"
    assert hub.latest(run_id)["reason"] == "operator interrupt"


def test_run_service_continues_when_runner_signature_cannot_be_inspected(tmp_path):
    service = RunService(output_root=tmp_path / "runs", runner_factory=RecordingRunner)

    with patch(
        "engine.run_service.inspect.signature",
        side_effect=ValueError("signature unavailable"),
    ):
        result = service.run_sync(
            RunRequest("1", "fixed_time", duration_seconds=1, warmup_seconds=0)
        )

    assert result.status is RunStatus.COMPLETED


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


def test_run_service_publishes_lifecycle_status_and_owns_runtime_sinks(tmp_path):
    BlockingRunner.release.clear()
    BlockingRunner.started.clear()
    publisher = FramePublisher()
    hub = RealtimeHub()
    service = RunService(
        output_root=tmp_path,
        runner_factory=BlockingRunner,
        frame_publisher=publisher,
        realtime_hub=hub,
    )

    queued = service.submit(RunRequest("1", "fixed_time", steps=1))

    assert isinstance(service.frame_publisher, FramePublisher)
    assert isinstance(service.realtime_hub, RealtimeHub)
    assert hub.latest(queued.run_id) == {
        "run_id": queued.run_id,
        "type": "status",
        "status": "queued",
        "reason": "",
        "simulation_time": 0.0,
    }
    assert BlockingRunner.started.wait(timeout=2)

    assert service.stop(queued.run_id) is True
    assert hub.latest(queued.run_id)["status"] == "interrupted"
    service.shutdown()
