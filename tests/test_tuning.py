import csv
import json
import subprocess
import sys
from pathlib import Path

from core.run_models import RunRequest, RunResult, RunStatus
from core.types import MetricSummary
from engine.artifacts import RunArtifacts
from engine.events import EVENT_FIELDS
from experiments.evidence import (
    EvidenceWriter,
    RunManifest,
    canonical_mapping_sha256,
)
from experiments.tuning import (
    PARAMETER_GRID,
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
    assert {request.flow_multiplier for request in requests} == {1.0, 1.5}
    assert {request.seed for request in requests} == {42, 123, 456}
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
):
    run_dir = tmp_path / f"run-{final_time}"
    run_dir.mkdir()
    artifacts = RunArtifacts(
        run_dir=run_dir,
        intersection_id="1",
        algorithm="fixed_time",
        flow_multiplier=1.0,
        seed=42,
        run_id=run_dir.name,
    )
    source_hashes = {"net": "b" * 64, "sumocfg": "c" * 64}
    requested_seconds = 36000 * step_length
    writer = EvidenceWriter(run_dir)
    writer.begin(RunManifest(
        run_id=artifacts.run_id,
        code_commit="a" * 40,
        scene_manifest_sha256=canonical_mapping_sha256(source_hashes),
        algorithm="fixed_time",
        parameters={},
        flow_multiplier=1.0,
        seed=42,
        duration_seconds=requested_seconds,
        warmup_seconds=0.0,
        derived_steps=36000,
        sumo_version="1.27.1",
        python_version="3.12.13",
        prediction_enabled=False,
        scene_id="1",
        scene_source_sha256=source_hashes,
        step_length=step_length,
        requested_seconds=requested_seconds,
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
        requested_steps=36000,
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


class _FakeService:
    def __init__(self, root):
        self.root = root
        self.requests = []

    def run_sync(self, request):
        self.requests.append(request)
        run_id = f"run-{len(self.requests)}"
        run_dir = self.root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return RunResult(
            run_id=run_id,
            status=RunStatus.COMPLETED,
            reason="",
            run_dir=run_dir,
            summary={
                "metrics": {
                    "avg_travel_time": 20.0,
                    "avg_queue_length": 2.0,
                    "fuel_consumption": 100.0,
                    "throughput": 50,
                }
            },
        )


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
    run_dir.mkdir(parents=True)
    (run_dir / "run_metadata.json").write_text(
        json.dumps({"status": "completed"}),
        encoding="utf-8",
    )
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")

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


def test_cli_tuning_parameters_are_frozen_into_following_matrix(
    tmp_path,
    monkeypatch,
):
    from scripts import run_pdf_matrix as module

    selected = {
        "overflow_occupancy_threshold": 0.85,
        "prediction_weight": 0.0,
        "base_green": 25.0,
    }
    captured = {}
    monkeypatch.setattr(
        module,
        "tune_ca_mp",
        lambda output_root, steps: selected,
    )
    monkeypatch.setattr(
        module,
        "run_pdf_matrix",
        lambda *args, **kwargs: captured.update(kwargs) or [],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_pdf_matrix.py",
            "--quick",
            "--tune",
            "--output-root",
            str(tmp_path),
        ],
    )

    module.main()

    assert captured["selected_params"] == selected
