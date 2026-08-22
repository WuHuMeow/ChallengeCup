"""Generate comparison figures and provenance manifests from run artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Any
from uuid import uuid4

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
        summary = EvidenceReader.load_summary(run_dir)
        if summary is None:
            continue
        metadata_path = run_dir / "run_metadata.json"
        if not metadata_path.exists():
            continue
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


def _publish_figure_directory(staging_dir: Path, output_dir: Path) -> None:
    """Replace a complete figure directory while preserving an older version."""
    backup_dir = output_dir.with_name(
        f".{output_dir.name}.{uuid4().hex}.backup"
    )
    moved_existing = False
    if output_dir.exists():
        attributes = getattr(
            output_dir.lstat(),
            "st_file_attributes",
            0,
        )
        if (
            not output_dir.is_dir()
            or output_dir.is_symlink()
            or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        ):
            raise ValueError("figure output directory is not a safe directory")
        output_dir.replace(backup_dir)
        moved_existing = True
    try:
        staging_dir.replace(output_dir)
    except BaseException:
        if moved_existing and not output_dir.exists() and backup_dir.exists():
            backup_dir.replace(output_dir)
        raise
    else:
        if moved_existing:
            shutil.rmtree(backup_dir, ignore_errors=True)


def generate_run_figures(run_dir: Path) -> list[Path]:
    """Generate summary, time-series, and FCD figures for one run."""
    run_dir = Path(run_dir)
    summary = EvidenceReader.load_summary(run_dir)
    if summary is None:
        raise ValueError("run figures require strict evidence")
    output_dir = run_dir / "figures"
    staging_dir = Path(tempfile.mkdtemp(
        prefix=f".{run_dir.name}.figures.",
        suffix=".tmp",
        dir=run_dir.parent,
    ))
    generated_names: list[str] = []
    entries = []
    try:
        metrics = summary.get("metrics", {})
        numeric = {
            key: value
            for key, value in metrics.items()
            if isinstance(value, (int, float))
        }
        if numeric:
            output = staging_dir / "run_exact_metrics.png"
            figure, axis = plt.subplots(figsize=(10, 5))
            pd.Series(numeric).plot(kind="bar", ax=axis, color="#10b981")
            axis.set_title("Exact run metrics")
            axis.grid(axis="y", alpha=0.3)
            figure.tight_layout()
            figure.savefig(output, dpi=160)
            plt.close(figure)
            generated_names.append(output.name)
            entries.append({
                "file": output.name,
                "metric": "exact_metrics",
                "sources": [str((run_dir / "summary.json").resolve())],
                "parameters": {},
            })
        metrics_path = run_dir / "metrics.csv"
        if metrics_path.exists():
            output = staging_dir / "queue_timeseries.png"
            _queue_timeseries(metrics_path, output)
            if EvidenceReader.validate(run_dir):
                raise ValueError("evidence changed while reading metrics.csv")
            generated_names.append(output.name)
            entries.append({
                "file": output.name,
                "metric": "queue_timeseries",
                "sources": [str(metrics_path.resolve())],
                "parameters": {},
            })
        trajectory_path = run_dir / "traj.xml"
        if trajectory_path.exists() and trajectory_path.stat().st_size > 0:
            output = staging_dir / "trajectory.png"
            _trajectory_plot(trajectory_path, output)
            if EvidenceReader.validate(run_dir):
                raise ValueError("evidence changed while reading traj.xml")
            generated_names.append(output.name)
            entries.append({
                "file": output.name,
                "metric": "fcd_position",
                "sources": [str(trajectory_path.resolve())],
                "parameters": {"vehicle_limit": 200},
            })
        _write_manifest(staging_dir, entries, f"generate_run_figures({run_dir})")
        if EvidenceReader.validate(run_dir):
            raise ValueError("evidence changed before figure publication")

        _publish_figure_directory(staging_dir, output_dir)
        return [output_dir / name for name in generated_names]
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def generate_matrix_figures(root: Path, output_dir: Path) -> list[Path]:
    """Generate aggregate comparison evidence from all completed summaries."""
    root = Path(root)
    output_dir = Path(output_dir)
    frame = collect_summaries(root)
    if frame.empty:
        raise ValueError(f"no summary.json files with metadata under {root}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(
        prefix=f".{output_dir.name}.",
        suffix=".tmp",
        dir=output_dir.parent,
    ))
    generated_names: list[str] = []
    entries: list[dict[str, Any]] = []
    try:
        summary_csv = staging_dir / "summaries.csv"
        frame.to_csv(summary_csv, index=False)
        summary_sources = [
            str(Path(path).resolve()) for path in frame["summary_path"]
        ]
        for metric in COMPARISON_METRICS:
            if metric not in frame.columns or pd.to_numeric(
                frame[metric], errors="coerce"
            ).dropna().empty:
                continue
            bar = staging_dir / f"algorithm_{metric}.png"
            _algorithm_bar(frame, metric, bar)
            generated_names.append(bar.name)
            entries.append({
                "file": bar.name,
                "metric": metric,
                "sources": summary_sources,
                "parameters": {"aggregation": "mean", "group_by": "algorithm"},
            })
            heatmap = staging_dir / f"intersection_{metric}_heatmap.png"
            plot_heatmap(summary_csv, heatmap, metric=metric)
            generated_names.append(heatmap.name)
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
            output = staging_dir / "representative_queue_timeseries.png"
            _queue_timeseries(metrics_path, output)
            if EvidenceReader.validate(representative):
                raise ValueError("evidence changed while reading metrics.csv")
            generated_names.append(output.name)
            entries.append({
                "file": output.name,
                "metric": "queue_timeseries",
                "sources": [str(metrics_path.resolve())],
                "parameters": {"selection": str(representative.resolve())},
            })
        trajectory_path = representative / "traj.xml"
        if trajectory_path.exists() and trajectory_path.stat().st_size > 0:
            output = staging_dir / "representative_trajectory.png"
            _trajectory_plot(trajectory_path, output)
            if EvidenceReader.validate(representative):
                raise ValueError("evidence changed while reading traj.xml")
            generated_names.append(output.name)
            entries.append({
                "file": output.name,
                "metric": "fcd_position",
                "sources": [str(trajectory_path.resolve())],
                "parameters": {
                    "selection": str(representative.resolve()),
                    "vehicle_limit": 200,
                },
            })
        for run_dir in frame["run_dir"]:
            if EvidenceReader.validate(Path(run_dir)):
                raise ValueError("evidence changed before aggregate publication")
        _write_manifest(
            staging_dir,
            entries,
            f"python -m visualization.report --input {root} --output {output_dir}",
        )
        _publish_figure_directory(staging_dir, output_dir)
        return [output_dir / name for name in generated_names]
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    generated = generate_matrix_figures(args.input, args.output)
    print(f"Generated {len(generated)} figures in {args.output}")


if __name__ == "__main__":
    main()
