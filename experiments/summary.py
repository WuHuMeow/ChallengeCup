"""Exact run-level metrics derived from completed SUMO artifacts."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from defusedxml import ElementTree as ET

from engine.artifacts import RunArtifacts


@dataclass(frozen=True)
class ExactMetrics:
    avg_travel_time: float | None
    avg_delay: float | None
    avg_queue_length: float | None
    max_queue_length: float | None
    throughput: int
    total_stops: int | None
    fuel_consumption: float | None


def _complete_values(rows: list[object], attribute: str) -> list[float] | None:
    values = []
    for row in rows:
        raw = row.get(attribute)
        if raw is None:
            return None
        try:
            values.append(float(raw))
        except ValueError:
            return None
    return values or None


def parse_tripinfo(path: Path) -> ExactMetrics:
    """Parse only exact vehicle-level measurements; never synthesize zeroes."""
    root = ET.parse(path).getroot()
    rows = list(root.iter("tripinfo"))
    durations = _complete_values(rows, "duration")
    delays = _complete_values(rows, "timeLoss")
    stops = _complete_values(rows, "waitingCount")

    fuels = []
    for row in rows:
        raw = row.get("fuel_abs")
        emissions = row.find("emissions")
        if raw is None and emissions is not None:
            raw = emissions.get("fuel_abs")
        if raw is None:
            fuels = None
            break
        try:
            fuels.append(float(raw))
        except ValueError:
            fuels = None
            break

    return ExactMetrics(
        avg_travel_time=(
            sum(durations) / len(durations) if durations is not None else None
        ),
        avg_delay=sum(delays) / len(delays) if delays is not None else None,
        avg_queue_length=None,
        max_queue_length=None,
        throughput=len(rows),
        total_stops=int(sum(stops)) if stops is not None else None,
        fuel_consumption=sum(fuels) if fuels else None,
    )


def parse_queue_metrics(path: Path) -> dict[str, float | None]:
    """Aggregate queue snapshots written by MetricsCollector."""
    if not path.exists() or path.stat().st_size == 0:
        return {"avg_queue_length": None, "max_queue_length": None}
    averages = []
    maximums = []
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            try:
                if row.get("avg_queue_length", "") != "":
                    averages.append(float(row["avg_queue_length"]))
                if row.get("max_queue_length", "") != "":
                    maximums.append(float(row["max_queue_length"]))
            except ValueError:
                continue
    return {
        "avg_queue_length": (
            sum(averages) / len(averages) if averages else None
        ),
        "max_queue_length": max(maximums) if maximums else None,
    }


SUMMARY_SCHEMA = "challenge-cup-run-summary"
SUMMARY_SCHEMA_VERSION = 1


def metric_summary_payload(run_id: str, summary, warmup_seconds: float) -> dict:
    """Canonical, reader-verifiable serialization of one MetricSummary."""
    metrics: dict[str, object] = {
        "completed_vehicle_count": int(summary.completed_vehicle_count),
        "unfinished_vehicle_count": int(summary.unfinished_vehicle_count),
        "throughput": int(summary.throughput),
        "avg_travel_time_seconds": summary.avg_travel_time_seconds,
        "avg_delay_seconds": summary.avg_delay_seconds,
        "avg_queue_length_vehicles": summary.avg_queue_length_vehicles,
        "max_queue_length_vehicles": summary.max_queue_length_vehicles,
        "total_stops": (
            int(summary.total_stops) if summary.total_stops is not None else None
        ),
        "fuel_ml": summary.fuel_ml,
        "co2_g": summary.co2_g,
        "fuel_ml_per_completed": summary.fuel_ml_per_completed,
        "co2_g_per_completed": summary.co2_g_per_completed,
    }
    for name in (
        "collision",
        "red_light",
        "illegal_transition",
        "harsh_braking",
        "teleport",
        "potential_conflict",
    ):
        metrics[f"{name}_count"] = int(summary.safety_counts.get(name, 0))
    # Legacy alias keys keep older analysis scripts working; strict readers
    # treat the canonical *_seconds/_ml/_g keys as authoritative.
    metrics["avg_travel_time"] = summary.avg_travel_time_seconds
    metrics["avg_delay"] = summary.avg_delay_seconds
    metrics["avg_queue_length"] = summary.avg_queue_length_vehicles
    metrics["max_queue_length"] = summary.max_queue_length_vehicles
    metrics["fuel_consumption"] = summary.fuel_ml
    return {
        "schema": SUMMARY_SCHEMA,
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "warmup_seconds": float(warmup_seconds),
        "metrics": metrics,
        "units": {
            "time_seconds": "s",
            "queue_vehicles": "veh",
            "fuel_ml": "ml",
            "co2_g": "g",
            "counts": "veh_or_events",
            "avg_travel_time_seconds": "s",
            "avg_travel_time": "s",
            "avg_delay": "s",
            "avg_queue_length": "vehicles",
            "max_queue_length": "vehicles",
            "fuel_consumption": "ml",
        },
        "sources": {
            "travel_time": "tripinfo.xml",
            "delay": "tripinfo.xml",
            "stops": "tripinfo.xml",
            "fuel": "tripinfo.xml",
            "co2": "tripinfo.xml",
            "queue": "metrics.csv",
            "safety_events": "events.csv",
        },
    }


def write_run_summary(
    artifacts: RunArtifacts,
    warmup_seconds: float = 600.0,
) -> dict:
    """Write one canonical summary derived from raw outputs, atomically."""
    from core.types import MetricSummary

    summary = MetricSummary.from_raw_outputs(artifacts.run_dir, warmup_seconds)
    payload = metric_summary_payload(artifacts.run_id, summary, warmup_seconds)
    temporary = artifacts.summary.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(artifacts.summary)
    return payload
