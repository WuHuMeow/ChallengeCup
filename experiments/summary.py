"""Exact run-level metrics derived from completed SUMO artifacts."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from defusedxml import ElementTree as ET

from engine.artifacts import RunArtifacts
from core.types import MetricSummary


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


def metric_summary_payload(
    run_id: str,
    summary: MetricSummary,
    warmup_seconds: float,
) -> dict:
    """Return canonical metrics plus additive legacy consumer aliases."""
    metrics = asdict(summary)
    metrics.update({
        "avg_travel_time": summary.avg_travel_time_seconds,
        "avg_delay": summary.avg_delay_seconds,
        "avg_queue_length": summary.avg_queue_length_vehicles,
        "max_queue_length": summary.max_queue_length_vehicles,
        "fuel_consumption": summary.fuel_ml,
    })
    return {
        "schema": "challenge-cup.metric-summary",
        "schema_version": 1,
        "run_id": run_id,
        "warmup_seconds": float(warmup_seconds),
        "metrics": metrics,
        "units": {
            "completed_vehicle_count": "count",
            "unfinished_vehicle_count": "count",
            "throughput": "vehicles",
            "avg_travel_time_seconds": "s",
            "avg_delay_seconds": "s",
            "total_stops": "count",
            "fuel_ml": "ml",
            "co2_g": "g",
            "fuel_ml_per_completed": "ml/vehicle",
            "co2_g_per_completed": "g/vehicle",
            "avg_queue_length_vehicles": "vehicles",
            "max_queue_length_vehicles": "vehicles",
            **{f"{name}_count": "count" for name in summary.safety_counts},
        },
        "sources": {
            "travel": "tripinfo.xml",
            "queue": "metrics.csv",
            "safety": "events.csv",
        },
    }


def _atomic_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_run_summary(
    artifacts: RunArtifacts,
    warmup_seconds: float = 0.0,
    summary: MetricSummary | None = None,
) -> dict:
    """Write one provenance-bearing summary from exact and snapshot sources."""
    resolved = summary or MetricSummary.from_raw_outputs(
        artifacts.run_dir,
        warmup_seconds,
    )
    payload = metric_summary_payload(artifacts.run_id, resolved, warmup_seconds)
    _atomic_json(artifacts.summary, payload)
    return payload
