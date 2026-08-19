"""Traceable paired statistical analysis for the experiment matrix.

Consumes a frozen ``matrix.csv`` and produces descriptive statistics, paired t-tests
(Bonferroni-corrected), and a reproducibility manifest.  Every comparison is paired on
``intersection_id``, ``flow_multiplier``, and ``seed``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from scipy.stats import ttest_rel

from algorithms.registry import get_algorithm_registry

PAIR_KEYS = ["intersection_id", "flow_multiplier", "seed"]
METRICS = (
    "avg_travel_time",
    "avg_delay",
    "avg_queue_length",
    "throughput",
    "total_stops",
    "fuel_consumption",
)
FORMAL_ALGORITHMS = tuple(
    spec.key for spec in get_algorithm_registry().list(formal_only=True)
)
CANDIDATE_ALGORITHM = "capacity_aware_maxpressure"
BASELINES = tuple(
    key for key in FORMAL_ALGORITHMS if key != CANDIDATE_ALGORITHM
)
LOWER_IS_BETTER = {
    "avg_travel_time",
    "avg_delay",
    "avg_queue_length",
    "total_stops",
    "fuel_consumption",
}
N_TESTS = len(BASELINES) * len(METRICS)  # Bonferroni divisor


def improvement_percent(
    candidate: pd.Series, baseline: pd.Series, metric: str
) -> float:
    """Mean relative improvement; positive == better."""
    if metric in LOWER_IS_BETTER:
        return float(((baseline - candidate) / baseline).mean() * 100.0)
    return float(((candidate - baseline) / baseline).mean() * 100.0)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze_matrix(
    matrix_csv: Path, output_dir: Path
) -> dict[str, Path]:
    """Run paired analysis and write results to *output_dir*.

    Returns a dictionary mapping artifact names to their file paths.
    """
    # ------------------------------------------------------------------
    # 1. Load and validate
    # ------------------------------------------------------------------
    frame = pd.read_csv(matrix_csv)
    required = [*PAIR_KEYS, "algorithm", "status", *METRICS]
    missing = [c for c in required if c not in frame.columns]
    if missing:
        raise ValueError(f"Matrix CSV missing columns: {missing}")

    # Only completed runs
    incomplete = frame[frame["status"] != "completed"]
    if len(incomplete):
        raise ValueError(
            f"Matrix contains {len(incomplete)} non-completed row(s); "
            "only fully completed matrices are accepted"
        )

    # All three algorithms must be present
    algorithms = set(frame["algorithm"].unique())
    expected = set(FORMAL_ALGORITHMS)
    if algorithms != expected:
        raise ValueError(
            f"Expected algorithms {sorted(expected)}, got {sorted(algorithms)}"
        )

    # Duplicate check on pair keys + algorithm
    dup_mask = frame.duplicated(subset=[*PAIR_KEYS, "algorithm"], keep=False)
    if dup_mask.any():
        dup_cols = ["intersection_id", "algorithm", "flow_multiplier", "seed"]
        dup_rows = frame[dup_mask]
        dup_detail = dup_rows[dup_cols].to_dict("records")
        raise ValueError(
            f"Matrix contains duplicate case(s): {dup_detail}"
        )

    # ------------------------------------------------------------------
    # 2. Descriptive statistics
    # ------------------------------------------------------------------
    desc_rows: list[dict[str, Any]] = []
    for algo in sorted(expected):
        subset = frame[frame["algorithm"] == algo]
        for metric in METRICS:
            values = subset[metric]
            desc_rows.append(
                {
                    "algorithm": algo,
                    "metric": metric,
                    "n": int(values.count()),
                    "mean": float(values.mean()),
                    "std": float(values.std(ddof=1)),
                    "min": float(values.min()),
                    "max": float(values.max()),
                }
            )
    desc_df = pd.DataFrame(desc_rows)
    desc_path = output_dir / "descriptive_stats.csv"
    desc_path.parent.mkdir(parents=True, exist_ok=True)
    desc_df.to_csv(desc_path, index=False)

    # ------------------------------------------------------------------
    # 3. Paired t-tests
    # ------------------------------------------------------------------
    paired_rows: list[dict[str, Any]] = []
    candidate_algo = CANDIDATE_ALGORITHM
    candidate_data = frame[frame["algorithm"] == candidate_algo]

    for baseline_algo in BASELINES:
        baseline_data = frame[frame["algorithm"] == baseline_algo]
        # Merge on pair keys to guarantee identical ordering
        merged = pd.merge(
            candidate_data,
            baseline_data,
            on=PAIR_KEYS,
            suffixes=("_candidate", "_baseline"),
        )
        for metric in METRICS:
            c = merged[f"{metric}_candidate"]
            b = merged[f"{metric}_baseline"]

            if len(c) == 0 or len(b) == 0:
                raise ValueError(
                    f"No paired data for {baseline_algo} vs {candidate_algo} "
                    f"on {metric}"
                )

            t_stat, p_value = ttest_rel(c, b, nan_policy="omit")
            p_bonf = min(p_value * N_TESTS, 1.0)

            paired_rows.append(
                {
                    "baseline": baseline_algo,
                    "candidate": candidate_algo,
                    "metric": metric,
                    "n_pairs": len(c),
                    "baseline_mean": float(b.mean()),
                    "candidate_mean": float(c.mean()),
                    "mean_difference": float(c.mean() - b.mean()),
                    "improvement_percent": improvement_percent(c, b, metric),
                    "t_statistic": float(t_stat),
                    "p_value": float(p_value),
                    "p_value_bonferroni": p_bonf,
                    "significant_after_bonferroni": p_bonf < 0.05,
                }
            )

    paired_df = pd.DataFrame(paired_rows)
    paired_path = output_dir / "paired_tests.csv"
    paired_df.to_csv(paired_path, index=False)

    # ------------------------------------------------------------------
    # 4. Manifest
    # ------------------------------------------------------------------
    manifest: dict[str, Any] = {
        "matrix_path": str(matrix_csv.resolve()),
        "matrix_sha256": _sha256(matrix_csv),
        "command": " ".join(sys.argv),
        "metrics": list(METRICS),
        "pair_keys": PAIR_KEYS,
        "baselines": list(BASELINES),
        "correction": f"Bonferroni, N_tests={N_TESTS}",
        "outputs": {
            "descriptive_stats": {
                "path": str(desc_path.resolve()),
                "sha256": _sha256(desc_path),
            },
            "paired_tests": {
                "path": str(paired_path.resolve()),
                "sha256": _sha256(paired_path),
            },
        },
    }
    manifest_path = output_dir / "analysis_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "descriptive_stats": desc_path,
        "paired_tests": paired_path,
        "analysis_manifest": manifest_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run paired statistical analysis on the experiment matrix."
    )
    parser.add_argument(
        "--matrix", required=True, type=Path, help="Path to matrix.csv"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="Output directory"
    )
    args = parser.parse_args()

    outputs = analyze_matrix(args.matrix, args.output)
    print(f"Wrote {len(outputs)} file(s) to {args.output.resolve()}:")
    for name, path in outputs.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
