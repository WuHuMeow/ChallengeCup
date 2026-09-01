"""Canonical algorithm identities and construction for every runtime entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from algorithms.base import BaseControlAlgorithm
from algorithms.capacity_aware_max_pressure import CapacityAwareMaxPressureAlgorithm
from algorithms.classic_max_pressure import ClassicMaxPressureAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm


class AlgorithmUnavailableError(RuntimeError):
    """Raised when a registered identity has not been implemented yet."""


@dataclass(frozen=True)
class AlgorithmSpec:
    key: str
    display_name: str
    factory: Callable[..., BaseControlAlgorithm]
    formal: bool
    aliases: tuple[str, ...]
    available: bool = True
    unavailable_reason: str = ""


class AlgorithmRegistry:
    """Ordered registry with canonical and migration-only lookup keys."""

    def __init__(self) -> None:
        self._specs: dict[str, AlgorithmSpec] = {}
        self._lookup: dict[str, str] = {}
        self._read_only = False

    def register(self, spec: AlgorithmSpec) -> None:
        if self._read_only:
            raise RuntimeError("algorithm registry is read-only")
        if not spec.key or not spec.display_name:
            raise ValueError("algorithm key and display_name are required")
        names = (spec.key, *spec.aliases)
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate algorithm name in spec: {spec.key}")
        collision = next((name for name in names if name in self._lookup), None)
        if collision is not None:
            raise ValueError(f"algorithm name already registered: {collision}")
        if not spec.available and not spec.unavailable_reason:
            raise ValueError("unavailable algorithms require an unavailable_reason")
        self._specs[spec.key] = spec
        for name in names:
            self._lookup[name] = spec.key

    def get(self, key: str) -> AlgorithmSpec:
        try:
            return self._specs[self._lookup[key]]
        except KeyError as exc:
            raise KeyError(f"unknown algorithm: {key}") from exc

    def list(self, formal_only: bool = False) -> tuple[AlgorithmSpec, ...]:
        values = tuple(self._specs.values())
        if formal_only:
            return tuple(spec for spec in values if spec.formal)
        return values

    def freeze(self) -> None:
        self._read_only = True


def _build_registry() -> AlgorithmRegistry:
    registry = AlgorithmRegistry()
    registry.register(
        AlgorithmSpec("fixed_time", "Fixed Time", FixedTimeAlgorithm, True, ())
    )
    registry.register(
        AlgorithmSpec(
            "classic_maxpressure",
            "Classic MaxPressure",
            ClassicMaxPressureAlgorithm,
            True,
            (),
        )
    )
    registry.register(
        AlgorithmSpec(
            "capacity_aware_maxpressure",
            "Capacity-Aware MaxPressure",
            CapacityAwareMaxPressureAlgorithm,
            True,
            ("ca_maxpressure",),
        )
    )
    registry.register(
        AlgorithmSpec(
            "actuated",
            "Actuated Control",
            RuleAdaptiveAlgorithm,
            False,
            ("rule_adaptive",),
        )
    )
    registry.freeze()
    return registry


_REGISTRY = _build_registry()


def get_algorithm_registry() -> AlgorithmRegistry:
    """Return the process-wide read-only built-in registry."""
    return _REGISTRY


def canonicalize_algorithm_key(key: str) -> str:
    """Resolve a canonical key or a migration-only legacy alias."""
    return get_algorithm_registry().get(key).key
