"""Run the PDF-required experiment matrix with resumable run identities."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.run_models import RunRequest, RunResult, RunStatus  # noqa: E402
from engine.artifacts import RunArtifacts  # noqa: E402
from engine.run_service import RunService  # noqa: E402
from experiments.tuning import tune_ca_mp  # noqa: E402


ALGORITHMS = ("fixed_time", "actuated", "ca_maxpressure")
FLOW_MULTIPLIERS = (1.0, 1.5)
SEEDS = (42, 123, 456)
REQUIRED_ARTIFACTS = RunArtifacts.required_output_names()


def _selected_params(output_root: Path) -> dict[str, float]:
    path = output_root / "selected_params.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    parameters = payload.get("parameters", payload)
    return {key: float(value) for key, value in parameters.items()}


def build_pdf_matrix(
    output_root: Path,
    steps: int = 36000,
    intersections: tuple[str, ...] | None = None,
    selected_params: dict[str, float] | None = None,
) -> list[RunRequest]:
    intersections = intersections or tuple(str(index) for index in range(1, 21))
    parameters = selected_params if selected_params is not None else _selected_params(
        Path(output_root)
    )
    return [
        RunRequest(
            intersection_id=intersection,
            algorithm=algorithm,
            steps=steps,
            flow_multiplier=flow_multiplier,
            seed=seed,
            output_root=Path(output_root) / "runs",
            algorithm_params=parameters if algorithm == "ca_maxpressure" else {},
        )
        for intersection in intersections
        for algorithm in ALGORITHMS
        for flow_multiplier in FLOW_MULTIPLIERS
        for seed in SEEDS
    ]


def request_key(request: RunRequest) -> str:
    return "|".join([
        request.intersection_id,
        request.algorithm,
        f"{request.flow_multiplier:g}",
        str(request.seed),
        str(request.steps),
    ])


def is_complete(result_dir: Path) -> bool:
    try:
        metadata = json.loads(
            (result_dir / "run_metadata.json").read_text(encoding="utf-8")
        )
        return metadata.get("status") == "completed" and all(
            (result_dir / name).stat().st_size > 0
            for name in REQUIRED_ARTIFACTS
        )
    except (OSError, json.JSONDecodeError):
        return False


def _run_dir(request: RunRequest, run_id: str) -> Path:
    return (
        Path(request.output_root)
        / f"i{request.intersection_id}"
        / request.algorithm
        / f"x{request.flow_multiplier:g}"
        / f"s{request.seed}"
        / run_id
    )


def _load_result(request: RunRequest, run_id: str) -> RunResult:
    run_dir = _run_dir(request, run_id)
    metadata = json.loads(
        (run_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    summary_path = run_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return RunResult(
        run_id=run_id,
        status=RunStatus(metadata["status"]),
        reason=metadata.get("reason", ""),
        run_dir=run_dir,
        summary=summary,
    )


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_matrix(path: Path, requests, results) -> None:
    rows = []
    for request, result in zip(requests, results):
        metrics = (result.summary or {}).get("metrics", {})
        rows.append({
            "intersection_id": request.intersection_id,
            "algorithm": request.algorithm,
            "flow_multiplier": request.flow_multiplier,
            "seed": request.seed,
            "steps": request.steps,
            "run_id": result.run_id,
            "status": result.status.value,
            "reason": result.reason,
            "run_dir": str(result.run_dir),
            "avg_travel_time": metrics.get("avg_travel_time"),
            "avg_delay": metrics.get("avg_delay"),
            "avg_queue_length": metrics.get("avg_queue_length"),
            "max_queue_length": metrics.get("max_queue_length"),
            "throughput": metrics.get("throughput"),
            "total_stops": metrics.get("total_stops"),
            "fuel_consumption": metrics.get("fuel_consumption"),
        })
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_pdf_matrix(
    output_root: Path,
    steps: int = 36000,
    resume: bool = True,
    intersections: tuple[str, ...] | None = None,
    run_service: RunService | None = None,
    selected_params: dict[str, float] | None = None,
) -> list[RunResult]:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    requests = build_pdf_matrix(
        output_root,
        steps=steps,
        intersections=intersections,
        selected_params=selected_params,
    )
    state_path = output_root / "matrix_state.json"
    state = {}
    if resume and state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    service = run_service or RunService(output_root=output_root / "runs")
    owns_service = run_service is None
    results = []
    try:
        for request in requests:
            key = request_key(request)
            run_id = state.get(key)
            run_dir = _run_dir(request, run_id) if run_id else None
            if resume and run_dir is not None and is_complete(run_dir):
                result = _load_result(request, run_id)
            else:
                result = service.run_sync(request)
                state[key] = result.run_id
                _atomic_json(state_path, state)
            results.append(result)
            _write_matrix(output_root / "matrix.csv", requests[:len(results)], results)
        return results
    finally:
        if owns_service:
            service.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=36000)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--tune", action="store_true")
    args = parser.parse_args()
    selected = None
    if args.tune:
        selected = tune_ca_mp(
            args.output_root,
            steps=100 if args.quick else args.steps,
        )
    intersections = ("1", "11", "16") if args.quick else None
    steps = 100 if args.quick else args.steps
    results = run_pdf_matrix(
        args.output_root,
        steps=steps,
        resume=not args.no_resume,
        intersections=intersections,
        selected_params=selected,
    )
    counts = {}
    for result in results:
        counts[result.status.value] = counts.get(result.status.value, 0) + 1
    print(json.dumps({"runs": len(results), "statuses": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
