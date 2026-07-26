import csv
import json
import subprocess
import sys
from pathlib import Path

from core.run_models import RunResult, RunStatus
from experiments.tuning import (
    PARAMETER_GRID,
    calibration_seeds,
    holdout_seeds,
    tune_ca_mp,
)
from scripts.run_pdf_matrix import (
    build_pdf_matrix,
    is_complete,
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
        "actuated",
        "ca_maxpressure",
    }
    assert {request.flow_multiplier for request in requests} == {1.0, 1.5}
    assert {request.seed for request in requests} == {42, 123, 456}
    assert all(request.steps == 36000 for request in requests)


def test_tuning_grid_and_seed_split_are_exact():
    assert PARAMETER_GRID == {
        "overflow_occupancy_threshold": (0.85, 0.90, 0.95),
        "prediction_weight": (0.0, 0.15),
        "base_green": (25.0, 35.0, 45.0),
    }
    assert calibration_seeds() == (42,)
    assert holdout_seeds() == (123, 456)


def test_is_complete_requires_every_nonempty_artifact(tmp_path):
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
        "summary.json",
    )
    for name in required:
        (run_dir / name).write_text("x", encoding="utf-8")

    assert is_complete(run_dir) is True
    (run_dir / "summary.json").write_text("", encoding="utf-8")
    assert is_complete(run_dir) is False


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
    assert holdout["seeds"] == [123, 456]
    calibration_requests = [
        request for request in service.requests if request.seed == 42
    ]
    holdout_requests = [
        request for request in service.requests if request.seed in (123, 456)
    ]
    assert calibration_requests
    assert holdout_requests
    assert all(request.seed == 42 for request in calibration_requests)
    assert all(request.seed in (123, 456) for request in holdout_requests)


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
