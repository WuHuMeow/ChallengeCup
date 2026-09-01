"""Immutable metadata produced by the SUMO scene preflight."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


def _readonly_mapping(values: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True)
class SceneManifest:
    """Traceable, read-only result of validating one SUMO scene source."""

    scene_id: str
    source_files: Mapping[str, str] = field(default_factory=dict)
    sha256: Mapping[str, str] = field(default_factory=dict)
    step_length: float = 1.0
    tls_ids: tuple[str, ...] = ()
    lane_ids: tuple[str, ...] = ()
    movement_count: int = 0
    validation_status: str = "fail"
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_files", _readonly_mapping(self.source_files))
        object.__setattr__(self, "sha256", _readonly_mapping(self.sha256))
        object.__setattr__(self, "tls_ids", tuple(self.tls_ids))
        object.__setattr__(self, "lane_ids", tuple(self.lane_ids))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    @property
    def intersection_id(self) -> str:
        """Compatibility display field for existing API consumers."""
        return self.scene_id

    @property
    def name(self) -> str:
        return f"路口_{self.scene_id}"

    @property
    def description(self) -> str:
        return f"雄安新区路口 {self.scene_id} 的 SUMO 仿真场景"
