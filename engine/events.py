"""Event log writer for simulation lifecycle and control actions."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Canonical safety-event CSV schema shared by writers and strict readers.
EVENT_FIELDS = (
    "run_id",
    "intersection_id",
    "algorithm",
    "step",
    "simulation_seconds",
    "type",
    "entity_ids",
    "source",
    "confidence",
    "detail",
    "accepted",
    "action_value",
)


class EventLogger:
    """Buffer and write ``step,type,detail`` event rows."""

    def __init__(self, output_file: Path) -> None:
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self._rows: List[dict] = []

    @property
    def rows(self) -> List[dict]:
        """Return a copy of buffered rows for diagnostics."""
        return list(self._rows)

    def log(self, step: int, event_type: str, detail: str) -> None:
        self._rows.append({"step": step, "type": event_type, "detail": detail})

    def save(self) -> None:
        """Write all buffered rows, including a header for an empty log."""
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["step", "type", "detail"])
            writer.writeheader()
            writer.writerows(self._rows)
        logger.info("Saved %d events to %s", len(self._rows), self.output_file)
