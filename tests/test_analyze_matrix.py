"""Tests for strict analysis of the frozen 540-run experiment matrix."""

from __future__ import annotations

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


def write_complete_matrix_fixture(tmp_path: Path) -> Path:
    """Write a literal-shape 360 normal + 180 disturbance result matrix."""
    from experiments.matrix import FormalMatrix

    specs = FormalMatrix.all()
    normal_keys = {
        (spec.scene_id, spec.algorithm, spec.flow_multiplier, spec.seed): spec.run_key
        for spec in specs
        if spec.matrix_kind == "normal"
    }
    disturbance_keys = {
        (spec.scene_id, spec.algorithm, spec.disturbance.kind): spec.run_key
        for spec in specs
        if spec.matrix_kind == "disturbance"
    }
    rows = []
    factors = {
        "fixed_time": (100.0, 50.0, 10.0, 100.0, 8.0, 1000.0),
        "classic_maxpressure": (90.0, 45.0, 9.0, 105.0, 7.0, 900.0),
        "capacity_aware_maxpressure": (80.0, 40.0, 8.0, 110.0, 6.0, 800.0),
    }
    for scene in range(1, 21):
        for flow in (1.0, 1.25):
            for seed in (42, 43, 44):
                scale = 1.0 + 0.01 * scene + 0.001 * flow + 0.000001 * seed
                for algorithm in ALGORITHMS:
                    row = {
                        "run_key": normal_keys[(str(scene), algorithm, flow, seed)],
                        "scene_id": str(scene),
                        "intersection_id": str(scene),
                        "algorithm": algorithm,
                        "flow_multiplier": flow,
                        "seed": seed,
                        "matrix_kind": "normal",
                        "disturbance_kind": "",
                        "status": "completed",
                        "collision_count": 0,
                        "red_light_count": 0,
                        "illegal_transition_count": 0,
                        "harsh_braking_count": 2,
                        "teleport_count": 1,
                        "potential_conflict_count": 3,
                    }
                    row.update({
                        metric: value * scale
                        for metric, value in zip(METRICS, factors[algorithm])
                    })
                    rows.append(row)
    for scene in range(1, 21):
        for algorithm in ALGORITHMS:
            for kind in ("construction", "event_demand", "vehicle_failure"):
                row = {
                    "run_key": disturbance_keys[(str(scene), algorithm, kind)],
                    "scene_id": str(scene),
                    "intersection_id": str(scene),
                    "algorithm": algorithm,
                    "flow_multiplier": 1.0,
                    "seed": 42,
                    "matrix_kind": "disturbance",
                    "disturbance_kind": kind,
                    "status": "completed",
                    "collision_count": 0,
                    "red_light_count": 0,
                    "illegal_transition_count": 0,
                    "harsh_braking_count": 5,
                    "teleport_count": 4,
                    "potential_conflict_count": 6,
                }
                row.update({
                    metric: value * (1.0 + 0.01 * scene)
                    for metric, value in zip(METRICS, factors[algorithm])
                })
                rows.append(row)
    assert len(rows) == 540
    path = tmp_path / "matrix.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_analysis_accepts_only_complete_frozen_matrix_and_selects_candidate(tmp_path):
    """Catch legacy partial analysis and reversed paired direction."""
    matrix = write_complete_matrix_fixture(tmp_path)

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


def test_analysis_rejects_duplicate_case(tmp_path):
    """Catch duplicate run keys or design units inflating the sample."""
    matrix = write_complete_matrix_fixture(tmp_path)
    frame = pd.read_csv(matrix)
    pd.concat([frame, frame.iloc[[0]]], ignore_index=True).to_csv(matrix, index=False)

    with pytest.raises(ValueError, match="duplicate"):
        analyze_matrix(matrix, tmp_path / "stats")


def test_analysis_rejects_unique_but_unexpected_run_key(tmp_path):
    """Catch a 540-row matrix that substitutes an unplanned experiment."""
    matrix = write_complete_matrix_fixture(tmp_path)
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
def test_analysis_rejects_legacy_or_incomplete_schema(tmp_path, mutation, match):
    """Catch silent normalization of old algorithms, loads, or incomplete evidence."""
    matrix = write_complete_matrix_fixture(tmp_path)
    mutation(pd.read_csv(matrix)).to_csv(matrix, index=False)

    with pytest.raises(ValueError, match=match):
        analyze_matrix(matrix, tmp_path / "stats")
