"""Fixed-time timing-plan resolution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping
import xml.etree.ElementTree as ET

from core.types import Scene
from scenes.timing_loader import get_default_period_name, parse_timing_excel


class FixedTimePlanError(ValueError):
    """Raised when no legal fixed timing plan is available."""


@dataclass(frozen=True)
class ResolvedTimingPlan:
    """A selected, source-addressable timing program frozen before a run."""

    source_kind: str
    source_path: str
    source_sha256: str
    program_id: str
    phases: tuple["TimingPhase", ...]

    def as_manifest(self) -> dict[str, object]:
        return {
            "source_kind": self.source_kind,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "program_id": self.program_id,
        }


@dataclass(frozen=True)
class TimingPhase:
    duration: float
    state: str


@dataclass(frozen=True)
class _NetworkSignalModel:
    green_states: tuple[str, ...]
    yellow_states: tuple[str, ...]
    state_length: int
    approach_links: Mapping[str, tuple[int, ...]]


class FixedTimePlanResolver:
    """Resolve a legal plan without mutating any source input."""

    def resolve(self, scene: Scene) -> ResolvedTimingPlan:
        standardized = self._standardized_scene_path(scene)
        if standardized is not None:
            return self._from_standardized_file(standardized)

        excel_path = Path(scene.meta.timing_xlsx)
        if excel_path.is_file():
            try:
                periods = parse_timing_excel(excel_path)
                if not periods:
                    raise FixedTimePlanError(
                        f"official Excel contains no legal timing plan: {excel_path}"
                    )
                period_name = get_default_period_name(sorted(periods))
                timing = periods[period_name]
                self._validate_excel_phases(timing.phases)
                phases = self._excel_phases(
                    timing.phases,
                    self._network_signal_model(Path(scene.meta.sumo_net)),
                )
                self._validate_phases(phases, require_states=True)
                return self._resolved(
                    "official_excel",
                    excel_path,
                    f"excel:{period_name}",
                    phases,
                )
            except FixedTimePlanError:
                raise
            except Exception as exc:
                raise FixedTimePlanError(
                    f"invalid timing plan in official Excel {excel_path}: {exc}"
                ) from exc

        net_path = Path(scene.meta.sumo_net)
        if net_path.is_file():
            try:
                return self._from_network(net_path)
            except (ET.ParseError, OSError, FixedTimePlanError) as exc:
                raise FixedTimePlanError(
                    f"invalid timing plan in source network {net_path}: {exc}"
                ) from exc

        raise FixedTimePlanError("no legal timing plan is available for this scene")

    @staticmethod
    def _standardized_scene_path(scene: Scene) -> Path | None:
        for key in (
            "timing_plan",
            "fixed_time_plan",
            "standardized_timing_plan",
        ):
            candidate = scene.config.get(key)
            if candidate is None:
                continue
            if isinstance(candidate, Mapping):
                candidate = candidate.get("source_path")
            if not isinstance(candidate, (str, Path)):
                raise FixedTimePlanError(
                    f"invalid timing plan reference in scene.config[{key!r}]"
                )
            path = Path(candidate)
            if not path.is_file():
                raise FixedTimePlanError(
                    f"standardized timing plan does not exist: {path}"
                )
            return path
        return None

    def _from_standardized_file(self, path: Path) -> ResolvedTimingPlan:
        try:
            payload: Mapping[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            program_id = payload["program_id"]
            phases = tuple(
                TimingPhase(float(item["duration"]), str(item["state"]))
                for item in payload["phases"]
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise FixedTimePlanError(
                f"invalid standardized timing plan {path}: {exc}"
            ) from exc
        self._validate_program_id(program_id)
        self._validate_phases(phases, require_states=True)
        return self._resolved("standardized_scene", path, str(program_id), phases)

    def _from_network(self, path: Path) -> ResolvedTimingPlan:
        root = ET.parse(path).getroot()
        programs = sorted(
            root.findall("tlLogic"),
            key=lambda logic: (logic.get("id", ""), logic.get("programID", "")),
        )
        if not programs:
            raise FixedTimePlanError("network contains no tlLogic")
        program = programs[0]
        program_id = program.get("programID")
        phases = tuple(
            TimingPhase(float(phase.attrib["duration"]), phase.get("state", ""))
            for phase in program.findall("phase")
        )
        self._validate_program_id(program_id)
        self._validate_phases(phases, require_states=True)
        return self._resolved("source_net_xml", path, str(program_id), phases)

    def _network_signal_model(self, path: Path) -> _NetworkSignalModel:
        """Read source signal states and map controlled links to each approach."""
        root = ET.parse(path).getroot()
        programs = sorted(
            root.findall("tlLogic"),
            key=lambda logic: (logic.get("id", ""), logic.get("programID", "")),
        )
        if not programs:
            raise FixedTimePlanError("source network contains no tlLogic for Excel timing")
        states = [phase.get("state", "") for phase in programs[0].findall("phase")]
        if not states or any(not state for state in states):
            raise FixedTimePlanError("source network has no executable signal states")
        state_lengths = {len(state) for state in states}
        if len(state_lengths) != 1:
            raise FixedTimePlanError("source network signal states have inconsistent lengths")
        greens = [state for state in states if any(signal in state for signal in "Gg")]
        yellows = [state for state in states if any(signal in state for signal in "Yy")]
        if not greens or not yellows:
            raise FixedTimePlanError("source network lacks green or yellow signal states")
        state_length = state_lengths.pop()
        return _NetworkSignalModel(
            green_states=tuple(greens),
            yellow_states=tuple(yellows),
            state_length=state_length,
            approach_links=self._approach_link_indices(
                root,
                tls_id=programs[0].get("id", ""),
                state_length=state_length,
            ),
        )

    @classmethod
    def _approach_link_indices(
        cls,
        root: ET.Element,
        *,
        tls_id: str,
        state_length: int,
    ) -> dict[str, tuple[int, ...]]:
        edge_approaches: dict[str, str] = {}
        for edge in root.findall("edge"):
            edge_id = edge.get("id", "")
            if not edge_id or edge_id.startswith(":"):
                continue
            approach = cls._edge_approach(edge)
            if approach is not None:
                edge_approaches[edge_id] = approach

        grouped: dict[str, set[int]] = {}
        for connection in root.findall("connection"):
            if connection.get("tl") != tls_id:
                continue
            approach = edge_approaches.get(connection.get("from", ""))
            raw_index = connection.get("linkIndex")
            if approach is None or raw_index is None:
                continue
            try:
                link_index = int(raw_index)
            except ValueError as exc:
                raise FixedTimePlanError(
                    f"source network has an invalid signal link index: {raw_index}"
                ) from exc
            if not 0 <= link_index < state_length:
                raise FixedTimePlanError(
                    f"source network signal link index {link_index} is out of range"
                )
            grouped.setdefault(approach, set()).add(link_index)

        return {
            approach: tuple(sorted(indices))
            for approach, indices in grouped.items()
            if indices
        }

    @staticmethod
    def _edge_approach(edge: ET.Element) -> str | None:
        lane = edge.find("lane")
        shape = lane.get("shape", "") if lane is not None else ""
        try:
            points = [
                tuple(float(coordinate) for coordinate in point.split(",")[:2])
                for point in shape.split()
            ]
        except ValueError:
            return None
        if len(points) < 2:
            return None
        dx = points[-1][0] - points[0][0]
        dy = points[-1][1] - points[0][1]
        if abs(dx) >= abs(dy) and dx != 0:
            return "east" if dx < 0 else "west"
        if dy != 0:
            return "north" if dy < 0 else "south"
        return None

    @classmethod
    def _excel_phases(
        cls,
        excel_phases: list[object],
        signal_model: _NetworkSignalModel,
    ) -> tuple[TimingPhase, ...]:
        """Expand each Excel phase into green, yellow, and all-red SUMO phases."""
        ordered = sorted(excel_phases, key=lambda item: getattr(item, "phase_index"))
        coordinated = cls._coordinated_four_approach_phases(ordered, signal_model)
        if coordinated is not None:
            return coordinated

        expanded: list[TimingPhase] = []
        for position, phase in enumerate(ordered):
            green = float(getattr(phase, "green_time"))
            yellow = float(getattr(phase, "yellow_time"))
            all_red = float(getattr(phase, "red_time"))
            expanded.append(
                TimingPhase(
                    green,
                    signal_model.green_states[
                        position % len(signal_model.green_states)
                    ],
                )
            )
            if yellow > 0:
                expanded.append(
                    TimingPhase(
                        yellow,
                        signal_model.yellow_states[
                            position % len(signal_model.yellow_states)
                        ],
                    )
                )
            if all_red > 0:
                expanded.append(TimingPhase(all_red, "r" * signal_model.state_length))
        return tuple(expanded)

    @staticmethod
    def _coordinated_four_approach_phases(
        ordered_phases: list[object],
        signal_model: _NetworkSignalModel,
    ) -> tuple[TimingPhase, ...] | None:
        required_approaches = ("east", "west", "north", "south")
        if set(signal_model.approach_links) != set(required_approaches):
            return None

        east_west: list[object] = []
        north_south: list[object] = []
        for phase in ordered_phases:
            phase_name = str(getattr(phase, "phase_name", "")).replace(" ", "")
            if "东西" in phase_name:
                east_west.append(phase)
            elif "南北" in phase_name:
                north_south.append(phase)
            else:
                return None
        if len(east_west) != 2 or len(north_south) != 2:
            return None

        east_west_green = sum(
            float(getattr(phase, "green_time")) for phase in east_west
        ) / 2.0
        north_south_green = sum(
            float(getattr(phase, "green_time")) for phase in north_south
        ) / 2.0
        allocations = (
            ("east", east_west[0], east_west_green),
            ("west", east_west[1], east_west_green),
            ("north", north_south[0], north_south_green),
            ("south", north_south[1], north_south_green),
        )

        expanded: list[TimingPhase] = []
        for approach, source_phase, green in allocations:
            green_state = ["r"] * signal_model.state_length
            yellow_state = ["r"] * signal_model.state_length
            for link_index in signal_model.approach_links[approach]:
                green_state[link_index] = "G"
                yellow_state[link_index] = "y"
            expanded.append(TimingPhase(green, "".join(green_state)))

            yellow = float(getattr(source_phase, "yellow_time"))
            all_red = float(getattr(source_phase, "red_time"))
            if yellow > 0:
                expanded.append(TimingPhase(yellow, "".join(yellow_state)))
            if all_red > 0:
                expanded.append(
                    TimingPhase(all_red, "r" * signal_model.state_length)
                )
        return tuple(expanded)

    @staticmethod
    def _validate_program_id(program_id: object) -> None:
        if not isinstance(program_id, str) or not program_id.strip():
            raise FixedTimePlanError("timing plan has no program ID")

    @staticmethod
    def _validate_phases(
        phases: tuple[TimingPhase, ...], *, require_states: bool = False
    ) -> None:
        if not phases:
            raise FixedTimePlanError("timing plan contains no phases")
        state_lengths = {len(phase.state) for phase in phases if phase.state}
        if require_states and len(state_lengths) != 1:
            raise FixedTimePlanError("timing plan signal states have inconsistent lengths")
        for phase in phases:
            if not math.isfinite(phase.duration) or phase.duration <= 0:
                raise FixedTimePlanError("timing plan has a non-positive phase duration")
            if require_states and not phase.state:
                raise FixedTimePlanError("timing plan has a phase without signal state")

    @staticmethod
    def _validate_excel_phases(phases: list[object]) -> None:
        indices: set[int] = set()
        for phase in phases:
            phase_index = getattr(phase, "phase_index", None)
            green = getattr(phase, "green_time", None)
            yellow = getattr(phase, "yellow_time", None)
            all_red = getattr(phase, "red_time", None)
            if (
                not isinstance(phase_index, int)
                or phase_index < 0
                or phase_index in indices
                or not isinstance(green, (int, float))
                or green <= 0
                or not isinstance(yellow, (int, float))
                or yellow < 0
                or not isinstance(all_red, (int, float))
                or all_red < 0
            ):
                raise FixedTimePlanError("timing plan has an illegal Excel phase")
            indices.add(phase_index)

    @staticmethod
    def _resolved(
        source_kind: str,
        path: Path,
        program_id: str,
        phases: tuple[TimingPhase, ...],
    ) -> ResolvedTimingPlan:
        resolved_path = path.resolve()
        repository_root = Path(__file__).resolve().parents[1]
        try:
            portable_path = resolved_path.relative_to(repository_root).as_posix()
        except ValueError as exc:
            raise FixedTimePlanError(
                f"timing plan source is outside the repository: {resolved_path}"
            ) from exc
        return ResolvedTimingPlan(
            source_kind=source_kind,
            source_path=portable_path,
            source_sha256=sha256(resolved_path.read_bytes()).hexdigest(),
            program_id=program_id,
            phases=phases,
        )
