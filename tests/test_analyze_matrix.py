"""Tests for strict analysis of the frozen 540-run experiment matrix."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.analyze_matrix import analyze_matrix


METRICS = (
    "avg_travel_time",
    "avg_delay",
    "avg_queue_length",
    "throughput",
    "total_stops",
    "fuel_consumption",
)
ALGORITHMS = (
    "fixed_time",
    "classic_maxpressure",
    "capacity_aware_maxpressure",
)


def write_complete_matrix_fixture(tmp_path: Path, monkeypatch) -> Path:
    """Write a complete formal shape backed by controlled fake sealed summaries."""
    from experiments import matrix as matrix_module
    from experiments.matrix import FormalMatrix, _new_manifest

    specs = FormalMatrix.all()
    rows = []
    summaries = {}
    factors = {
        "fixed_time": (100.0, 50.0, 10.0, 100.0, 8.0, 1000.0),
        "classic_maxpressure": (90.0, 45.0, 9.0, 105.0, 7.0, 900.0),
        "capacity_aware_maxpressure": (80.0, 40.0, 8.0, 110.0, 6.0, 800.0),
    }
    manifest = _new_manifest(specs)
    for index, spec in enumerate(specs):
        run_id = f"run-{index:03d}"
        run_dir = (
            tmp_path
            / "runs"
            / f"i{spec.scene_id}"
            / spec.algorithm
            / f"x{spec.flow_multiplier:g}"
            / f"s{spec.seed}"
            / run_id
        )
        run_dir.mkdir(parents=True)
        (run_dir / "status.json").write_text(
            json.dumps({"run_id": run_id, "status": "completed", "reason": ""}),
            encoding="utf-8",
        )
        disturbance = spec.disturbance
        scale = (
            1.0 + 0.01 * int(spec.scene_id)
            if disturbance is not None
            else 1.0
            + 0.01 * int(spec.scene_id)
            + 0.001 * spec.flow_multiplier
            + 0.000001 * spec.seed
        )
        metrics = {
            metric: value * scale
            for metric, value in zip(METRICS, factors[spec.algorithm])
        }
        metrics.update({
            "collision_count": 0,
            "red_light_count": 0,
            "illegal_transition_count": 0,
            "harsh_braking_count": 5 if disturbance else 2,
            "teleport_count": 4 if disturbance else 1,
            "potential_conflict_count": 6 if disturbance else 3,
        })
        row = {
            "run_key": spec.run_key,
            "scene_id": spec.scene_id,
            "intersection_id": spec.intersection_id,
            "algorithm": spec.algorithm,
            "flow_multiplier": spec.flow_multiplier,
            "seed": spec.seed,
            "matrix_kind": spec.matrix_kind,
            "disturbance_kind": disturbance.kind if disturbance else "",
            "disturbance_begin_seconds": (
                disturbance.begin_seconds if disturbance else ""
            ),
            "disturbance_end_seconds": disturbance.end_seconds if disturbance else "",
            "disturbance_target": disturbance.target if disturbance else "",
            "disturbance_intensity": disturbance.intensity if disturbance else "",
            "duration_seconds": spec.duration_seconds,
            "warmup_seconds": spec.warmup_seconds,
            "steps": "",
            "steps_origin": "none",
            "algorithm_params": json.dumps(
                spec.algorithm_params, sort_keys=True, separators=(",", ":")
            ),
            "run_id": run_id,
            "status": "completed",
            "reason": "",
            "run_dir": str(run_dir.relative_to(tmp_path)),
            **metrics,
        }
        rows.append(row)
        summaries[str(run_dir.resolve())] = {"run_id": run_id, "metrics": metrics}
        manifest["attempt_chains"][spec.run_key].append({
            "run_id": run_id,
            "run_dir": str(run_dir.resolve()),
            "status": "completed",
            "reason": "",
            "parent_failure": None,
        })
    assert len(rows) == 540
    (tmp_path / "matrix_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    path = tmp_path / "matrix.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    monkeypatch.setattr(matrix_module, "_strict_is_complete", lambda *args: True)
    monkeypatch.setattr(
        matrix_module.EvidenceReader,
        "load_summary",
        staticmethod(lambda run_dir: summaries[str(Path(run_dir).resolve())]),
    )
    return path


def test_analysis_accepts_only_complete_frozen_matrix_and_selects_candidate(
    tmp_path, monkeypatch
):
    """Catch legacy partial analysis and reversed paired direction."""
    matrix = write_complete_matrix_fixture(tmp_path, monkeypatch)

    outputs = analyze_matrix(matrix, tmp_path / "stats")

    paired = pd.read_csv(outputs["paired_tests"])
    assert set(paired["baseline"]) == {"fixed_time"}
    assert set(paired["candidate"]) == {
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    }
    assert set(paired["n_pairs"]) == {120}
    assert (paired["mean_difference"] < 0).all()
    selection = pd.read_json(outputs["selection"], typ="series")
    assert selection["algorithm"] == "capacity_aware_maxpressure"
    assert bool(selection["improvement_claim"]) is True
    descriptive = pd.read_csv(outputs["descriptive_stats"])
    assert set(descriptive["matrix_kind"]) == {"normal"}
    assert set(descriptive["n"]) == {120}
    resilience = pd.read_csv(outputs["disturbance_resilience"])
    assert set(resilience["matrix_kind"]) == {"disturbance"}
    assert set(resilience["disturbance_kind"]) == {
        "construction",
        "event_demand",
        "vehicle_failure",
    }
    assert set(resilience["n"]) == {20}


def test_analysis_rejects_duplicate_case(tmp_path, monkeypatch):
    """Catch duplicate run keys or design units inflating the sample."""
    matrix = write_complete_matrix_fixture(tmp_path, monkeypatch)
    frame = pd.read_csv(matrix)
    pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_csv(matrix, index=False)

    with pytest.raises(ValueError, match="duplicate"):
        analyze_matrix(matrix, tmp_path / "stats")


def test_analysis_rejects_unique_but_unexpected_run_key(tmp_path, monkeypatch):
    """Catch a 540-row matrix that substitutes an unplanned experiment."""
    matrix = write_complete_matrix_fixture(tmp_path, monkeypatch)
    frame = pd.read_csv(matrix)
    frame.loc[0, "run_key"] = "unexpected-but-unique"
    frame.to_csv(matrix, index=False)

    with pytest.raises(ValueError, match="expected run keys"):
        analyze_matrix(matrix, tmp_path / "stats")


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda frame: frame.iloc[:-1], "exactly 540"),
        (
            lambda frame: frame.assign(
                flow_multiplier=frame["flow_multiplier"].replace(1.25, 1.5)
            ),
            "flow multipliers",
        ),
        (
            lambda frame: frame.assign(
                algorithm=frame["algorithm"].replace("classic_maxpressure", "actuated")
            ),
            "algorithms",
        ),
        (lambda frame: frame.assign(status="failed"), "non-completed"),
    ],
)
def test_analysis_rejects_legacy_or_incomplete_schema(
    tmp_path, monkeypatch, mutation, match
):
    """Catch silent normalization of old algorithms, loads, or incomplete evidence."""
    matrix = write_complete_matrix_fixture(tmp_path, monkeypatch)
    mutation(pd.read_csv(matrix)).to_csv(matrix, index=False)

    with pytest.raises(ValueError, match=match):
        analyze_matrix(matrix, tmp_path / "stats")


@pytest.mark.parametrize(
    "mutation,match",
    (
        (
            lambda frame: frame.assign(
                run_key=frame["run_key"].iloc[[1, 0] + list(range(2, len(frame)))].to_numpy()
            ),
            "identity",
        ),
        (
            lambda frame: frame.assign(
                run_id=frame["run_id"].iloc[[1, 0] + list(range(2, len(frame)))].to_numpy()
            ),
            "attempt",
        ),
        (
            lambda frame: frame.assign(
                run_dir=frame["run_dir"].iloc[[1, 0] + list(range(2, len(frame)))].to_numpy()
            ),
            "attempt",
        ),
        (
            lambda frame: frame.assign(
                avg_travel_time=frame["avg_travel_time"] + 1.0
            ),
            "sealed summary",
        ),
        (
            lambda frame: frame.assign(collision_count=1),
            "sealed summary",
        ),
    ),
)
def test_analysis_rejects_swapped_identity_or_forged_summary(
    tmp_path, monkeypatch, mutation, match
):
    """Catch key-set-only validation and CSV-controlled statistical values."""
    matrix = write_complete_matrix_fixture(tmp_path, monkeypatch)
    mutation(pd.read_csv(matrix, keep_default_na=False)).to_csv(matrix, index=False)

    with pytest.raises(ValueError, match=match):
        analyze_matrix(matrix, tmp_path / "stats")


def test_analysis_rejects_relative_run_directory_outside_matrix_root(
    tmp_path, monkeypatch
):
    """Catch relative evidence paths escaping the controlled matrix root."""
    matrix = write_complete_matrix_fixture(tmp_path, monkeypatch)
    frame = pd.read_csv(matrix, keep_default_na=False)
    frame.loc[0, "run_dir"] = "../outside/run-000"
    frame.to_csv(matrix, index=False)

    with pytest.raises(ValueError, match="outside"):
        analyze_matrix(matrix, tmp_path / "stats")


def test_analysis_rejects_parent_segments_even_when_path_resolves_inside(
    tmp_path, monkeypatch
):
    """Catch normalization hiding an explicitly uncontrolled parent traversal."""
    matrix = write_complete_matrix_fixture(tmp_path, monkeypatch)
    with matrix.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
        fieldnames = list(rows[0])
    rows[0]["run_dir"] = f"runs/../{rows[0]['run_dir']}"
    with matrix.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="parent traversal"):
        analyze_matrix(matrix, tmp_path / "stats")
