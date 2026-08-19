"""Event log writer for simulation lifecycle and control actions."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

EVENT_FIELDS = (
    "run_id",
    "intersection_id",
    "algorithm",
    "step",
    "type",
    "status",
    "reason",
    "accepted",
    "action_type",
    "action_value",
    "action_reason",
    "detail",
)

EVENT_ALGORITHM_NAMES = {
    "rule_adaptive": "actuated",
}


def contract_algorithm_name(internal_name: str) -> str:
    """Return the stable external algorithm name used by events.csv."""
    return EVENT_ALGORITHM_NAMES.get(internal_name, internal_name)


class EventLogger:
    """Buffer and write contextual, auditable event rows.

    The ``step``, ``type`` and ``detail`` columns remain available for older
    consumers.  The remaining columns make lifecycle and action outcomes
    machine-readable without parsing warning text.
    """

    def __init__(
        self,
        output_file: Path,
        *,
        run_id: str = "",
        intersection_id: str = "",
        algorithm: str = "",
    ) -> None:
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.intersection_id = intersection_id
        self.algorithm = contract_algorithm_name(algorithm)
        self._rows: List[dict] = []

    @property
    def rows(self) -> List[dict]:
        """Return a copy of buffered rows for diagnostics."""
        return list(self._rows)

    def log(
        self,
        step: int,
        event_type: str,
        detail: str = "",
        *,
        status: str | None = None,
        reason: str | None = None,
        action: object | None = None,
        accepted: bool | None = None,
    ) -> None:
        action_type = ""
        action_value = ""
        action_reason = ""
        if action is not None:
            action_type = str(getattr(action, "action_type", ""))
            action_value = json.dumps(
                getattr(action, "value", None),
                ensure_ascii=False,
                sort_keys=True,
            )
            action_reason = str(getattr(action, "reason", ""))
        if status is None and accepted is not None:
            status = "accepted" if accepted else "rejected"
        self._rows.append({
            "run_id": self.run_id,
            "intersection_id": self.intersection_id,
            "algorithm": self.algorithm,
            "step": step,
            "type": event_type,
            "status": status or "",
            "reason": reason if reason is not None else "",
            "accepted": "" if accepted is None else str(accepted).lower(),
            "action_type": action_type,
            "action_value": action_value,
            "action_reason": action_reason,
            "detail": detail,
        })

    def save(self) -> None:
        """Write all buffered rows, including a header for an empty log."""
        with open(self.output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(EVENT_FIELDS))
            writer.writeheader()
            writer.writerows(self._rows)
        logger.info("Saved %d events to %s", len(self._rows), self.output_file)
