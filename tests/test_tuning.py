import csv
import json
import subprocess
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from core.run_models import (
    DisturbanceSpec,
    RunRequest,
    RunResult,
    RunStatus,
    VariantSpec,
)
from core.types import MetricSummary
from engine.artifacts import RunArtifacts
from engine.events import EVENT_FIELDS
from experiments.evidence import (
    EvidenceReader,
    EvidenceWriter,
    RunManifest,
    canonical_mapping_sha256,
)
from experiments.tuning import (
    PARAMETER_GRID,
    _metrics,
    calibration_seeds,
    holdout_seeds,
    tune_ca_mp,
)
from scripts.run_pdf_matrix import (
    _load_result,
    _run_dir,
    build_pdf_matrix,
    is_complete,
    request_key,
    run_pdf_matrix,
)


def test_pdf_matrix_has_exact_360_requests():
    requests = build_pdf_matrix(Path("out"), steps=36000)

    assert len(requests) == 360
    assert {request.intersection_id for request in requests} == {
        str(index) for index in range(1, 21)
    }
    assert {request.algorithm for request in requests} == {
        "fixed_time",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    }
    assert {request.flow_multiplier for request in requests} == {1.0, 1.25}
    assert {request.seed for request in requests} == {42, 43, 44}
    assert all(request.steps == 36000 for request in requests)


def test_request_key_includes_step_origin_and_seconds_window_inputs():
    formal = RunRequest(
        "1",
        "fixed_time",
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )
    explicit = RunRequest(
        "1",
        "fixed_time",
        steps=36000,
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )
    no_override = RunRequest(
        "1", "fixed_time", duration_seconds=3600, warmup_seconds=300
    )

    formal_identity = json.loads(request_key(formal))
    explicit_identity = json.loads(request_key(explicit))
    no_override_identity = json.loads(request_key(no_override))

    assert formal_identity != explicit_identity
    assert formal_identity["steps_origin"] == "compatibility"
    assert explicit_identity["steps_origin"] == "explicit"
    assert no_override_identity["steps"] is None
    assert no_override_identity["steps_origin"] == "none"
    assert no_override_identity["duration_seconds"] == 3600
    assert no_override_identity["warmup_seconds"] == 300
    assert no_override_identity["step_length_override"] is None


@pytest.mark.parametrize(
    "request_overrides",
    [
        {"variant": VariantSpec(signal_duration_scale=1.1)},
        {
            "disturbance": DisturbanceSpec(
                "construction",
                begin_seconds=100.0,
                end_seconds=200.0,
                target="lane-1",
                intensity=0.5,
            )
        },
        {"edge_delay_steps": 2},
        {"edge_directions": ("north",)},
    ],
)
def test_request_key_includes_execution_dimensions(request_overrides):
    baseline = RunRequest("1", "fixed_time", steps=100)
    changed = RunRequest("1", "fixed_time", steps=100, **request_overrides)

    assert request_key(baseline) != request_key(changed)


def test_tuning_grid_and_seed_split_are_exact():
    assert PARAMETER_GRID == {
        "overflow_occupancy_threshold": (0.85, 0.90, 0.95),
        "prediction_weight": (0.0, 0.15),
        "base_green": (25.0, 35.0, 45.0),
    }
    assert calibration_seeds() == (42,)
    assert holdout_seeds() == (43, 44)


def test_tuning_request_uses_seconds_and_high_formal_traffic_level():
    from experiments.tuning import _request

    request = _request(Path("out"), "1", "fixed_time", 42)

    assert request.duration_seconds == 3600
    assert request.warmup_seconds == 600
    assert request.steps is None
    assert request.flow_multiplier == 1.25


def test_is_complete_rejects_legacy_nonempty_artifacts_without_evidence_contract(
    tmp_path,
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "run_metadata.json").write_text(
        json.dumps({"status": "completed"}),
        encoding="utf-8",
    )
    required = (
        "metrics.csv",
        "events.csv",
        "simulation_log.csv",
        "tripinfo.xml",
        "stats.xml",
        "traj.xml",
        "collisions.xml",
        "summary.json",
    )
    for name in required:
        (run_dir / name).write_text("x", encoding="utf-8")

    assert is_complete(run_dir) is False
    (run_dir / "summary.json").write_text("", encoding="utf-8")
    assert is_complete(run_dir) is False


