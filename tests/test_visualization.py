import csv
import json
from pathlib import Path

import pandas as pd

from visualization.plots import plot_heatmap
from visualization.report import collect_summaries, generate_matrix_figures


def _write_summary_csv(path):
    frame = pd.DataFrame([
        {"intersection_id": "1", "algorithm": "fixed_time", "avg_travel_time": 20},
        {"intersection_id": "1", "algorithm": "ca_maxpressure", "avg_travel_time": 15},
        {"intersection_id": "2", "algorithm": "fixed_time", "avg_travel_time": 30},
        {"intersection_id": "2", "algorithm": "ca_maxpressure", "avg_travel_time": 21},
    ])
    frame.to_csv(path, index=False)
    return path


def _sample_matrix(root):
    for intersection, algorithm, value in [
        ("1", "fixed_time", 20.0),
        ("1", "ca_maxpressure", 15.0),
        ("2", "fixed_time", 30.0),
        ("2", "ca_maxpressure", 21.0),
    ]:
        run_dir = root / f"i{intersection}" / algorithm / "x1" / "s42" / "run1"
        run_dir.mkdir(parents=True)
        (run_dir / "summary.json").write_text(
            json.dumps({
                "run_id": f"{intersection}-{algorithm}",
                "metrics": {
                    "avg_travel_time": value,
                    "avg_delay": value / 2,
                    "avg_queue_length": value / 10,
                    "max_queue_length": value / 5,
                    "throughput": 100,
                    "total_stops": 10,
                    "fuel_consumption": value * 100,
                },
                "sources": {"travel": "tripinfo.xml", "queue": "metrics.csv"},
            }),
            encoding="utf-8",
        )
        (run_dir / "run_metadata.json").write_text(
            json.dumps({
                "run_id": f"{intersection}-{algorithm}",
                "intersection_id": intersection,
                "algorithm": algorithm,
                "flow_multiplier": 1.0,
                "seed": 42,
                "status": "completed",
            }),
            encoding="utf-8",
        )
        with (run_dir / "metrics.csv").open(
            "w", newline="", encoding="utf-8"
        ) as output:
            writer = csv.DictWriter(
                output,
                fieldnames=["step", "avg_queue_length", "max_queue_length"],
            )
            writer.writeheader()
            writer.writerows([
                {"step": 0, "avg_queue_length": 1, "max_queue_length": 2},
                {"step": 10, "avg_queue_length": 2, "max_queue_length": 4},
            ])
        (run_dir / "tripinfo.xml").write_text("<tripinfos/>", encoding="utf-8")
        (run_dir / "traj.xml").write_text(
            "<fcd-export><timestep time='0'><vehicle id='v0' lane='E0_0' "
            "pos='1'/></timestep><timestep time='1'><vehicle id='v0' "
            "lane='E0_0' pos='5'/></timestep></fcd-export>",
            encoding="utf-8",
        )
    return root


def test_heatmap_pivots_intersection_by_algorithm(tmp_path):
    csv_path = _write_summary_csv(tmp_path / "summaries.csv")
    output = tmp_path / "heatmap.png"

    plot_heatmap(csv_path, output, metric="avg_travel_time")

    assert output.exists()
    assert output.stat().st_size > 1000


def test_collect_summaries_reads_run_identity_and_exact_metrics(tmp_path):
    frame = collect_summaries(_sample_matrix(tmp_path / "matrix"))

    assert len(frame) == 4
    assert set(frame["intersection_id"].astype(str)) == {"1", "2"}
    assert set(frame["algorithm"]) == {"fixed_time", "ca_maxpressure"}
    assert "avg_travel_time" in frame.columns
    assert all(Path(path).is_file() for path in frame["summary_path"])


def test_every_figure_has_provenance_manifest(tmp_path):
    matrix = _sample_matrix(tmp_path / "matrix")
    output_dir = tmp_path / "figures"

    generated = generate_matrix_figures(matrix, output_dir)

    manifest = json.loads(
        (output_dir / "manifest.json").read_text(encoding="utf-8")
    )
    assert {path.name for path in generated} == {
        item["file"] for item in manifest["figures"]
    }
    assert {
        "algorithm_avg_travel_time.png",
        "intersection_avg_travel_time_heatmap.png",
        "representative_queue_timeseries.png",
        "representative_trajectory.png",
    } <= {path.name for path in generated}
    assert all(item["sources"] for item in manifest["figures"])
    assert all(
        Path(source).exists()
        for item in manifest["figures"]
        for source in item["sources"]
    )
