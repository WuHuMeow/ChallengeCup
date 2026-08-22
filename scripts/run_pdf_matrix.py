"""Run the PDF-required experiment matrix with resumable run identities."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.run_models import RunRequest, RunResult, RunStatus  # noqa: E402
from engine.artifacts import RunArtifacts  # noqa: E402
from engine.run_service import RunService  # noqa: E402
from experiments.evidence import EvidenceReader  # noqa: E402
from experiments.matrix import (  # noqa: E402
    FORMAL_ALGORITHMS,
    FORMAL_FLOWS,
    FORMAL_SEEDS,
    FormalMatrix,
    RunSpec,
    run_matrix,
)


ALGORITHMS = FORMAL_ALGORITHMS
FLOW_MULTIPLIERS = FORMAL_FLOWS
SEEDS = FORMAL_SEEDS
REQUIRED_ARTIFACTS = RunArtifacts.required_output_names()


def parse_matrix_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the bounded smoke/quick and frozen formal matrix profiles."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile", choices=("smoke", "quick", "formal"), default="formal"
    )
    parser.add_argument("--duration-seconds", type=float, default=None)
    parser.add_argument("--warmup-seconds", type=float, default=None)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args(argv)


def build_profile_matrix(args: argparse.Namespace) -> tuple[RunSpec, ...]:
    """Build a CLI profile without allowing formal-factor overrides."""
    if args.profile == "formal":
        if args.seed is not None:
            raise ValueError("formal profile does not accept --seed")
        if args.duration_seconds not in (None, 3600.0):
            raise ValueError("formal profile duration is frozen at 3600 seconds")
        if args.warmup_seconds not in (None, 600.0):
            raise ValueError("formal profile warmup is frozen at 600 seconds")
        return FormalMatrix.all()

    defaults = {
        "smoke": (10.0, 0.0),
        "quick": (600.0, 60.0),
    }
    default_duration, default_warmup = defaults[args.profile]
    duration = (
        default_duration if args.duration_seconds is None else args.duration_seconds
    )
    warmup = default_warmup if args.warmup_seconds is None else args.warmup_seconds
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration-seconds must be finite and > 0")
    if (
        not math.isfinite(warmup)
        or warmup < 0
        or warmup >= duration
    ):
        raise ValueError("warmup-seconds must be finite, >= 0, and less than duration")
    selected_seeds = (
        (42,)
        if args.profile == "smoke" and args.seed is None
        else FORMAL_SEEDS
        if args.profile == "quick" and args.seed is None
        else (args.seed,)
    )
    if any(seed is None or seed < 0 for seed in selected_seeds):
        raise ValueError("seed must be >= 0")
    scenes = {"smoke": {"1"}, "quick": {"1", "11", "16"}}[args.profile]
    algorithms = (
        {"fixed_time"}
        if args.profile == "smoke"
        else set(FORMAL_ALGORITHMS)
    )
    flows = {1.0} if args.profile == "smoke" else set(FORMAL_FLOWS)
    explicit_steps = (
        100
        if args.profile == "smoke"
        and args.duration_seconds is None
        and args.warmup_seconds is None
        else None
    )
    return tuple(
        RunSpec(
            spec.scene_id,
            spec.algorithm,
            spec.flow_multiplier,
            selected_seed,
            duration_seconds=duration,
            warmup_seconds=warmup,
            algorithm_params=spec.algorithm_params,
            steps=explicit_steps,
        )
        for spec in FormalMatrix.normal()
        for selected_seed in selected_seeds
        if spec.scene_id in scenes
        and spec.algorithm in algorithms
        and spec.flow_multiplier in flows
        and spec.seed == 42
    )


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
        "variant": asdict(request.variant),
        "disturbance": (
            asdict(request.disturbance)
            if request.disturbance is not None
            else None
        ),
        "edge_delay_steps": int(request.edge_delay_steps),
        "edge_directions": list(request.edge_directions),
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
        manifest = json.loads(
            (result_dir / "manifest.json").read_text(encoding="utf-8")
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
        request_dimensions = manifest.get("request_dimensions")
        if not isinstance(request_dimensions, dict):
            return False
        recorded_parameters = request_dimensions.get("algorithm_params")
        if not isinstance(recorded_parameters, dict):
            return False
        normalized_recorded_parameters = {
            str(name): float(value)
            for name, value in recorded_parameters.items()
        }
        normalized_request_parameters = {
            str(name): float(value)
            for name, value in request.algorithm_params.items()
        }
        if normalized_recorded_parameters != normalized_request_parameters:
            return False
        recorded_request_identity = {
            "requested_steps": (
                int(request_dimensions["requested_steps"])
                if request_dimensions.get("requested_steps") is not None
                else None
            ),
            "steps_origin": str(request_dimensions["steps_origin"]),
            "duration_seconds": float(request_dimensions["duration_seconds"]),
            "warmup_seconds": float(request_dimensions["warmup_seconds"]),
            "step_length_override": (
                float(request_dimensions["step_length_override"])
                if request_dimensions.get("step_length_override") is not None
                else None
            ),
        }
        current_request_identity = {
            "requested_steps": (
                int(request.steps) if request.steps is not None else None
            ),
            "steps_origin": request.steps_origin,
            "duration_seconds": float(request.duration_seconds),
            "warmup_seconds": float(request.warmup_seconds),
            "step_length_override": (
                float(request.step_length_override)
                if request.step_length_override is not None
                else None
            ),
        }
        if recorded_request_identity != current_request_identity:
            return False
        recorded_execution_dimensions = {
            "variant": request_dimensions["variant"],
            "disturbance": request_dimensions.get("disturbance"),
            "edge_delay_steps": int(request_dimensions["edge_delay_steps"]),
            "edge_directions": list(request_dimensions["edge_directions"]),
        }
        current_execution_dimensions = {
            "variant": asdict(request.variant),
            "disturbance": (
                asdict(request.disturbance)
                if request.disturbance is not None
                else None
            ),
            "edge_delay_steps": int(request.edge_delay_steps),
            "edge_directions": list(request.edge_directions),
        }
        if json.dumps(
            recorded_execution_dimensions,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ) != json.dumps(
            current_execution_dimensions,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ):
            return False
        recorded_run_id = metadata.get("run_id")
        if recorded_run_id is not None and str(recorded_run_id) != result_dir.name:
            return False

        requested_steps = metadata.get("requested_steps")
        if (
            request.steps_origin == "explicit"
            and requested_steps is not None
            and requested_steps != request.steps
        ):
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
            target_time = (
                request.steps * step_length
                if request.steps is not None
                else request.duration_seconds
            )
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
    return _load_result_dir(request, _run_dir(request, run_id))


def _load_result_dir(request: RunRequest, run_dir: Path) -> RunResult:
    run_dir = Path(run_dir)
    metadata = json.loads(
        (run_dir / "run_metadata.json").read_text(encoding="utf-8")
    )
    summary = EvidenceReader.load_summary(run_dir)
    if summary is None:
        raise ValueError("run result has no canonical strict-evidence summary")
    return RunResult(
        run_id=run_dir.name,
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
                if not is_complete(result.run_dir, request):
                    raise ValueError(
                        "live matrix result is not strict evidence for its request"
                    )
                result = _load_result_dir(request, result.run_dir)
                state[key] = result.run_id
                _atomic_json(state_path, state)
            results.append(result)
            _write_matrix(output_root / "matrix.csv", requests[:len(results)], results)
        return results
    finally:
        if owns_service:
            service.shutdown()


def main() -> None:
    args = parse_matrix_args()
    try:
        specs = build_profile_matrix(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    report = run_matrix(specs, args.output_root, args.resume)
    print(json.dumps({
        "runs": len(report.entries),
        "completed": report.completed,
        "failed": report.failed,
        "skipped": report.skipped,
        "retried": report.retried,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