def _write_completed_matrix_run(
    tmp_path,
    final_time,
    *,
    step_length=0.1,
    configured_end_time=None,
    request=None,
    run_id=None,
):
    resolved_run_id = run_id or f"run-{final_time}"
    intersection_id = request.intersection_id if request is not None else "1"
    algorithm = request.algorithm if request is not None else "fixed_time"
    flow_multiplier = request.flow_multiplier if request is not None else 1.0
    seed = request.seed if request is not None else 42
    requested_steps = (
        int(request.steps)
        if request is not None and request.steps is not None
        else 36000
    )
    run_dir = tmp_path / resolved_run_id
    run_dir.mkdir()
    artifacts = RunArtifacts(
        run_dir=run_dir,
        intersection_id=intersection_id,
        algorithm=algorithm,
        flow_multiplier=flow_multiplier,
        seed=seed,
        run_id=run_dir.name,
    )
    source_hashes = {"net": "b" * 64, "sumocfg": "c" * 64}
    requested_seconds = requested_steps * step_length
    writer = EvidenceWriter(run_dir)
    writer.begin(RunManifest(
        run_id=artifacts.run_id,
        code_commit="a" * 40,
        scene_manifest_sha256=canonical_mapping_sha256(source_hashes),
        algorithm=algorithm,
        parameters=(dict(request.algorithm_params) if request is not None else {}),
        flow_multiplier=flow_multiplier,
        seed=seed,
        duration_seconds=requested_seconds,
        warmup_seconds=0.0,
        derived_steps=requested_steps,
        sumo_version="1.27.1",
        python_version="3.12.13",
        prediction_enabled=False,
        scene_id=intersection_id,
        scene_source_sha256=source_hashes,
        step_length=step_length,
        requested_seconds=requested_seconds,
        request_dimensions={
            "algorithm_params": (
                dict(request.algorithm_params) if request is not None else {}
            ),
            "requested_steps": (
                requested_steps
                if request is None
                else int(request.steps)
                if request.steps is not None
                else None
            ),
            "steps_origin": (
                request.steps_origin if request is not None else "explicit"
            ),
            "duration_seconds": (
                request.duration_seconds
                if request is not None
                else requested_seconds
            ),
            "warmup_seconds": (
                request.warmup_seconds if request is not None else 0.0
            ),
            "step_length_override": (
                request.step_length_override if request is not None else None
            ),
            "variant": (
                asdict(request.variant)
                if request is not None
                else asdict(VariantSpec())
            ),
            "disturbance": (
                asdict(request.disturbance)
                if request is not None and request.disturbance is not None
                else None
            ),
            "edge_delay_steps": (
                request.edge_delay_steps if request is not None else 0
            ),
            "edge_directions": (
                list(request.edge_directions) if request is not None else []
            ),
        },
    ))
    artifacts.metrics.write_text(
        "step,timestamp,avg_queue_length,max_queue_length\n0,0,1,2\n",
        encoding="utf-8",
    )
    artifacts.step_log.write_text(
        "step,timestamp,current_phase\n0,0,0\n",
        encoding="utf-8",
    )
    with artifacts.events.open("w", newline="", encoding="utf-8") as output:
        csv.DictWriter(output, fieldnames=list(EVENT_FIELDS)).writeheader()
    artifacts.tripinfo.write_text(
        '<tripinfos><tripinfo id="v0" depart="0" arrival="1" duration="1" '
        'timeLoss="0" waitingCount="0"><emissions fuel_abs="1" '
        'CO2_abs="1000"/></tripinfo></tripinfos>',
        encoding="utf-8",
    )
    artifacts.stats.write_text(
        f'<summary><step time="{final_time:.2f}"/></summary>',
        encoding="utf-8",
    )
    artifacts.trajectory.write_text("<fcd-export/>", encoding="utf-8")
    artifacts.collisions.write_text("<collisions/>", encoding="utf-8")
    summary = MetricSummary.from_raw_outputs(run_dir, warmup_seconds=0.0)
    writer.finalize(RunStatus.COMPLETED, summary)
    artifacts.write_status("queued", "")
    artifacts.write_status("starting", "")
    artifacts.write_status("running", "")
    artifacts.write_metadata(
        "completed",
        "",
        list(run_dir.iterdir()),
        started_at="2026-08-22T00:00:00+00:00",
        ended_at="2026-08-22T01:00:00+00:00",
        sumo_version="1.27.1",
        requested_steps=requested_steps,
        requested_seconds=requested_seconds,
        warmup_seconds=0.0,
        final_simulation_time=final_time,
        step_length=step_length,
        configured_end_time=configured_end_time,
    )
    writer.seal()
    return run_dir


