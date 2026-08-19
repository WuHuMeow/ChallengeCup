"""Read-only structural preflight for official SUMO scene inputs."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from scenes.models import SceneManifest
from scenes.timing_loader import parse_timing_excel


class SceneValidationError(ValueError):
    """Raised by callers that require a usable, formal scene."""


class SceneValidator:
    """Validate a scene without modifying any file below its source root."""

    _REQUIRED = ("net", "flow", "route", "turn", "sumocfg", "timing", "map")
    _SUMO_SUFFIXES = {
        "net": ".net.xml",
        "flow": ".flow.xml",
        "route": ".rou.xml",
        "turn": ".turn.xml",
        "sumocfg": ".sumocfg",
    }

    def __init__(self, repository_root: Path | str | None = None) -> None:
        self.repository_root = (
            Path(repository_root).resolve() if repository_root is not None else self._find_repository_root()
        )

    @staticmethod
    def _find_repository_root() -> Path:
        for candidate in (Path.cwd().resolve(), *Path.cwd().resolve().parents):
            if (candidate / ".git").exists():
                return candidate
        return Path.cwd().resolve()

    def validate(self, scene_root: Path) -> SceneManifest:
        """Return a manifest. Structural errors are represented as ``fail`` warnings."""
        root = Path(scene_root).resolve()
        scene_id = root.name
        warnings: list[str] = []
        files = self._discover_files(root, warnings)
        sha256 = {key: self._sha256(path) for key, path in files.items()}
        source_files = {key: self._relative_path(path) for key, path in files.items()}

        parsed = self._parse_xml_inputs(files, warnings)
        step_length = self._step_length(parsed.get("sumocfg"), warnings)
        tls_ids, lane_ids, movement_count = self._validate_network(
            parsed.get("net"), warnings
        )
        self._validate_routes(parsed.get("net"), parsed.get("flow"), parsed.get("route"), warnings)
        self._validate_turns(parsed.get("net"), parsed.get("turn"), warnings)
        self._validate_sumocfg(parsed.get("sumocfg"), files, warnings)
        self._validate_timing(files.get("timing"), warnings)

        status = "pass" if not warnings else "fail"
        # These source-layout omissions are known warnings, not structural failure.
        errors = [warning for warning in warnings if not warning.startswith("source warning:")]
        if not errors:
            status = "pass"
        return SceneManifest(
            scene_id=scene_id,
            source_files=source_files,
            sha256=sha256,
            step_length=step_length,
            tls_ids=tls_ids,
            lane_ids=lane_ids,
            movement_count=movement_count,
            validation_status=status,
            warnings=tuple(warnings),
        )

    def _discover_files(self, root: Path, warnings: list[str]) -> dict[str, Path]:
        files: dict[str, Path] = {}
        sumo_dir = root / "sumo工程"
        prefix = f"demo_{root.name}"
        for key, suffix in self._SUMO_SUFFIXES.items():
            expected = sumo_dir / f"{prefix}{suffix}"
            matches = [expected] if expected.is_file() else sorted(sumo_dir.glob(f"*{suffix}")) if sumo_dir.exists() else []
            if len(matches) == 1:
                files[key] = matches[0]
            elif not matches:
                warnings.append(f"missing required {key} input")
            else:
                warnings.append(f"ambiguous {key} input")

        timing_dir = root / "路口数据"
        timings = sorted(timing_dir.glob("*.xlsx")) if timing_dir.exists() else []
        if len(timings) == 1:
            files["timing"] = timings[0]
        elif not timings:
            warnings.append("missing required timing input")
        else:
            warnings.append("ambiguous timing input")

        map_dirs = [root / name for name in ("高精地图", "高清地图") if (root / name).is_dir()]
        maps = [path for directory in map_dirs for path in sorted(directory.glob("*.png"))]
        if len(maps) == 1:
            files["map"] = maps[0]
        elif not maps:
            warnings.append("missing required map input")
        else:
            warnings.append("ambiguous map input")
        return files

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _relative_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repository_root).as_posix()
        except ValueError:
            return path.resolve().as_posix()

    @staticmethod
    def _parse_xml_inputs(files: dict[str, Path], warnings: list[str]) -> dict[str, ET.Element]:
        parsed: dict[str, ET.Element] = {}
        for key in ("net", "flow", "route", "turn", "sumocfg"):
            path = files.get(key)
            if path is None:
                continue
            try:
                parsed[key] = ET.parse(path).getroot()
            except (ET.ParseError, OSError) as exc:
                warnings.append(f"invalid {key} XML: {exc}")
        return parsed

    @staticmethod
    def _step_length(config: ET.Element | None, warnings: list[str]) -> float:
        if config is None:
            return 1.0
        element = config.find(".//step-length")
        if element is None:
            return 1.0  # SUMO's documented default.
        raw = element.get("value", element.text or "")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            warnings.append("invalid step-length")
            return 1.0
        if not math.isfinite(value) or value <= 0:
            warnings.append("invalid step-length")
            return 1.0
        return value

    @staticmethod
    def _validate_network(net: ET.Element | None, warnings: list[str]) -> tuple[tuple[str, ...], tuple[str, ...], int]:
        if net is None:
            warnings.append("missing controlled movement mapping")
            return (), (), 0
        edge_lanes: dict[str, dict[str, str]] = {}
        lane_ids: list[str] = []
        for edge in net.findall("edge"):
            edge_id = edge.get("id")
            if not edge_id:
                continue
            edge_lanes[edge_id] = {}
            for lane in edge.findall("lane"):
                lane_id = lane.get("id")
                index = lane.get("index")
                if lane_id:
                    lane_ids.append(lane_id)
                    edge_lanes[edge_id][index if index is not None else lane_id.rsplit("_", 1)[-1]] = lane_id
        tls = net.findall("tlLogic")
        tls_ids = tuple(sorted(tls_id for tls_id in (tls_item.get("id") for tls_item in tls) if tls_id))
        tls_set = set(tls_ids)
        if not tls_ids:
            warnings.append("missing TLS program")
        for program in tls:
            phases = program.findall("phase")
            if not phases:
                warnings.append(f"TLS {program.get('id', '<unknown>')} has no phases")
            for phase in phases:
                try:
                    duration = float(phase.get("duration", ""))
                    if not math.isfinite(duration) or duration <= 0:
                        raise ValueError
                except ValueError:
                    warnings.append(f"TLS {program.get('id', '<unknown>')} has invalid phase duration")

        movements = 0
        for connection in net.findall("connection"):
            tls_id = connection.get("tl")
            from_edge, to_edge = connection.get("from"), connection.get("to")
            from_lane, to_lane = connection.get("fromLane"), connection.get("toLane")
            if tls_id is None:
                continue
            if tls_id not in tls_set:
                warnings.append(f"controlled connection references unknown TLS {tls_id}")
                continue
            if (
                from_edge not in edge_lanes
                or to_edge not in edge_lanes
                or from_lane not in edge_lanes[from_edge]
                or to_lane not in edge_lanes[to_edge]
            ):
                warnings.append("controlled movement has invalid incoming/outgoing lane reference")
                continue
            movements += 1
        if movements == 0:
            warnings.append("missing controlled movement mapping")
        return tls_ids, tuple(sorted(lane_ids)), movements

    @staticmethod
    def _connections(net: ET.Element | None) -> set[tuple[str, str]]:
        if net is None:
            return set()
        return {
            (connection.get("from"), connection.get("to"))
            for connection in net.findall("connection")
            if connection.get("from") and connection.get("to")
        }

    @classmethod
    def _validate_routes(cls, net: ET.Element | None, flow: ET.Element | None, route: ET.Element | None, warnings: list[str]) -> None:
        if net is None:
            return
        edges = {edge.get("id") for edge in net.findall("edge") if edge.get("id")}
        connections = cls._connections(net)
        vtypes = {
            vtype.get("id")
            for root in (flow, route)
            if root is not None
            for vtype in root.findall("vType")
            if vtype.get("id")
        }
        if flow is not None:
            for item in list(flow.findall("flow")) + list(flow.findall("vehicle")):
                item_type = item.get("type")
                if item_type and item_type not in vtypes:
                    warnings.append(f"flow references unknown vehicle type {item_type}")
                for attr in ("from", "to"):
                    edge = item.get(attr)
                    if edge and edge not in edges:
                        warnings.append(f"flow references unknown edge {edge}")
        if route is not None:
            named_routes = {
                route_element.get("id"): route_element
                for route_element in route.findall("route")
                if route_element.get("id")
            }
            for vehicle in route.findall("vehicle"):
                item_type = vehicle.get("type")
                if item_type and item_type not in vtypes:
                    warnings.append(f"route references unknown vehicle type {item_type}")
                route_element = vehicle.find("route")
                if route_element is not None:
                    cls._validate_route_edges(route_element.get("edges", ""), edges, connections, warnings)
                elif vehicle.get("route") not in named_routes:
                    warnings.append(
                        f"vehicle references unknown named route {vehicle.get('route', '')}"
                    )
            for route_element in route.findall("route"):
                cls._validate_route_edges(route_element.get("edges", ""), edges, connections, warnings)

    @staticmethod
    def _validate_route_edges(raw_edges: str, edges: set[str], connections: set[tuple[str, str]], warnings: list[str]) -> None:
        route_edges = raw_edges.split()
        if not route_edges:
            warnings.append("route has no edges")
            return
        if any(edge not in edges for edge in route_edges):
            warnings.append("route references unknown edge")
        if any((left, right) not in connections for left, right in zip(route_edges, route_edges[1:])):
            warnings.append("route contains disconnected edges")

    @classmethod
    def _validate_turns(cls, net: ET.Element | None, turns: ET.Element | None, warnings: list[str]) -> None:
        if net is None or turns is None:
            return
        edges = {edge.get("id") for edge in net.findall("edge") if edge.get("id")}
        connections = cls._connections(net)
        for relation in turns.findall(".//edgeRelation"):
            source, target = relation.get("from"), relation.get("to")
            if source not in edges or target not in edges:
                warnings.append("turn relation references unknown edge")
            elif (source, target) not in connections:
                warnings.append("turn relation has no network connection")

    @staticmethod
    def _validate_sumocfg(config: ET.Element | None, files: dict[str, Path], warnings: list[str]) -> None:
        if config is None:
            return
        input_root = config.find("input")
        if input_root is None:
            warnings.append("sumocfg has no input section")
            return
        net_file = input_root.find("net-file")
        if net_file is None or net_file.get("value") != files.get("net", Path()).name:
            warnings.append("sumocfg does not reference its network")
        route_files = input_root.find("route-files")
        if route_files is None or files.get("route", Path()).name not in route_files.get("value", "").split(","):
            warnings.append("sumocfg does not reference its route input")
        configured = " ".join(element.get("value", "") for element in input_root)
        for key in ("flow", "turn"):
            path = files.get(key)
            if path is not None and path.name not in configured:
                warnings.append(f"source warning: sumocfg does not explicitly reference {key} input")

    @staticmethod
    def _validate_timing(path: Path | None, warnings: list[str]) -> None:
        if path is None:
            return
        try:
            if not parse_timing_excel(path):
                warnings.append("timing workbook has no timing plans")
        except (OSError, ValueError, ImportError, IndexError, KeyError) as exc:
            warnings.append(f"invalid timing workbook: {exc}")
