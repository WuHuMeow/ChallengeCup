"""Reusable evidence-grade plots for simulation results."""

from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402


def plot_algorithm_comparison(
    csv_files: List[Path],
    labels: List[str],
    output_file: Path,
    metric: str = "avg_queue_length",
) -> None:
    """Compare one time-series metric across run-level CSV files."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(10, 6))
    for csv_file, label in zip(csv_files, labels):
        frame = pd.read_csv(csv_file)
        if metric in frame.columns and "step" in frame.columns:
            axis.plot(frame["step"], frame[metric], label=label)
    axis.set_xlabel("Simulation step")
    axis.set_ylabel(metric)
    axis.set_title(f"Algorithm comparison: {metric}")
    axis.grid(True, alpha=0.3)
    if axis.lines:
        axis.legend()
    figure.tight_layout()
    figure.savefig(output_file, dpi=160)
    plt.close(figure)


def plot_heatmap(
    results_csv: Path,
    output_file: Path,
    metric: str = "avg_travel_time",
) -> None:
    """Plot a real intersection-by-algorithm metric matrix."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(results_csv)
    required = {"intersection_id", "algorithm", metric}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"heatmap input is missing columns: {sorted(missing)}")
    frame[metric] = pd.to_numeric(frame[metric], errors="coerce")
    pivot = frame.pivot_table(
        index="intersection_id",
        columns="algorithm",
        values=metric,
        aggfunc="mean",
    )
    if pivot.empty:
        raise ValueError(f"no numeric values available for {metric}")
    pivot = pivot.reindex(
        sorted(pivot.index, key=lambda value: int(value)),
    )

    figure, axis = plt.subplots(figsize=(10, max(5, len(pivot.index) * 0.4)))
    image = axis.imshow(pivot.to_numpy(), aspect="auto", cmap="viridis")
    axis.set_xticks(
        range(len(pivot.columns)),
        [str(value) for value in pivot.columns],
        rotation=30,
        ha="right",
    )
    axis.set_yticks(
        range(len(pivot.index)),
        [str(value) for value in pivot.index],
    )
    axis.set_xlabel("Algorithm")
    axis.set_ylabel("Intersection")
    axis.set_title(f"Intersection comparison: {metric}")
    figure.colorbar(image, ax=axis, label=metric)
    figure.tight_layout()
    figure.savefig(output_file, dpi=160)
    plt.close(figure)