def test_is_complete_rejects_short_native_sumo_run(tmp_path):
    request = build_pdf_matrix(tmp_path, steps=36000, intersections=("1",))[0]
    run_dir = _write_completed_matrix_run(tmp_path, final_time=3598.0)

    assert is_complete(run_dir, request) is False


def test_is_complete_accepts_full_native_sumo_run(tmp_path):
    request = build_pdf_matrix(tmp_path, steps=36000, intersections=("1",))[0]
    run_dir = _write_completed_matrix_run(tmp_path, final_time=3599.9)

    assert is_complete(run_dir, request) is True


def test_is_complete_accepts_full_seconds_first_formal_run(tmp_path):
    """Catch a formal request being rejected merely because steps is None."""
    request = RunRequest(
        "1",
        "fixed_time",
        duration_seconds=3600,
        warmup_seconds=600,
    )
    run_dir = _write_completed_matrix_run(
        tmp_path,
        final_time=3599.9,
        request=request,
    )

    assert is_complete(run_dir, request) is True


def test_is_complete_rejects_legacy_matrix_metadata(tmp_path):
    request = build_pdf_matrix(tmp_path, steps=36000, intersections=("1",))[0]
    run_dir = _write_completed_matrix_run(tmp_path, final_time=3599.9)
    metadata_path = run_dir / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    for field in (
        "requested_steps",
        "final_simulation_time",
        "step_length",
        "configured_end_time",
    ):
        metadata.pop(field)
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assert is_complete(run_dir, request) is False


def test_is_complete_caps_requested_steps_at_configured_end(tmp_path):
    request = build_pdf_matrix(tmp_path, steps=36000, intersections=("1",))[0]
    run_dir = _write_completed_matrix_run(
        tmp_path,
        final_time=3599.0,
        step_length=1.0,
        configured_end_time=3600.0,
        request=request,
    )

    assert is_complete(run_dir, request) is True


def test_is_complete_rejects_non_finite_step_length(tmp_path):
    request = build_pdf_matrix(tmp_path, steps=36000, intersections=("1",))[0]
    run_dir = _write_completed_matrix_run(
        tmp_path,
        final_time=3599.9,
    )
    metadata_path = run_dir / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["step_length"] = float("nan")
    metadata["final_simulation_time"] = None
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assert is_complete(run_dir, request) is False


def test_is_complete_rejects_non_finite_native_time(tmp_path):
    request = build_pdf_matrix(tmp_path, steps=36000, intersections=("1",))[0]
    run_dir = _write_completed_matrix_run(tmp_path, final_time=3599.9)
    metadata_path = run_dir / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["final_simulation_time"] = None
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    (run_dir / "stats.xml").write_text(
        '<summary><step time="nan"/></summary>',
        encoding="utf-8",
    )

    assert is_complete(run_dir, request) is False


def test_is_complete_rejects_metadata_for_a_different_request(tmp_path):
    request = build_pdf_matrix(tmp_path, steps=36000, intersections=("1",))[0]
    run_dir = _write_completed_matrix_run(tmp_path, final_time=3599.9)
    metadata_path = run_dir / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["seed"] = 123
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    assert is_complete(run_dir, request) is False


