import csv
import json
from unittest.mock import patch

import pytest

from core.types import JointState
from engine.artifacts import RunArtifacts
from engine.collector import MetricsCollector
from experiments.metrics import compute_metrics
from experiments.summary import parse_tripinfo, write_run_summary


def _write_tripinfo(path, rows):
    parts = ["<tripinfos>"]
    for index, row in enumerate(rows):
        emissions = row.pop("emissions", None)
        attributes = " ".join(f'{key}="{value}"' for key, value in row.items())
        if emissions is None:
            parts.append(f'<tripinfo id="v{index}" {attributes}/>')
        else:
            emission_attributes = " ".join(
                f'{key}="{value}"' for key, value in emissions.items()
            )
            parts.append(
                f'<tripinfo id="v{index}" {attributes}>'
                f"<emissions {emission_attributes}/></tripinfo>"
            )
    parts.append("</tripinfos>")
    path.write_text("".join(parts), encoding="utf-8")
    return path


def test_tripinfo_summary_uses_real_duration_delay_stops_and_fuel(tmp_path):
    path = _write_tripinfo(
        tmp_path / "tripinfo.xml",
        [
            {
                "duration": 100,
                "timeLoss": 20,
                "waitingCount": 2,
                "emissions": {"fuel_abs": 5},
            },
            {
                "duration": 140,
                "timeLoss": 40,
                "waitingCount": 4,
                "emissions": {"fuel_abs": 7},
            },
        ],
    )

    exact = parse_tripinfo(path)

    assert exact.avg_travel_time == 120
    assert exact.avg_delay == 30
    assert exact.total_stops == 6
    assert exact.fuel_consumption == 12
    assert exact.throughput == 2


def test_missing_exact_fields_are_null_not_zero(tmp_path):
    exact = parse_tripinfo(
        _write_tripinfo(tmp_path / "tripinfo.xml", [{}])
    )

    assert exact.avg_travel_time is None
    assert exact.avg_delay is None
    assert exact.total_stops is None
    assert exact.fuel_consumption is None
    assert exact.throughput == 1


def test_run_summary_combines_exact_tripinfo_and_queue_metrics(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    _write_tripinfo(
        artifacts.tripinfo,
        [{
            "depart": 0,
            "arrival": 60,
            "duration": 60,
            "timeLoss": 10,
            "waitingCount": 1,
            "emissions": {"fuel_abs": 2.5},
        }],
    )
    with artifacts.metrics.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["timestamp", "avg_queue_length", "max_queue_length"],
        )
        writer.writeheader()
        writer.writerows([
            {"timestamp": 0, "avg_queue_length": 2, "max_queue_length": 4},
            {"timestamp": 1, "avg_queue_length": 6, "max_queue_length": 9},
        ])

    payload = write_run_summary(artifacts)

    assert payload["run_id"] == artifacts.run_id
    assert payload["metrics"]["avg_queue_length"] == 4
    assert payload["metrics"]["max_queue_length"] == 9
    assert payload["metrics"]["avg_travel_time"] == 60
    assert json.loads(artifacts.summary.read_text(encoding="utf-8")) == payload


def test_instantaneous_metrics_do_not_fabricate_exact_fields():
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="phase_0",
        elapsed_phase_time=0.0,
        queues=[],
        flows={},
    )

    metrics = compute_metrics(0, state)

    assert metrics.avg_travel_time is None
    assert metrics.total_stops is None
    assert metrics.fuel_consumption is None


def test_metrics_collector_save_failure_preserves_previous_atomic_snapshot(tmp_path):
    output = tmp_path / "metrics.csv"
    output.write_text("previous-snapshot\n", encoding="utf-8")
    state = JointState(
        step=0,
        timestamp=0.0,
        tls_id="tls",
        current_phase=0,
        current_phase_name="phase_0",
        elapsed_phase_time=0.0,
        queues=[],
        flows={},
    )
    collector = MetricsCollector(output)
    collector.record(0, state, compute_metrics(0, state))

    with patch(
        "engine.collector.csv.DictWriter.writerows",
        side_effect=RuntimeError("csv write failed"),
    ):
        with pytest.raises(RuntimeError, match="csv write failed"):
            collector.save()

    assert output.read_text(encoding="utf-8") == "previous-snapshot\n"
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob(".*.tmp"))
