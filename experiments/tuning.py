"""Bounded CA-MP calibration with a strict calibration/holdout split."""

from __future__ import annotations

import csv
import itertools
import json
from pathlib import Path
from statistics import mean

from core.run_models import RunRequest, RunResult, RunStatus
from engine.run_service import RunService


PARAMETER_GRID = {
    "overflow_occupancy_threshold": (0.85, 0.90, 0.95),
    "prediction_weight": (0.0, 0.15),
    "base_green": (25.0, 35.0, 45.0),
}
CALIBRATION_INTERSECTIONS = ("1", "11", "16")
CALIBRATION_SEEDS = (42,)
HOLDOUT_SEEDS = (123, 456)


def calibration_seeds() -> tuple[int, ...]:
    return CALIBRATION_SEEDS


def holdout_seeds() -> tuple[int, ...]:
    return HOLDOUT_SEEDS


def parameter_candidates() -> list[dict[str, float]]:
    keys = tuple(PARAMETER_GRID)
    return [
        dict(zip(keys, values))
        for values in itertools.product(*(PARAMETER_GRID[key] for key in keys))
    ]


def _metrics(result: RunResult) -> dict | None:
    if result.status is not RunStatus.COMPLETED or not result.summary:
        return None
    metrics = result.summary.get("metrics")
    return metrics if isinstance(metrics, dict) else None


def _ratio(value: object, baseline: object, *, throughput: bool = False) -> float:
    if value is None or baseline is None:
        return float("inf")
    value_float = float(value)
    baseline_float = float(baseline)
    if baseline_float == 0:
        if value_float == 0:
            return 1.0
        return 0.0 if throughput else float("inf")
    return value_float / baseline_float


def relative_composite(candidate: RunResult, baseline: RunResult) -> float:
    """Lower is better; missing or failed evidence receives infinity."""
    candidate_metrics = _metrics(candidate)
    baseline_metrics = _metrics(baseline)
    if candidate_metrics is None or baseline_metrics is None:
        return float("inf")
    ratios = {
        "travel": _ratio(
            candidate_metrics.get("avg_travel_time"),
            baseline_metrics.get("avg_travel_time"),
        ),
        "queue": _ratio(
            candidate_metrics.get("avg_queue_length"),
            baseline_metrics.get("avg_queue_length"),
        ),
        "fuel": _ratio(
            candidate_metrics.get("fuel_consumption"),
            baseline_metrics.get("fuel_consumption"),
        ),
        "throughput": _ratio(
            candidate_metrics.get("throughput"),
            baseline_metrics.get("throughput"),
            throughput=True,
        ),
    }
    if any(value == float("inf") for value in ratios.values()):
        return float("inf")
    return (
        0.35 * ratios["travel"]
        + 0.30 * ratios["queue"]
        + 0.15 * ratios["fuel"]
        - 0.20 * ratios["throughput"]
    )


def _request(
    output_root: Path,
    intersection: str,
    algorithm: str,
    seed: int,
    steps: int,
    parameters: dict[str, float] | None = None,
) -> RunRequest:
    return RunRequest(
        intersection_id=intersection,
        algorithm=algorithm,
        steps=steps,
        flow_multiplier=1.5,
        seed=seed,
        output_root=output_root / "runs",
        algorithm_params=parameters or {},
    )


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)


def tune_ca_mp(
    output_root: Path,
    steps: int = 36000,
    run_service: RunService | None = None,
) -> dict[str, float]:
    """Calibrate on seed 42, freeze a winner, then evaluate seeds 123/456."""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    service = run_service or RunService(output_root=output_root / "runs")
    owns_service = run_service is None
    try:
        baselines = {
            intersection: service.run_sync(
                _request(
                    output_root,
                    intersection,
                    "fixed_time",
                    CALIBRATION_SEEDS[0],
                    steps,
                )
            )
            for intersection in CALIBRATION_INTERSECTIONS
        }
        rows = []
        candidate_runs: dict[tuple[float, float, float], list[RunResult]] = {}
        for parameters in parameter_candidates():
            key = (
                parameters["overflow_occupancy_threshold"],
                parameters["prediction_weight"],
                parameters["base_green"],
            )
            runs = [
                service.run_sync(
                    _request(
                        output_root,
                        intersection,
                        "ca_maxpressure",
                        CALIBRATION_SEEDS[0],
                        steps,
                        parameters,
                    )
                )
                for intersection in CALIBRATION_INTERSECTIONS
            ]
            candidate_runs[key] = runs
            scores = [
                relative_composite(run, baselines[intersection])
                for intersection, run in zip(CALIBRATION_INTERSECTIONS, runs)
            ]
            score = mean(scores)
            rows.append({
                **parameters,
                "score": score,
                "run_ids": ";".join(run.run_id for run in runs),
                "statuses": ";".join(run.status.value for run in runs),
            })
        _write_csv(output_root / "tuning_results.csv", rows)

        winner = min(
            rows,
            key=lambda row: (
                float(row["score"]),
                float(row["overflow_occupancy_threshold"]),
                float(row["prediction_weight"]),
                float(row["base_green"]),
            ),
        )
        selected = {
            "overflow_occupancy_threshold": float(
                winner["overflow_occupancy_threshold"]
            ),
            "prediction_weight": float(winner["prediction_weight"]),
            "base_green": float(winner["base_green"]),
        }
        selected_key = (
            selected["overflow_occupancy_threshold"],
            selected["prediction_weight"],
            selected["base_green"],
        )
        selected_payload = {
            "parameters": selected,
            "score": winner["score"],
            "calibration_intersections": list(CALIBRATION_INTERSECTIONS),
            "calibration_seeds": list(CALIBRATION_SEEDS),
            "source_run_ids": [
                run.run_id for run in candidate_runs[selected_key]
            ],
        }
        (output_root / "selected_params.json").write_text(
            json.dumps(
                selected_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        holdout_rows = []
        for intersection, seed in itertools.product(
            CALIBRATION_INTERSECTIONS,
            HOLDOUT_SEEDS,
        ):
            baseline = service.run_sync(
                _request(
                    output_root,
                    intersection,
                    "fixed_time",
                    seed,
                    steps,
                )
            )
            candidate = service.run_sync(
                _request(
                    output_root,
                    intersection,
                    "ca_maxpressure",
                    seed,
                    steps,
                    selected,
                )
            )
            holdout_rows.append({
                "intersection_id": intersection,
                "seed": seed,
                "baseline_run_id": baseline.run_id,
                "candidate_run_id": candidate.run_id,
                "score": relative_composite(candidate, baseline),
            })
        holdout_payload = {
            "parameters": selected,
            "seeds": list(HOLDOUT_SEEDS),
            "cases": holdout_rows,
            "mean_score": mean(row["score"] for row in holdout_rows),
        }
        (output_root / "holdout_summary.json").write_text(
            json.dumps(
                holdout_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return selected
    finally:
        if owns_service:
            service.shutdown()