def test_is_complete_rejects_evidence_for_different_algorithm_parameters(tmp_path):
    recorded_request = RunRequest(
        "1",
        "capacity_aware_maxpressure",
        steps=100,
        algorithm_params={
            "overflow_occupancy_threshold": 0.95,
            "prediction_weight": 0.15,
            "base_green": 45.0,
        },
    )
    current_request = RunRequest(
        "1",
        "capacity_aware_maxpressure",
        steps=100,
        algorithm_params={
            "overflow_occupancy_threshold": 0.85,
            "prediction_weight": 0.0,
            "base_green": 25.0,
        },
    )
    run_dir = _write_completed_matrix_run(
        tmp_path,
        final_time=10.0,
        request=recorded_request,
    )

    assert EvidenceReader.validate(run_dir) == []
    assert is_complete(run_dir, current_request) is False


def test_is_complete_rejects_evidence_for_different_step_override(tmp_path):
    recorded_request = RunRequest(
        "1",
        "fixed_time",
        steps=100,
        step_length_override=0.2,
    )
    current_request = RunRequest(
        "1",
        "fixed_time",
        steps=100,
        step_length_override=0.1,
    )
    run_dir = _write_completed_matrix_run(
        tmp_path,
        final_time=20.0,
        step_length=0.2,
        request=recorded_request,
    )

    assert EvidenceReader.validate(run_dir) == []
    assert is_complete(run_dir, current_request) is False


@pytest.mark.parametrize(
    "request_overrides",
    [
        {"variant": VariantSpec(signal_duration_scale=1.1)},
        {
            "disturbance": DisturbanceSpec(
                "construction",
                begin_seconds=100.0,
                end_seconds=200.0,
                target="lane-1",
                intensity=0.5,
            )
        },
        {"edge_delay_steps": 2},
        {"edge_directions": ("north",)},
    ],
)
def test_is_complete_rejects_different_execution_dimensions(
    tmp_path,
    request_overrides,
):
    recorded_request = RunRequest("1", "fixed_time", steps=100)
    current_request = RunRequest(
        "1",
        "fixed_time",
        steps=100,
        **request_overrides,
    )
    run_dir = _write_completed_matrix_run(
        tmp_path,
        final_time=10.0,
        request=recorded_request,
    )

    assert EvidenceReader.validate(run_dir) == []
    assert is_complete(run_dir, current_request) is False


class _FakeService:
    def __init__(self, root):
        self.root = root
        self.requests = []

    def run_sync(self, request):
        self.requests.append(request)
        self.root.mkdir(parents=True, exist_ok=True)
        step_length = request.step_length_override or 0.1
        requested_steps = request.steps or 1
        run_dir = _write_completed_matrix_run(
            self.root,
            final_time=float(requested_steps) * step_length,
            step_length=step_length,
            request=request,
            run_id=f"run-{len(self.requests)}",
        )
        return RunResult(
            run_id=run_dir.name,
            status=RunStatus.COMPLETED,
            reason="",
            run_dir=run_dir,
            summary=json.loads((run_dir / "summary.json").read_text(encoding="utf-8")),
        )


class _CompletedMatrixService:
    def __init__(self, root):
        self.root = Path(root)
        self.requests = []

    def run_sync(self, request):
        self.requests.append(request)
        parent = (
            self.root
            / f"i{request.intersection_id}"
            / request.algorithm
            / f"x{request.flow_multiplier:g}"
            / f"s{request.seed}"
        )
        parent.mkdir(parents=True, exist_ok=True)
        step_length = 1.0
        run_dir = _write_completed_matrix_run(
            parent,
            final_time=float(request.steps) * step_length,
            step_length=step_length,
            request=request,
            run_id=f"smoke-{len(self.requests)}",
        )
        return RunResult(
            run_id=run_dir.name,
            status=RunStatus.COMPLETED,
            reason="",
            run_dir=run_dir,
            summary=json.loads(
                (run_dir / "summary.json").read_text(encoding="utf-8")
            ),
            algorithm=request.algorithm,
        )


