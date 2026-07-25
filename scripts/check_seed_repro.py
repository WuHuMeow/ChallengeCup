"""Check deterministic metrics for repeated and different SUMO seeds."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from algorithms.fixed_time import FixedTimeAlgorithm  # noqa: E402
from engine.artifacts import RunArtifacts  # noqa: E402
from engine.runner import SimulationRunner  # noqa: E402
from scenes.registry import SceneRegistry  # noqa: E402

STEPS = 300


def run_once(seed: int, output_root: Path, steps: int = STEPS) -> RunArtifacts:
    """Run one isolated experiment and return its artifact paths."""
    artifacts = RunArtifacts.create(output_root, "1", "fixed_time", 1.0, seed)
    scene = SceneRegistry().get_scene("1")
    runner = SimulationRunner(
        scene,
        FixedTimeAlgorithm(),
        seed=seed,
        artifacts=artifacts,
    )
    runner.run(steps)
    return artifacts


def read_metrics(artifacts: RunArtifacts) -> list[dict[str, str]]:
    with artifacts.metrics.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_step_log(artifacts: RunArtifacts) -> list[dict[str, str]]:
    with artifacts.step_log.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def comparable_metadata(artifacts: RunArtifacts) -> dict:
    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    payload.pop("started_at", None)
    payload.pop("ended_at", None)
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "output" / "seed_check",
    )
    args = parser.parse_args(argv)
    if args.steps <= 0:
        parser.error("--steps must be > 0")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    first = run_once(42, args.output_root / "a", args.steps)
    second = run_once(42, args.output_root / "b", args.steps)
    different = run_once(7, args.output_root / "c", args.steps)

    if read_metrics(first) != read_metrics(second) or read_step_log(first) != read_step_log(second):
        raise AssertionError("same seed must produce identical metrics and step-log rows")
    if (
        read_metrics(first) == read_metrics(different)
        and read_step_log(first) == read_step_log(different)
    ):
        raise AssertionError("different seeds should produce different simulation observations")
    if comparable_metadata(first) != comparable_metadata(second):
        raise AssertionError("same seed metadata differs beyond timestamps")
    print(
        f"OK: seed=42 repeated deterministically ({len(read_metrics(first))} rows); "
        "seed=7 differs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
