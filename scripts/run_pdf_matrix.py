"""Run the PDF-required experiment matrix with resumable run identities."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from algorithms.registry import get_algorithm_registry  # noqa: E402
from core.run_models import RunRequest, RunResult, RunStatus  # noqa: E402
from engine.artifacts import RunArtifacts  # noqa: E402
from engine.run_service import RunService  # noqa: E402
from experiments.evidence import EvidenceReader  # noqa: E402
from experiments.tuning import tune_ca_mp  # noqa: E402


ALGORITHMS = tuple(
    spec.key for spec in get_algorithm_registry().list(formal_only=True)
)
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
            algorithm_params=(
                parameters if algorithm == "capacity_aware_maxpressure" else {}
            ),
        )
        for intersection in intersections
        for algorithm in ALGORITHMS
        for flow_multiplier in FLOW_MULTIPLIERS
        for seed in SEEDS
    ]


def request_key(request: RunRequest) -> str:
    parameters = dict(sorted(
        (str(name), float(value))
        for name, value in request.algorithm_params.items()
    ))
    encoded_parameters = json.dumps(
        parameters,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    identity = {
        "intersection_id": str(request.intersection_id),
        "algorithm": str(request.algorithm),
        "flow_multiplier": float(request.flow_multiplier),
        "seed": int(request.seed),
        "steps": int(request.steps) if request.steps is not None else None,
        "steps_origin": request.steps_origin,
        "duration_seconds": float(request.duration_seconds),
        "warmup_seconds": float(request.warmup_seconds),
        "step_length_override": (
            float(request.step_length_override)
            if request.step_length_override is not None
            else None
        ),
        "algorithm_params": parameters,
        "algorithm_params_fingerprint": hashlib.sha256(
            encoded_parameters
        ).hexdigest(),
    }
    return json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def read_final_sumo_time(stats_path: Path) -> float | None:
    """Return the last native SUMO summary timestamp without loading the XML."""
    final_time = None
    try:
        for _, element in ET.iterparse(stats_path, events=("end",)):
            if element.tag == "step" and element.get("time") is not None:
                final_time = float(element.get("time"))
            element.clear()
    except (OSError, ET.ParseError, TypeError, ValueError):
        return None
    return final_time


def is_complete(result_dir: Path, request: RunRequest | None = None) -> bool:
    try:
        if EvidenceReader.validate(result_dir):
            return False
        metadata = json.loads(
            (result_dir / "run_metadata.json").read_text(encoding="utf-8")
        )
        artifacts_complete = metadata.get("status") == "completed" and all(
            (result_dir / name).stat().st_size > 0
            for name in REQUIRED_ARTIFACTS
        )
        if not artifacts_complete or request is None:
            return artifacts_complete

        metadata_identity = (
            str(metadata["intersection_id"]),
            str(metadata["algorithm"]),
            float(metadata["flow_multiplier"]),
            int(metadata["seed"]),
        )
        request_identity = (
            str(request.intersection_id),
            str(request.algorithm),
            float(request.flow_multiplier),
            int(request.seed),
        )
        if metadata_identity != request_identity:
            return False
        recorded_run_id = metadata.get("run_id")
        if recorded_run_id is not None and str(recorded_run_id) != result_dir.name:
            return False

        requested_steps = metadata.get("requested_steps")
        if requested_steps is not None and requested_steps != request.steps:
            return False

        # Primary: trust recorded final_simulation_time in metadata
        recorded_final_time = metadata.get("final_simulation_time")
        if recorded_final_time is not None:
            recorded_final_time = float(recorded_final_time)
            step_length = metadata.get("step_length")
            if step_length is None:
                step_length = 0.1
            step_length = float(step_length)
            if not math.isfinite(step_length) or step_length <= 0:
                return False
            target_time = request.steps * step_length
            configured_end_time = metadata.get("configured_end_time")
            if configured_end_time is not None:
                configured_end_time = float(configured_end_time)
                if not math.isfinite(configured_end_time) or configured_end_time <= 0:
                    return False
                target_time = min(target_time, configured_end_time)
            if not math.isfinite(target_time) or target_time <= 0:
                return False
            tolerance = step_length + 1e-9
            return (
                math.isfinite(recorded_final_time)
                and recorded_final_time + tolerance >= target_time
            )

        # Fallback: stats.xml may have been cleaned up for disk space,
        # or metadata may be from an older version (legacy).
        # Reject if metadata has explicit non-finite step_length.
        md_step_len = metadata.get("step_length")
        if md_step_len is not None:
            md_step_len = float(md_step_len)
            if not math.isfinite(md_step_len) or md_step_len <= 0:
                return False
        stats_file = result_dir / "stats.xml"
        if stats_file.exists():
            native_final_time = read_final_sumo_time(stats_file)
            if native_final_time is None or not math.isfinite(native_final_time):
                return False
        return True
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
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
        algorithm=request.algorithm,
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
            if resume and run_dir is not None and is_complete(run_dir, request):
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