class _InvalidLiveResultService:
    def __init__(self, root):
        self.root = root

    def run_sync(self, request):
        run_dir = self.root / "unverified-live-result"
        run_dir.mkdir(parents=True, exist_ok=True)
        return RunResult(
            run_id=run_dir.name,
            status=RunStatus.COMPLETED,
            reason="",
            run_dir=run_dir,
            summary={"metrics": {"throughput": 999}},
        )


class _InvalidAtCallService(_FakeService):
    def __init__(self, root, invalid_call):
        super().__init__(root)
        self.invalid_call = invalid_call

    def run_sync(self, request):
        result = super().run_sync(request)
        if len(self.requests) == self.invalid_call:
            (result.run_dir / "hashes.json").unlink()
        return result


class _SpoofedSummaryService(_FakeService):
    def run_sync(self, request):
        return replace(
            super().run_sync(request),
            summary={"metrics": {"throughput": 999999}},
        )


class _MismatchedLiveResultService:
    def __init__(self, root):
        self.root = root
        self.calls = 0

    def run_sync(self, request):
        self.calls += 1
        self.root.mkdir(parents=True, exist_ok=True)
        run_dir = _write_completed_matrix_run(
            self.root,
            final_time=3600.0 + self.calls,
        )
        return RunResult(
            run_id=run_dir.name,
            status=RunStatus.COMPLETED,
            reason="",
            run_dir=run_dir,
            summary=json.loads((run_dir / "summary.json").read_text(encoding="utf-8")),
        )


def test_matrix_rejects_unvalidated_live_result_before_writing_matrix(tmp_path):
    service = _InvalidLiveResultService(tmp_path / "runs")

    with pytest.raises(ValueError, match="strict evidence"):
        run_pdf_matrix(
            tmp_path,
            steps=1,
            resume=False,
            intersections=("1",),
            run_service=service,
        )

    assert not (tmp_path / "matrix.csv").exists()


def test_matrix_rejects_valid_live_evidence_for_a_different_request(tmp_path):
    service = _MismatchedLiveResultService(tmp_path / "runs")

    with pytest.raises(ValueError, match="strict evidence"):
        run_pdf_matrix(
            tmp_path,
            steps=1,
            resume=False,
            intersections=("11",),
            run_service=service,
        )

    assert service.calls == 1
    assert not (tmp_path / "matrix.csv").exists()


def test_tuning_metrics_rejects_completed_result_without_strict_evidence(tmp_path):
    run_dir = tmp_path / "unverified-result"
    run_dir.mkdir()
    result = RunResult(
        run_id="unverified-result",
        status=RunStatus.COMPLETED,
        reason="",
        run_dir=run_dir,
        summary={"metrics": {"throughput": 999}},
    )

    assert _metrics(result) is None


def test_tuning_metrics_loads_canonical_disk_summary_not_in_memory_payload(tmp_path):
    request = RunRequest("1", "fixed_time", steps=10)
    service = _FakeService(tmp_path / "runs")
    canonical = service.run_sync(request)
    spoofed = replace(
        canonical,
        summary={"metrics": {"throughput": 999999}},
    )

    assert _metrics(spoofed)["throughput"] == 1


@pytest.mark.parametrize("invalid_call", [1, 4])
def test_tuning_fails_closed_on_any_invalid_calibration_evidence(
    tmp_path,
    invalid_call,
):
    service = _InvalidAtCallService(tmp_path / "runs", invalid_call)
    (tmp_path / "selected_params.json").write_text("stale", encoding="utf-8")
    (tmp_path / "holdout_summary.json").write_text("stale", encoding="utf-8")

    with pytest.raises(ValueError, match="calibration evidence"):
        tune_ca_mp(tmp_path, steps=10, run_service=service)

    assert not (tmp_path / "selected_params.json").exists()
    assert not (tmp_path / "holdout_summary.json").exists()


