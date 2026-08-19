"""Validation and deterministic XML emitters for temporary SUMO disturbances."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from core.run_models import DisturbanceSpec

if TYPE_CHECKING:
    from core.run_models import VariantBundle


def _network_context(network_file: Path, target: str) -> tuple[str, str, float]:
    """Return the target edge, one reachable continuation, and lane length."""
    root = ET.parse(network_file).getroot()
    lane = next((node for node in root.findall(".//lane") if node.get("id") == target), None)
    if lane is None:
        raise ValueError(f"unknown disturbance lane: {target}")
    edge = target.rsplit("_", 1)[0]
    connection = next(
        (node for node in root.findall("connection") if node.get("from") == edge and node.get("to")),
        None,
    )
    if connection is None:
        raise ValueError(f"no reachable continuation for disturbance lane: {target}")
    return edge, connection.get("to"), float(lane.get("length", "1"))


def write_disturbance(
    spec: DisturbanceSpec,
    output_file: Path,
    *,
    network_file: Path,
) -> None:
    """Write one bounded additional file without mutating the parent scene."""
    root = ET.Element("additional")
    effective_end = spec.begin_seconds + (
        spec.end_seconds - spec.begin_seconds
    ) * min(spec.intensity, 1.0)
    interval = {"begin": f"{spec.begin_seconds:g}", "end": f"{effective_end:g}"}
    if spec.kind == "construction":
        edge, _, _ = _network_context(network_file, spec.target)
        rerouter = ET.SubElement(root, "rerouter", {"id": "construction_rerouter", "edges": edge})
        window = ET.SubElement(rerouter, "interval", interval)
        ET.SubElement(window, "closingLaneReroute", {"id": spec.target, "allow": "authority"})
    elif spec.kind == "event_demand":
        lane = next(
            (node for node in ET.parse(network_file).getroot().findall(".//lane")
             if node.get("id", "").rsplit("_", 1)[0] == spec.target),
            None,
        )
        if lane is None:
            raise ValueError(f"unknown disturbance edge: {spec.target}")
        target_lane = lane.get("id")
        edge, next_edge, _ = _network_context(network_file, target_lane)
        ET.SubElement(root, "vType", {"id": "event_demand_type", "vClass": "passenger", "maxSpeed": "13.89"})
        ET.SubElement(root, "route", {"id": "event_demand_route", "edges": f"{edge} {next_edge}"})
        calibrator = ET.SubElement(root, "calibrator", {"id": "event_demand_calibrator", "edge": edge, "pos": "0", "freq": "1"})
        ET.SubElement(calibrator, "flow", {**interval, "id": "event_demand", "vehsPerHour": f"{360 * spec.intensity:g}", "type": "event_demand_type", "route": "event_demand_route"})
    else:
        edge, next_edge, lane_length = _network_context(network_file, spec.target)
        ET.SubElement(root, "vType", {"id": "vehicle_failure_type", "vClass": "passenger", "maxSpeed": "13.89"})
        vehicle = ET.SubElement(root, "vehicle", {"id": "vehicle_failure", "type": "vehicle_failure_type", "depart": f"{spec.begin_seconds:g}"})
        ET.SubElement(vehicle, "route", {"edges": f"{edge} {next_edge}"})
        ET.SubElement(vehicle, "stop", {"lane": spec.target, "endPos": f"{max(1.0, lane_length * 0.7):g}", "duration": f"{max(1.0, effective_end - spec.begin_seconds):g}", "parking": "false"})
    ET.ElementTree(root).write(output_file, encoding="utf-8", xml_declaration=True)


def validate_variant(bundle: "VariantBundle") -> list[str]:
    """Return reproducibility and SUMO-input problems; an empty list is valid."""
    issues: list[str] = []
    names = bundle.manifest.get("additional_files", [])
    if len(names) != len(set(names)):
        issues.append("additional file conflict")
    inputs = [bundle.flow_file, bundle.route_file, bundle.sumo_cfg, bundle.network_file]
    if any(path is None or not path.exists() for path in inputs):
        issues.append("missing generated runtime input")
        return issues
    try:
        network_root = ET.parse(bundle.network_file).getroot()
        known_edges = {node.get("id") for node in network_root.findall("edge") if node.get("id")}
        known_lanes = {node.get("id") for node in network_root.findall(".//lane") if node.get("id")}
    except ET.ParseError:
        return [*issues, "invalid network XML"]
    try:
        config_root = ET.parse(bundle.sumo_cfg).getroot()
        route_files = config_root.find("./input/route-files")
        configured_routes = (
            [Path(value.strip()).name for value in route_files.get("value", "").split(",") if value.strip()]
            if route_files is not None else []
        )
        if configured_routes != [bundle.route_file.name]:
            issues.append("runtime route population must contain only the derived route file")
    except ET.ParseError:
        issues.append("invalid runtime SUMO config")
    roots: list[tuple[Path, ET.Element]] = []
    for path in [bundle.flow_file, bundle.route_file, *bundle.additional_files]:
        if not path.exists():
            issues.append(f"missing additional/runtime file: {path.name}")
            continue
        try:
            roots.append((path, ET.parse(path).getroot()))
        except ET.ParseError:
            issues.append(f"invalid XML: {path.name}")
    vtypes = {node.get("id") for _, root in roots for node in root.findall(".//vType") if node.get("id")}
    routes = {node.get("id") for _, root in roots for node in root.findall(".//route") if node.get("id")}
    demand_ids: list[str] = []
    for path, root in roots:
        for node in [*root.findall("flow"), *root.findall("vehicle")]:
            if node.get("id") and path != bundle.flow_file:
                demand_ids.append(node.get("id"))
            vehicle_type = node.get("type")
            if vehicle_type and vehicle_type not in vtypes:
                issues.append(f"unknown vehicle type: {vehicle_type}")
            route = node.get("route")
            if route and route not in routes:
                issues.append(f"missing route: {route}")
        for route in root.findall(".//route"):
            for edge in route.get("edges", "").split():
                if edge not in known_edges:
                    issues.append(f"unknown edge: {edge}")
        for node in root.findall(".//stop"):
            if node.get("lane") not in known_lanes:
                issues.append(f"inaccessible lane target: {node.get('lane')}")
        for interval in root.findall(".//interval"):
            try:
                if float(interval.get("end", "nan")) <= float(interval.get("begin", "nan")):
                    issues.append("invalid disturbance interval")
            except ValueError:
                issues.append("invalid disturbance interval")
    if len(demand_ids) != len(set(demand_ids)):
        issues.append("duplicate demand IDs")
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
