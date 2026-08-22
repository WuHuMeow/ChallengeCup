import csv
import json
from pathlib import Path

import pandas as pd

from core.run_models import RunStatus
from core.types import MetricSummary
from engine.artifacts import RunArtifacts
from engine.events import EVENT_FIELDS
from experiments.evidence import (
    EvidenceWriter,
    RunManifest,
    canonical_mapping_sha256,
)
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
        artifacts = RunArtifacts.create(
            root,
            intersection,
            algorithm,
            1.0,
            42,
            run_id="run1",
        )
        source_hashes = {"net": "b" * 64, "sumocfg": "c" * 64}
        writer = EvidenceWriter(artifacts.run_dir)
        writer.begin(RunManifest(
            run_id=artifacts.run_id,
            code_commit="a" * 40,
            scene_manifest_sha256=canonical_mapping_sha256(source_hashes),
            algorithm=algorithm,
            parameters={},
            flow_multiplier=1.0,
            seed=42,
            duration_seconds=100.0,
            warmup_seconds=0.0,
            derived_steps=100,
            sumo_version="1.27.1",
            python_version="3.12.13",
            prediction_enabled=False,
            scene_id=intersection,
            scene_source_sha256=source_hashes,
            step_length=1.0,
            requested_seconds=100.0,
        ))
        with artifacts.metrics.open(
            "w", newline="", encoding="utf-8"
        ) as output:
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "step",
                    "timestamp",
                    "avg_queue_length",
                    "max_queue_length",
                ],
            )
            writer.writeheader()
            writer.writerows([
                {
                    "step": 0,
                    "timestamp": 0,
                    "avg_queue_length": 1,
                    "max_queue_length": 2,
                },
                {
                    "step": 10,
                    "timestamp": 10,
                    "avg_queue_length": 2,
                    "max_queue_length": 4,
                },
            ])
        artifacts.step_log.write_text(
            "step,timestamp,current_phase\n0,0,0\n10,10,0\n",
            encoding="utf-8",
        )
        with artifacts.events.open("w", newline="", encoding="utf-8") as output:
            csv.DictWriter(output, fieldnames=list(EVENT_FIELDS)).writeheader()
        artifacts.tripinfo.write_text(
            '<tripinfos><tripinfo id="v0" depart="0" '
            f'arrival="{value}" duration="{value}" timeLoss="{value / 2}" '
            f'waitingCount="10"><emissions fuel_abs="{value * 100}" '
            'CO2_abs="1000"/></tripinfo></tripinfos>',
            encoding="utf-8",
        )
        artifacts.stats.write_text("<summary/>", encoding="utf-8")
        artifacts.trajectory.write_text(
            "<fcd-export><timestep time='0'><vehicle id='v0' lane='E0_0' "
            "pos='1'/></timestep><timestep time='1'><vehicle id='v0' "
            "lane='E0_0' pos='5'/></timestep></fcd-export>",
            encoding="utf-8",
        )
        artifacts.collisions.write_text("<collisions/>", encoding="utf-8")
        summary = MetricSummary.from_raw_outputs(
            artifacts.run_dir,
            warmup_seconds=0.0,
        )
        writer = EvidenceWriter(artifacts.run_dir)
        writer.finalize(RunStatus.COMPLETED, summary)
        artifacts.write_status("queued", "")
        artifacts.write_status("starting", "")
        artifacts.write_status("running", "")
        artifacts.write_metadata(
            "completed",
            "",
            list(artifacts.run_dir.iterdir()),
            started_at="2026-08-22T00:00:00+00:00",
            ended_at="2026-08-22T00:01:40+00:00",
            sumo_version="1.27.1",
            requested_steps=100,
            requested_seconds=100.0,
            warmup_seconds=0.0,
            final_simulation_time=100.0,
            step_length=1.0,
        )
        writer.seal()
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