def test_tuning_fails_closed_on_non_finite_calibration_score(tmp_path, monkeypatch):
    from experiments import tuning

    service = _FakeService(tmp_path / "runs")
    monkeypatch.setattr(
        tuning,
        "_relative_composite_metrics",
        lambda *args: float("inf"),
    )

    with pytest.raises(ValueError, match="finite calibration score"):
        tune_ca_mp(tmp_path, steps=10, run_service=service)

    assert not (tmp_path / "selected_params.json").exists()
    assert not (tmp_path / "holdout_summary.json").exists()


def test_tuning_fails_closed_on_invalid_holdout_evidence(tmp_path):
    # 3 calibration baselines + 18 candidates * 3 intersections = 57.
    service = _InvalidAtCallService(tmp_path / "runs", invalid_call=58)

    with pytest.raises(ValueError, match="holdout evidence"):
        tune_ca_mp(tmp_path, steps=10, run_service=service)

    assert not (tmp_path / "selected_params.json").exists()
    assert not (tmp_path / "holdout_summary.json").exists()


def test_tuning_fails_closed_on_non_finite_holdout_score(tmp_path, monkeypatch):
    from experiments import tuning

    service = _FakeService(tmp_path / "runs")
    calls = 0

    def calibration_then_invalid_holdout(*args):
        nonlocal calls
        calls += 1
        return 0.8 if calls <= 54 else float("inf")

    monkeypatch.setattr(
        tuning,
        "_relative_composite_metrics",
        calibration_then_invalid_holdout,
    )

    with pytest.raises(ValueError, match="finite holdout score"):
        tune_ca_mp(tmp_path, steps=10, run_service=service)

    assert not (tmp_path / "selected_params.json").exists()
    assert not (tmp_path / "holdout_summary.json").exists()


def test_tuning_does_not_publish_selection_when_final_commit_fails(
    tmp_path,
    monkeypatch,
):
    service = _FakeService(tmp_path / "runs")
    original_replace = Path.replace

    def fail_selection_commit(path, target):
        if Path(target).name == "selected_params.json":
            raise OSError("selection commit unavailable")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_selection_commit)

    with pytest.raises(OSError, match="selection commit unavailable"):
        tune_ca_mp(tmp_path, steps=10, run_service=service)

    assert not (tmp_path / "selected_params.json").exists()
    assert not (tmp_path / "holdout_summary.json").exists()


def test_matrix_uses_canonical_disk_summary_for_live_results(tmp_path):
    service = _SpoofedSummaryService(tmp_path / "runs")

    results = run_pdf_matrix(
        tmp_path,
        steps=10,
        resume=False,
        intersections=("1",),
        run_service=service,
    )

    assert results[0].summary["metrics"]["throughput"] == 1
    rows = list(csv.DictReader((tmp_path / "matrix.csv").open(encoding="utf-8")))
    assert rows[0]["throughput"] == "1"


