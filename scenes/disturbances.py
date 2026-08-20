"""Validation and deterministic XML emitters for temporary SUMO disturbances."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

from core.run_models import DisturbanceSpec

if TYPE_CHECKING:
    from core.run_models import VariantBundle

_SYMBOLIC_DEPARTURES = frozenset(
    {"triggered", "containerTriggered", "split", "begin"}
)


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
    scaled_interval = {
        "begin": f"{spec.begin_seconds:g}",
        "end": f"{effective_end:g}",
    }
    if spec.kind == "construction":
        edge, _, _ = _network_context(network_file, spec.target)
        rerouter = ET.SubElement(root, "rerouter", {"id": "construction_rerouter", "edges": edge})
        window = ET.SubElement(rerouter, "interval", scaled_interval)
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
        ET.SubElement(
            calibrator,
            "flow",
            {
                "begin": f"{spec.begin_seconds:g}",
                "end": f"{spec.end_seconds:g}",
                "id": "event_demand",
                "vehsPerHour": f"{360 * spec.intensity:g}",
                "type": "event_demand_type",
                "route": "event_demand_route",
            },
        )
    else:
        edge, next_edge, lane_length = _network_context(network_file, spec.target)
        ET.SubElement(root, "vType", {"id": "vehicle_failure_type", "vClass": "passenger", "maxSpeed": "13.89"})
        vehicle = ET.SubElement(root, "vehicle", {"id": "vehicle_failure", "type": "vehicle_failure_type", "depart": f"{spec.begin_seconds:g}"})
        ET.SubElement(vehicle, "route", {"edges": f"{edge} {next_edge}"})
        ET.SubElement(vehicle, "stop", {"lane": spec.target, "endPos": f"{max(1.0, lane_length * 0.7):g}", "duration": f"{max(1.0, effective_end - spec.begin_seconds):g}", "parking": "false"})
    ET.ElementTree(root).write(output_file, encoding="utf-8", xml_declaration=True)


def _configured_paths(node: ET.Element | None, config_file: Path) -> list[Path]:
    if node is None:
        return []
    return [
        (config_file.parent / value.strip()).resolve()
        for value in node.get("value", "").split(",")
        if value.strip()
    ]


def _validate_interval(
    node: ET.Element,
    issues: list[str],
    message: str,
) -> None:
    try:
        begin = float(node.get("begin", "nan"))
        end = float(node.get("end", "nan"))
        if (
            not math.isfinite(begin)
            or not math.isfinite(end)
            or begin < 0
            or end <= begin
        ):
            raise ValueError
    except (TypeError, ValueError):
        issues.append(message)


def _validate_route_edges(
    route: ET.Element,
    known_edges: set[str],
    connections: set[tuple[str, str]],
    issues: list[str],
) -> None:
    edges = route.get("edges", "").split()
    if not edges:
        issues.append("route has no edges")
        return
    for edge in edges:
        if edge not in known_edges:
            issues.append(f"unknown edge: {edge}")
    for left, right in zip(edges, edges[1:]):
        if (left, right) not in connections:
            issues.append(f"disconnected route edge pair: {left} -> {right}")


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
        connections = {
            (node.get("from"), node.get("to"))
            for node in network_root.findall("connection")
            if node.get("from") and node.get("to")
        }
    except (ET.ParseError, OSError):
        return [*issues, "invalid network XML"]
    try:
        config_root = ET.parse(bundle.sumo_cfg).getroot()
        net_file = config_root.find("./input/net-file")
        route_files = config_root.find("./input/route-files")
        configured_networks = _configured_paths(net_file, bundle.sumo_cfg)
        configured_routes = _configured_paths(route_files, bundle.sumo_cfg)
        if configured_networks != [bundle.network_file.resolve()]:
            issues.append("runtime network must reference the bundle network file")
        if configured_routes != [bundle.route_file.resolve()]:
            issues.append("runtime route population must contain only the derived route file")
        configured_additional = config_root.findall("./input/additional-files")
        if any(node.get("value", "").strip() for node in configured_additional):
            issues.append("configured additional-files would alter the runtime inputs")
    except (ET.ParseError, OSError):
        issues.append("invalid runtime SUMO config")
    roots: list[tuple[Path, ET.Element]] = []
    for path in [bundle.flow_file, bundle.route_file, *bundle.additional_files]:
        if not path.exists():
            issues.append(f"missing additional/runtime file: {path.name}")
            continue
        try:
            roots.append((path, ET.parse(path).getroot()))
        except (ET.ParseError, OSError):
            issues.append(f"invalid XML: {path.name}")
    runtime_roots = [
        (path, root)
        for path, root in roots
        if path.resolve() != bundle.flow_file.resolve()
    ]
    runtime_vtypes = {
        node.get("id")
        for _, root in runtime_roots
        for node in root.findall(".//vType")
        if node.get("id")
    }
    runtime_routes = {
        node.get("id")
        for _, root in runtime_roots
        for node in root.findall(".//route")
        if node.get("id")
    }
    intermediate_vtypes = {
        node.get("id")
        for path, root in roots
        if path.resolve() == bundle.flow_file.resolve()
        for node in root.findall(".//vType")
        if node.get("id")
    }
    intermediate_routes = {
        node.get("id")
        for path, root in roots
        if path.resolve() == bundle.flow_file.resolve()
        for node in root.findall(".//route")
        if node.get("id")
    }
    runtime_demand_ids: list[str] = []
    intermediate_demand_ids: list[str] = []
    for path, root in roots:
        is_runtime = path.resolve() != bundle.flow_file.resolve()
        vtypes = runtime_vtypes if is_runtime else intermediate_vtypes
        named_routes = runtime_routes if is_runtime else intermediate_routes
        calibrator_flows = set(root.findall(".//calibrator/flow"))
        for node in [*root.findall(".//flow"), *root.findall(".//vehicle")]:
            demand_id = node.get("id", "").strip()
            if not demand_id:
                issues.append("demand must have a non-empty demand ID")
            elif is_runtime:
                runtime_demand_ids.append(demand_id)
            else:
                intermediate_demand_ids.append(demand_id)
            vehicle_type = node.get("type")
            if vehicle_type and vehicle_type not in vtypes:
                issues.append(f"unknown vehicle type: {vehicle_type}")
            route_id = node.get("route")
            if route_id and route_id not in named_routes:
                issues.append(f"missing route: {route_id}")
            elif node in calibrator_flows and not route_id:
                issues.append("missing route for calibrator flow")
            if node.tag == "flow":
                if (
                    node in calibrator_flows
                    or node.get("begin") is not None
                    or node.get("end") is not None
                ):
                    _validate_interval(node, issues, "invalid demand interval")
                for name in ("from", "to"):
                    edge = node.get(name)
                    if edge and edge not in known_edges:
                        issues.append(f"unknown {name} edge: {edge}")
            else:
                raw_depart = node.get("depart", "")
                if raw_depart not in _SYMBOLIC_DEPARTURES:
                    try:
                        depart = float(raw_depart)
                        if not math.isfinite(depart) or depart < 0:
                            raise ValueError
                    except (TypeError, ValueError):
                        issues.append("invalid vehicle depart")
        for route in root.findall(".//route"):
            _validate_route_edges(route, known_edges, connections, issues)
        for rerouter in root.findall(".//rerouter"):
            rerouter_edges = rerouter.get("edges", "").split()
            if not rerouter_edges:
                issues.append("rerouter has no edges")
            for edge in rerouter_edges:
                if edge not in known_edges:
                    issues.append(f"unknown rerouter edge: {edge}")
        for calibrator in root.findall(".//calibrator"):
            edge = calibrator.get("edge")
            if edge not in known_edges:
                issues.append(f"unknown calibrator edge: {edge}")
        for closing in root.findall(".//closingLaneReroute"):
            lane = closing.get("id")
            if lane not in known_lanes:
                issues.append(f"inaccessible lane target: {lane}")
        for node in root.findall(".//stop"):
            if node.get("lane") not in known_lanes:
                issues.append(f"inaccessible lane target: {node.get('lane')}")
        for interval in root.findall(".//interval"):
            _validate_interval(interval, issues, "invalid disturbance interval")
    if (
        len(runtime_demand_ids) != len(set(runtime_demand_ids))
        or len(intermediate_demand_ids) != len(set(intermediate_demand_ids))
    ):
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
