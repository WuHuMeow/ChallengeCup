"""Fixed-time timing-plan resolution."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
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
                phases = tuple(
                    TimingPhase(
                        duration=phase.green_time + phase.yellow_time + phase.red_time,
                        state="",
                    )
                    for phase in timing.phases
                )
                self._validate_phases(phases)
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
        for phase in phases:
            if phase.duration <= 0:
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