def test_smoke_matrix_publishes_and_resumes_exact_100_step_evidence(tmp_path):
    """Catch explicit smoke identity loss in artifacts or completed resume."""
    from experiments.matrix import load_sealed_matrix_rows, run_matrix
    from scripts.run_pdf_matrix import build_profile_matrix, parse_matrix_args

    specs = build_profile_matrix(parse_matrix_args([
        "--profile", "smoke", "--output-root", str(tmp_path)
    ]))
    first_service = _CompletedMatrixService(tmp_path / "runs")

    first = run_matrix(
        specs,
        tmp_path,
        resume=False,
        run_service=first_service,
    )

    assert len(first_service.requests) == 1
    assert first_service.requests[0].steps == 100
    assert first_service.requests[0].steps_origin == "explicit"
    manifest_path = tmp_path / "matrix_manifest.json"
    results_path = tmp_path / "matrix_results.json"
    csv_path = tmp_path / "matrix.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result_row = json.loads(results_path.read_text(encoding="utf-8"))["rows"][0]
    csv_row = next(csv.DictReader(csv_path.open(encoding="utf-8")))
    assert manifest["specs"][0]["request"]["steps"] == 100
    assert manifest["specs"][0]["request"]["steps_origin"] == "explicit"
    assert result_row["steps"] == 100
    assert result_row["steps_origin"] == "explicit"
    assert csv_row["steps"] == "100"
    assert csv_row["steps_origin"] == "explicit"
    sealed_rows = load_sealed_matrix_rows(csv_path, specs)
    assert sealed_rows[0]["steps"] == "100"
    assert sealed_rows[0]["steps_origin"] == "explicit"

    immutable_paths = [manifest_path, results_path, csv_path]
    run_dir = first.entries[0].run_dir
    run_manifest = json.loads(
        (run_dir / "manifest.json").read_text(encoding="utf-8")
    )
    run_metadata = json.loads(
        (run_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    assert run_manifest["derived_steps"] == 100
    assert run_manifest["requested_seconds"] == 100.0
    assert run_manifest["warmup_seconds"] == 0.0
    assert run_metadata["requested_steps"] == 100
    assert run_metadata["requested_seconds"] == 100.0
    assert run_metadata["warmup_seconds"] == 0.0
    immutable_paths.extend(path for path in run_dir.rglob("*") if path.is_file())
    before = {path: path.read_bytes() for path in immutable_paths}
    resume_service = _CompletedMatrixService(tmp_path / "runs")

    resumed = run_matrix(
        specs,
        tmp_path,
        resume=True,
        run_service=resume_service,
    )

    assert resume_service.requests == []
    assert resumed.skipped == 1
    assert resumed.retried == 0
    assert resumed.entries == first.entries
    assert {path: path.read_bytes() for path in immutable_paths} == before


def test_tuning_writes_all_candidates_selected_params_and_holdout(tmp_path):
    service = _FakeService(tmp_path / "runs")

    selected = tune_ca_mp(tmp_path, steps=10, run_service=service)

    assert selected == {
        "overflow_occupancy_threshold": 0.85,
        "prediction_weight": 0.0,
        "base_green": 25.0,
    }
    rows = list(csv.DictReader(
        (tmp_path / "tuning_results.csv").open(encoding="utf-8")
    ))
    assert len(rows) == 18
    assert json.loads(
        (tmp_path / "selected_params.json").read_text(encoding="utf-8")
    )["parameters"] == selected
    holdout = json.loads(
        (tmp_path / "holdout_summary.json").read_text(encoding="utf-8")
    )
    assert holdout["seeds"] == [43, 44]
    calibration_requests = [
        request for request in service.requests if request.seed == 42
    ]
    holdout_requests = [
        request for request in service.requests if request.seed in (43, 44)
    ]
    assert calibration_requests
    assert holdout_requests
    assert all(request.seed == 42 for request in calibration_requests)
    assert all(request.seed in (43, 44) for request in holdout_requests)
    assert {request.algorithm for request in service.requests} == {
        "fixed_time",
        "capacity_aware_maxpressure",
    }


def test_resumed_matrix_result_keeps_the_canonical_algorithm(tmp_path):
    request = build_pdf_matrix(
        tmp_path,
        steps=100,
        intersections=("1",),
    )[-1]
    run_id = "resume-run"
    run_dir = _run_dir(request, run_id)
    run_dir.parent.mkdir(parents=True)
    _write_completed_matrix_run(
        run_dir.parent,
        final_time=10.0,
        request=request,
        run_id=run_id,
    )

    result = _load_result(request, run_id)

    assert result.algorithm == "capacity_aware_maxpressure"


def test_quick_matrix_writes_all_54_explicit_rows(tmp_path):
    service = _FakeService(tmp_path / "runs")

    results = run_pdf_matrix(
        tmp_path,
        steps=100,
        resume=False,
        intersections=("1", "11", "16"),
        run_service=service,
    )

    rows = list(csv.DictReader(
        (tmp_path / "matrix.csv").open(encoding="utf-8")
    ))
    assert len(results) == 54
    assert len(rows) == 54
    assert len(service.requests) == 54
    assert {row["status"] for row in rows} == {"completed"}
    assert len(json.loads(
        (tmp_path / "matrix_state.json").read_text(encoding="utf-8")
    )) == 54


def test_matrix_script_help_runs_directly():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "scripts/run_pdf_matrix.py", "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
