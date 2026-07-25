"""Run IA/IB stress simulations and record resource usage."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.runner import parse_args, run_single  # noqa: E402


def parse_stress_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the pressure-run CLI with the supported IA/IB defaults."""
    parser = argparse.ArgumentParser(description="IA/IB pressure and memory validation")
    parser.add_argument(
        "legacy_intersection", nargs="?", help=argparse.SUPPRESS
    )
    parser.add_argument("legacy_steps", nargs="?", type=int, help=argparse.SUPPRESS)
    parser.add_argument(
        "--algorithm", choices=("fixed_time", "actuated"), default="actuated"
    )
    parser.add_argument("--intersections", nargs="+", default=None)
    parser.add_argument("--steps", type=int, default=3600)
    parser.add_argument("--flow-multiplier", type=float, default=1.5)
    parser.add_argument("--output-root", type=Path, default=ROOT / "output" / "stress")
    parser.add_argument("--max-python-mib", type=float, default=1024)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if args.intersections is None:
        args.intersections = (
            [args.legacy_intersection]
            if args.legacy_intersection
            else ["1", "11", "16"]
        )
    else:
        args.intersections = [
            item
            for value in args.intersections
            for item in value.split(",")
            if item
        ]
    if args.legacy_steps is not None:
        args.steps = args.legacy_steps
    if args.steps <= 0:
        parser.error("--steps must be positive")
    if args.flow_multiplier <= 0:
        parser.error("--flow-multiplier must be positive")
    if args.max_python_mib <= 0:
        parser.error("--max-python-mib must be positive")
    invalid = [
        value
        for value in args.intersections
        if not value.isdigit() or not 1 <= int(value) <= 20
    ]
    if invalid:
        parser.error(f"invalid intersection(s): {', '.join(invalid)}")
    return args


def _output_sizes(
    root: Path, csv_path: Path | None, before: set[Path] | None = None
) -> dict[str, int]:
    sizes: dict[str, int] = {}
    if csv_path is not None and csv_path.exists():
        sizes[str(csv_path)] = csv_path.stat().st_size
    if root.exists():
        for path in root.rglob("*"):
            if path.is_file() and (before is None or path not in before):
                sizes.setdefault(str(path), path.stat().st_size)
    return sizes


def _step_length(intersection: str) -> float:
    config = ROOT / "engine" / "configs" / f"demo_{intersection}.sumocfg"
    if not config.exists():
        return 1.0
    match = re.search(
        r'<step-length\s+value="([0-9.]+)"',
        config.read_text(encoding="utf-8", errors="ignore"),
    )
    return float(match.group(1)) if match else 1.0


def _simulated_time_seconds(intersection: str, steps: int) -> float:
    return float(steps) * _step_length(intersection)


def _actual_simulated_time_seconds(
    csv_path: Path | None, intersection: str, requested_steps: int
) -> float:
    if csv_path is None:
        return 0.0
    step_log = csv_path.parent / "simulation_log.csv"
    last_step = -1
    if step_log.exists():
        with step_log.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                last_step = max(last_step, int(row["step"]))
    ticks = last_step + 1 if last_step >= 0 else requested_steps
    return ticks * _step_length(intersection)


def run_stress(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Execute configured runs, returning serializable metrics for each run."""
    args.output_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for intersection in args.intersections:
        started = time.perf_counter()
        tracemalloc.start()
        csv_path: Path | None = None
        error = ""
        exit_status = 0
        try:
            runner_args = parse_args([
                "--intersection", intersection,
                "--steps", str(args.steps),
                "--flow-multiplier", str(args.flow_multiplier),
                "--output-dir", str(args.output_root),
                "--algorithm", args.algorithm,
                "--seed", str(args.seed),
            ])
            csv_path = run_single(runner_args)
        except Exception as exc:  # retain all run outcomes for the report
            exit_status = 1
            error = f"{type(exc).__name__}: {exc}"
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        wall = time.perf_counter() - started
        peak_mib = peak / 1024 / 1024
        if peak_mib > args.max_python_mib:
            exit_status = 1
            error = error or (
                f"Python peak {peak_mib:.1f} MiB exceeds "
                f"{args.max_python_mib:g} MiB"
            )
        records.append({
            "intersection": intersection,
            "algorithm": args.algorithm,
            "flow_multiplier": args.flow_multiplier,
            "control_steps": args.steps,
            "simulated_time_seconds": _actual_simulated_time_seconds(
                csv_path, intersection, args.steps
            ),
            "wall_seconds": wall,
            "python_peak_mib": peak_mib,
            "output_sizes": _output_sizes(
                csv_path.parent if csv_path else args.output_root,
                csv_path,
            ),
            "exit_status": exit_status,
            "error": error,
        })
    (args.output_root / "stress_results.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8"
    )
    return records


def main(argv: list[str] | None = None) -> int:
    args = parse_stress_args(argv)
    records = run_stress(args)
    for record in records:
        print(
            f"[{('PASS' if record['exit_status'] == 0 else 'FAIL')}] "
            f"intersection={record['intersection']} steps={record['control_steps']} "
            f"sim={record['simulated_time_seconds']:.1f}s wall={record['wall_seconds']:.2f}s "
            f"peak={record['python_peak_mib']:.1f}MiB"
        )
    return 0 if all(item["exit_status"] == 0 for item in records) else 1


if __name__ == "__main__":
    sys.exit(main())
