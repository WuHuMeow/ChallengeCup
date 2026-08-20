"""Static positive-capacity validation for capacity-aware control runs."""

from __future__ import annotations

import math
from pathlib import Path
import xml.etree.ElementTree as ET


CAPACITY_SPACING_M = 7.5


def validate_capacity_aware_scene(net_path: Path) -> None:
    """Reject controlled movement lanes without positive static capacity."""
    root = ET.parse(net_path).getroot()
    lane_lengths = {
        lane.get("id"): lane.get("length")
        for lane in root.findall(".//lane")
        if lane.get("id") is not None
    }
    invalid: list[str] = []
    for connection in root.findall("connection"):
        if not connection.get("tl"):
            continue
        for edge_attr, lane_attr in (("from", "fromLane"), ("to", "toLane")):
            edge_id = connection.get(edge_attr)
            lane_index = connection.get(lane_attr)
            if edge_id is None or lane_index is None:
                continue
            lane_id = f"{edge_id}_{lane_index}"
            try:
                capacity = float(lane_lengths.get(lane_id)) / CAPACITY_SPACING_M
            except (TypeError, ValueError):
                capacity = 0.0
            if not math.isfinite(capacity) or capacity <= 0:
                invalid.append(lane_id)
    if invalid:
        raise ValueError(
            "capacity-aware preflight requires positive movement capacity for lanes: "
            + ", ".join(dict.fromkeys(invalid))
        )
