"""Exact run-level metrics derived from completed SUMO artifacts."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
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


def write_run_summary(artifacts: RunArtifacts) -> dict:
    """Write one provenance-bearing summary from exact and snapshot sources."""
    exact = parse_tripinfo(artifacts.tripinfo)
    metrics = asdict(exact)
    metrics.update(parse_queue_metrics(artifacts.metrics))
    payload = {
        "run_id": artifacts.run_id,
        "metrics": metrics,
        "sources": {
            "travel": artifacts.tripinfo.name,
            "queue": artifacts.metrics.name,
        },
    }
    artifacts.summary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload
