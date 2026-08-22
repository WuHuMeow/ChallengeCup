"""Generate comparison figures and provenance manifests from run artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from defusedxml import ElementTree as ET  # noqa: E402

from visualization.plots import plot_heatmap  # noqa: E402
from experiments.evidence import EvidenceReader  # noqa: E402


COMPARISON_METRICS = (
    "avg_travel_time",
    "avg_delay",
    "avg_queue_length",
    "throughput",
    "fuel_consumption",
)


def collect_summaries(root: Path) -> pd.DataFrame:
    """Collect exact summary metrics and run identity from one artifact tree."""
    rows = []
    for summary_path in sorted(Path(root).rglob("summary.json")):
        run_dir = summary_path.parent
        if EvidenceReader.validate(run_dir):
            continue
        metadata_path = run_dir / "run_metadata.json"
        if not metadata_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        row = {
            "run_id": metadata.get("run_id", summary.get("run_id", "")),
            "intersection_id": str(metadata["intersection_id"]),
            "algorithm": metadata["algorithm"],
            "flow_multiplier": metadata.get("flow_multiplier"),
            "seed": metadata.get("seed"),
            "status": metadata.get("status"),
            "run_dir": str(run_dir.resolve()),
            "summary_path": str(summary_path.resolve()),
        }
        row.update(summary.get("metrics", {}))
        rows.append(row)
    return pd.DataFrame(rows)


def _algorithm_bar(frame: pd.DataFrame, metric: str, output: Path) -> None:
    values = frame.assign(
        **{metric: pd.to_numeric(frame[metric], errors="coerce")}
    ).groupby("algorithm")[metric].mean().dropna()
    if values.empty:
        raise ValueError(f"no numeric values available for {metric}")
    figure, axis = plt.subplots(figsize=(8, 5))
    values.sort_index().plot(kind="bar", ax=axis, color="#3b82f6")
    axis.set_xlabel("Algorithm")
    axis.set_ylabel(metric)
    axis.set_title(f"Mean {metric} by algorithm")
    axis.grid(axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def _queue_timeseries(metrics_path: Path, output: Path) -> None:
    frame = pd.read_csv(metrics_path)
    figure, axis = plt.subplots(figsize=(10, 5))
    plotted = False
    for metric in ("avg_queue_length", "max_queue_length"):
        if metric in frame.columns:
            axis.plot(frame["step"], frame[metric], label=metric)
            plotted = True
    if not plotted:
        raise ValueError(f"no queue time-series columns in {metrics_path}")
    axis.set_xlabel("Simulation step")
    axis.set_ylabel("Vehicles")
    axis.set_title("Representative queue time series")
    axis.legend()
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def _trajectory_plot(fcd_path: Path, output: Path) -> None:
    root = ET.parse(fcd_path).getroot()
    traces: dict[str, list[tuple[float, float]]] = {}
    for timestep in root.iter("timestep"):
        time_value = float(timestep.get("time", "0"))
        for vehicle in timestep.findall("vehicle"):
            position = vehicle.get("pos")
            if position is None:
                continue
            traces.setdefault(vehicle.get("id", "unknown"), []).append(
                (time_value, float(position))
            )
    if not traces:
        raise ValueError(f"no vehicle trajectories in {fcd_path}")
    figure, axis = plt.subplots(figsize=(10, 6))
    for points in list(traces.values())[:200]:
        times, positions = zip(*points)
        axis.plot(times, positions, linewidth=0.7, alpha=0.5)
    axis.set_xlabel("Simulation time (s)")
    axis.set_ylabel("Lane position (m)")
    axis.set_title("Representative FCD time-space trajectories")
    axis.grid(True, alpha=0.2)
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)


def _write_manifest(
    output_dir: Path,
    figures: list[dict[str, Any]],
    command: str,
) -> None:
    payload = {"command": command, "figures": figures}
    (output_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate_run_figures(run_dir: Path) -> list[Path]:
    """Generate summary, time-series, and FCD figures for one run."""
    run_dir = Path(run_dir)
    if EvidenceReader.validate(run_dir):
        raise ValueError("run figures require strict evidence")
    output_dir = run_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    metrics = summary.get("metrics", {})
    numeric = {
        key: value
        for key, value in metrics.items()
        if isinstance(value, (int, float))
    }
    generated = []
    entries = []
    if numeric:
        output = output_dir / "run_exact_metrics.png"
        figure, axis = plt.subplots(figsize=(10, 5))
        pd.Series(numeric).plot(kind="bar", ax=axis, color="#10b981")
        axis.set_title("Exact run metrics")
        axis.grid(axis="y", alpha=0.3)
        figure.tight_layout()
        figure.savefig(output, dpi=160)
        plt.close(figure)
        generated.append(output)
        entries.append({
            "file": output.name,
            "metric": "exact_metrics",
            "sources": [str((run_dir / "summary.json").resolve())],
            "parameters": {},
        })
    metrics_path = run_dir / "metrics.csv"
    if metrics_path.exists():
        output = output_dir / "queue_timeseries.png"
        _queue_timeseries(metrics_path, output)
        generated.append(output)
        entries.append({
            "file": output.name,
            "metric": "queue_timeseries",
            "sources": [str(metrics_path.resolve())],
            "parameters": {},
        })
    trajectory_path = run_dir / "traj.xml"
    if trajectory_path.exists() and trajectory_path.stat().st_size > 0:
        output = output_dir / "trajectory.png"
        _trajectory_plot(trajectory_path, output)
        generated.append(output)
        entries.append({
            "file": output.name,
            "metric": "fcd_position",
            "sources": [str(trajectory_path.resolve())],
            "parameters": {"vehicle_limit": 200},
        })
    _write_manifest(output_dir, entries, f"generate_run_figures({run_dir})")
    return generated


def generate_matrix_figures(root: Path, output_dir: Path) -> list[Path]:
    """Generate aggregate comparison evidence from all completed summaries."""
    root = Path(root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = collect_summaries(root)
    if frame.empty:
        raise ValueError(f"no summary.json files with metadata under {root}")
    summary_csv = output_dir / "summaries.csv"
    frame.to_csv(summary_csv, index=False)

    generated: list[Path] = []
    entries: list[dict[str, Any]] = []
    summary_sources = [str(Path(path).resolve()) for path in frame["summary_path"]]
    for metric in COMPARISON_METRICS:
        if metric not in frame.columns or pd.to_numeric(
            frame[metric], errors="coerce"
        ).dropna().empty:
            continue
        bar = output_dir / f"algorithm_{metric}.png"
        _algorithm_bar(frame, metric, bar)
        generated.append(bar)
        entries.append({
            "file": bar.name,
            "metric": metric,
            "sources": summary_sources,
            "parameters": {"aggregation": "mean", "group_by": "algorithm"},
        })
        heatmap = output_dir / f"intersection_{metric}_heatmap.png"
        plot_heatmap(summary_csv, heatmap, metric=metric)
        generated.append(heatmap)
        entries.append({
            "file": heatmap.name,
            "metric": metric,
            "sources": summary_sources,
            "parameters": {
                "aggregation": "mean",
                "rows": "intersection_id",
                "columns": "algorithm",
            },
        })

    representative = Path(
        frame.sort_values(
            ["intersection_id", "algorithm", "seed"],
        ).iloc[0]["run_dir"]
    )
    metrics_path = representative / "metrics.csv"
    if metrics_path.exists():
        output = output_dir / "representative_queue_timeseries.png"
        _queue_timeseries(metrics_path, output)
        generated.append(output)
        entries.append({
            "file": output.name,
            "metric": "queue_timeseries",
            "sources": [str(metrics_path.resolve())],
            "parameters": {"selection": str(representative.resolve())},
        })
    trajectory_path = representative / "traj.xml"
    if trajectory_path.exists() and trajectory_path.stat().st_size > 0:
        output = output_dir / "representative_trajectory.png"
        _trajectory_plot(trajectory_path, output)
        generated.append(output)
        entries.append({
            "file": output.name,
            "metric": "fcd_position",
            "sources": [str(trajectory_path.resolve())],
            "parameters": {
                "selection": str(representative.resolve()),
                "vehicle_limit": 200,
            },
        })
    _write_manifest(
        output_dir,
        entries,
        f"python -m visualization.report --input {root} --output {output_dir}",
    )
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generated = generate_matrix_figures(args.input, args.output)
    print(f"Generated {len(generated)} figures in {args.output}")


if __name__ == "__main__":
    main()
