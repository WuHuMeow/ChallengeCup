"""Tests for scripts/analyze_matrix.py — paired statistical analysis of the experiment matrix."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.analyze_matrix import analyze_matrix


def write_complete_matrix_fixture(tmp_path: Path) -> Path:
    rows = []
    factors = {
        "fixed_time": (100.0, 50.0, 10.0, 100.0, 8.0, 1000.0),
        "actuated": (90.0, 45.0, 9.0, 105.0, 7.0, 900.0),
        "ca_maxpressure": (80.0, 40.0, 8.0, 110.0, 6.0, 800.0),
    }
    metrics = (
        "avg_travel_time",
        "avg_delay",
        "avg_queue_length",
        "throughput",
        "total_stops",
        "fuel_consumption",
    )
    for intersection in ("1", "2"):
        for flow in (1.0, 1.5):
            for seed in (42, 123, 456):
                for algorithm, values in factors.items():
                    row = {
                        "intersection_id": intersection,
                        "algorithm": algorithm,
                        "flow_multiplier": flow,
                        "seed": seed,
                        "status": "completed",
                    }
                    row.update(dict(zip(metrics, values)))
                    rows.append(row)
    path = tmp_path / "matrix.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def write_matrix_with_duplicate_case(tmp_path: Path) -> Path:
    path = write_complete_matrix_fixture(tmp_path)
    frame = pd.read_csv(path)
    pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_csv(path, index=False)
    return path


def test_analysis_pairs_identical_cases_and_preserves_direction(tmp_path):
    matrix = write_complete_matrix_fixture(tmp_path)
    outputs = analyze_matrix(matrix, tmp_path / "stats")
    paired = pd.read_csv(outputs["paired_tests"])
    assert set(paired["baseline"]) == {"fixed_time", "actuated"}
    assert set(paired["metric"]) == {
        "avg_travel_time",
        "avg_delay",
        "avg_queue_length",
        "throughput",
        "total_stops",
        "fuel_consumption",
    }
    assert set(paired["n_pairs"]) == {12}
    travel = paired.query(
        "baseline == 'fixed_time' and metric == 'avg_travel_time'"
    ).iloc[0]
    assert travel["improvement_percent"] > 0
    throughput = paired.query(
        "baseline == 'fixed_time' and metric == 'throughput'"
    ).iloc[0]
    assert throughput["improvement_percent"] > 0


def test_analysis_rejects_incomplete_or_duplicate_matrix(tmp_path):
    matrix = write_matrix_with_duplicate_case(tmp_path)
    with pytest.raises(ValueError, match="duplicate case"):
        analyze_matrix(matrix, tmp_path / "stats")
