"""Analyze only the complete frozen 540-run judge-facing matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.matrix import (  # noqa: E402
    FORMAL_ALGORITHMS,
    FORMAL_FLOWS,
    FORMAL_SEEDS,
    FormalMatrix,
)
from experiments.statistics import select_default  # noqa: E402


METRICS = (
    "avg_travel_time",
    "avg_delay",
    "avg_queue_length",
    "throughput",
    "total_stops",
    "fuel_consumption",
)
SAFETY_COLUMNS = (
    "collision_count",
    "red_light_count",
    "illegal_transition_count",
    "harsh_braking_count",
    "teleport_count",
    "potential_conflict_count",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _validate_frozen_frame(frame: pd.DataFrame) -> None:
    required = {
        "run_key",
        "scene_id",
        "intersection_id",
        "algorithm",
        "flow_multiplier",
        "seed",
        "matrix_kind",
        "disturbance_kind",
        "status",
        *METRICS,
        *SAFETY_COLUMNS,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Matrix schema missing columns: {missing}")
    if frame["run_key"].duplicated(keep=False).any():
        raise ValueError("Matrix contains duplicate run key")
    if len(frame) != 540:
        raise ValueError(f"Frozen matrix must contain exactly 540 rows, got {len(frame)}")
    actual_run_keys = set(frame["run_key"])
    expected_run_keys = {spec.run_key for spec in FormalMatrix.all()}
    if actual_run_keys != expected_run_keys:
        raise ValueError(
            "Matrix does not contain the 540 expected run keys: "
            f"missing={len(expected_run_keys - actual_run_keys)} "
            f"unexpected={len(actual_run_keys - expected_run_keys)}"
        )
    incomplete = frame[frame["status"] != "completed"]
    if not incomplete.empty:
        raise ValueError(
            f"Matrix contains {len(incomplete)} non-completed row(s)"
        )
    algorithms = set(frame["algorithm"])
    if algorithms != set(FORMAL_ALGORITHMS):
        raise ValueError(
            f"Frozen matrix algorithms must be {list(FORMAL_ALGORITHMS)}, "
            f"got {sorted(algorithms)}"
        )
    flows = {float(value) for value in frame["flow_multiplier"]}
    if flows != set(FORMAL_FLOWS):
        raise ValueError(
            f"Frozen matrix flow multipliers must be {list(FORMAL_FLOWS)}, "
            f"got {sorted(flows)}"
        )
    seeds = {int(value) for value in frame["seed"]}
    if seeds != set(FORMAL_SEEDS):
        raise ValueError(
            f"Frozen matrix seeds must be {list(FORMAL_SEEDS)}, got {sorted(seeds)}"
        )

    normal = frame[frame["matrix_kind"] == "normal"]
    disturbance = frame[frame["matrix_kind"] == "disturbance"]
    if len(normal) != 360 or len(disturbance) != 180:
        raise ValueError("Frozen matrix must contain 360 normal and 180 disturbance rows")
    if normal.duplicated(
        ["scene_id", "algorithm", "flow_multiplier", "seed"], keep=False
    ).any():
        raise ValueError("Matrix contains duplicate normal case")
    if disturbance.duplicated(
        ["scene_id", "algorithm", "disturbance_kind"], keep=False
    ).any():
        raise ValueError("Matrix contains duplicate disturbance case")
    if set(disturbance["disturbance_kind"]) != {
        "construction",
        "event_demand",
        "vehicle_failure",
    }:
        raise ValueError("Frozen matrix disturbance kinds do not match schema")
    if set(float(value) for value in disturbance["flow_multiplier"]) != {1.0}:
        raise ValueError("Frozen disturbance matrix flow multiplier must be 1.0")
    if set(int(value) for value in disturbance["seed"]) != {42}:
        raise ValueError("Frozen disturbance matrix seed must be 42")

    for column in METRICS:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"Matrix metric {column} must be complete and finite")


def analyze_matrix(matrix_csv: Path, output_dir: Path) -> dict[str, Path]:
    """Validate, pair, select, and publish analysis artifacts."""
    matrix_csv = Path(matrix_csv)
    output_dir = Path(output_dir)
    frame = pd.read_csv(matrix_csv)
    _validate_frozen_frame(frame)

    desc_rows: list[dict[str, Any]] = []
    for algorithm in FORMAL_ALGORITHMS:
        subset = frame[frame["algorithm"] == algorithm]
        for metric in METRICS:
            values = subset[metric]
            desc_rows.append({
                "algorithm": algorithm,
                "metric": metric,
                "n": int(values.count()),
                "mean": float(values.mean()),
                "std": float(values.std(ddof=1)),
                "min": float(values.min()),
                "max": float(values.max()),
            })

    output_dir.mkdir(parents=True, exist_ok=True)
    desc_path = output_dir / "descriptive_stats.csv"
    pd.DataFrame(desc_rows).to_csv(desc_path, index=False)

    selection = select_default(
        frame,
        candidates=("classic_maxpressure", "capacity_aware_maxpressure"),
        baseline="fixed_time",
    )
    paired_rows = []
    for result in selection.results:
        paired_rows.append({
            "baseline": result.baseline,
            "candidate": result.candidate,
            "metric": "avg_travel_time",
            "n_pairs": len(result.differences),
            "baseline_mean": float(
                frame[
                    (frame["algorithm"] == result.baseline)
                    & (frame["matrix_kind"] == "normal")
                ]["avg_travel_time"].mean()
            ),
            "candidate_mean": float(
                frame[
                    (frame["algorithm"] == result.candidate)
                    & (frame["matrix_kind"] == "normal")
                ]["avg_travel_time"].mean()
            ),
            "mean_difference": result.mean_difference,
            "relative_change": result.relative_change,
            "cohen_dz": result.cohen_dz,
            "ci_lower": result.confidence_interval[0],
            "ci_upper": result.confidence_interval[1],
            "improved_unit_count": result.improved_unit_count,
            "worst_scene_id": result.worst_unit["scene_id"],
            "worst_flow_multiplier": result.worst_unit["flow_multiplier"],
            "safety_eligible": result.safety_eligible,
            "eligible": result.eligible,
            "flags": ";".join(result.flags),
        })
    paired_path = output_dir / "paired_tests.csv"
    pd.DataFrame(paired_rows).to_csv(paired_path, index=False)

    selection_path = output_dir / "selection.json"
    _write_json(selection_path, {
        "algorithm": selection.algorithm,
        "improvement_claim": selection.improvement_claim,
        "candidates": [result.to_payload() for result in selection.results],
    })

    manifest_path = output_dir / "analysis_manifest.json"
    manifest: dict[str, Any] = {
        "schema": "challenge-cup-formal-matrix-analysis",
        "schema_version": 1,
        "matrix_path": str(matrix_csv.resolve()),
        "matrix_sha256": _sha256(matrix_csv),
        "expected_rows": 540,
        "pair_keys": ["scene_id", "flow_multiplier", "seed"],
        "difference_direction": "candidate_minus_baseline",
        "outputs": {
            "descriptive_stats": {
                "path": str(desc_path.resolve()),
                "sha256": _sha256(desc_path),
            },
            "paired_tests": {
                "path": str(paired_path.resolve()),
                "sha256": _sha256(paired_path),
            },
            "selection": {
                "path": str(selection_path.resolve()),
                "sha256": _sha256(selection_path),
            },
        },
    }
    _write_json(manifest_path, manifest)
    return {
        "descriptive_stats": desc_path,
        "paired_tests": paired_path,
        "selection": selection_path,
        "analysis_manifest": manifest_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    outputs = analyze_matrix(args.matrix, args.output)
    print(f"Wrote {len(outputs)} file(s) to {args.output.resolve()}")


if __name__ == "__main__":
    main()
