"""Validation and deterministic XML emitters for temporary SUMO disturbances."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from core.run_models import DisturbanceSpec

if TYPE_CHECKING:
    from core.run_models import VariantBundle


def write_disturbance(spec: DisturbanceSpec, output_file: Path) -> None:
    """Write one bounded additional file without mutating the parent scene."""
    root = ET.Element("additional")
    interval = {"begin": f"{spec.begin_seconds:g}", "end": f"{spec.end_seconds:g}"}
    if spec.kind == "construction":
        rerouter = ET.SubElement(root, "rerouter", {"id": "construction_rerouter", "edges": spec.target.rsplit("_", 1)[0]})
        window = ET.SubElement(rerouter, "interval", interval)
        ET.SubElement(window, "closingLaneReroute", {"id": spec.target, "allow": "authority"})
    elif spec.kind == "event_demand":
        # A calibrator raises deterministic entrance demand only during the event.
        ET.SubElement(root, "route", {"id": "event_demand_route", "edges": spec.target})
        calibrator = ET.SubElement(root, "calibrator", {"id": "event_demand_calibrator", "edge": spec.target, "pos": "0", "freq": "1"})
        ET.SubElement(calibrator, "flow", {**interval, "id": "event_demand", "vehsPerHour": f"{1000 * spec.intensity:g}", "type": "passenger", "route": "event_demand_route"})
    else:
        rerouter = ET.SubElement(root, "rerouter", {"id": "vehicle_failure_rerouter", "edges": spec.target.rsplit("_", 1)[0]})
        window = ET.SubElement(rerouter, "interval", interval)
        # Block the selected lane only; this intentionally creates no vehicle collision.
        ET.SubElement(window, "closingLaneReroute", {"id": spec.target, "allow": "authority"})
    ET.ElementTree(root).write(output_file, encoding="utf-8", xml_declaration=True)


def validate_variant(bundle: "VariantBundle") -> list[str]:
    """Return reproducibility and SUMO-input problems; an empty list is valid."""
    issues: list[str] = []
    names = bundle.manifest.get("additional_files", [])
    if len(names) != len(set(names)):
        issues.append("additional file conflict")
    flow_file = bundle.flow_file
    if flow_file is None or not flow_file.exists():
        issues.append("missing generated flow file")
        return issues
    try:
        flow_root = ET.parse(flow_file).getroot()
    except ET.ParseError:
        return [*issues, "invalid generated flow XML"]
    flow_ids = [node.get("id") for node in flow_root.findall("flow")]
    present_ids = [flow_id for flow_id in flow_ids if flow_id]
    if len(present_ids) != len(set(present_ids)):
        issues.append("duplicate demand IDs")
    for flow in flow_root.findall("flow"):
        if flow.get("route") == "":
            issues.append("missing route")
            break
    disturbance = bundle.manifest.get("disturbance")
    if isinstance(disturbance, dict):
        begin, end = disturbance.get("begin_seconds"), disturbance.get("end_seconds")
        if not isinstance(begin, (int, float)) or not isinstance(end, (int, float)) or end <= begin:
            issues.append("invalid disturbance interval")
        target = disturbance.get("target")
        lane_ids = set(bundle.manifest.get("lane_ids", []))
        if isinstance(target, str) and "_" in target and lane_ids and target not in lane_ids:
            issues.append("inaccessible lane target")
    return issues
