import pytest

from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
from algorithms.classic_max_pressure import ClassicMaxPressureAlgorithm
from algorithms.fixed_time import FixedTimeAlgorithm
from algorithms.registry import (
    AlgorithmRegistry,
    AlgorithmSpec,
    get_algorithm_registry,
)
from algorithms.rule_adaptive import RuleAdaptiveAlgorithm


def test_formal_registry_has_exactly_three_algorithms():
    assert [item.key for item in get_algorithm_registry().list(formal_only=True)] == [
        "fixed_time",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    ]


def test_legacy_ca_name_resolves_without_being_public():
    registry = get_algorithm_registry()

    assert registry.get("ca_maxpressure").key == "capacity_aware_maxpressure"
    assert "ca_maxpressure" not in {
        item.key for item in registry.list(formal_only=True)
    }


def test_built_in_factories_keep_distinct_algorithm_identities():
    registry = get_algorithm_registry()

    assert isinstance(registry.get("fixed_time").factory(), FixedTimeAlgorithm)
    assert isinstance(
        registry.get("capacity_aware_maxpressure").factory(),
        CAMaxPressureAlgorithm,
    )
    assert isinstance(registry.get("actuated").factory(), RuleAdaptiveAlgorithm)
    assert isinstance(
        registry.get("classic_maxpressure").factory(),
        ClassicMaxPressureAlgorithm,
    )


def test_classic_is_explicitly_available_as_an_independent_baseline():
    classic = get_algorithm_registry().get("classic_maxpressure")

    assert classic.formal is True
    assert classic.available is True
    assert classic.unavailable_reason == ""


def test_registry_rejects_duplicate_aliases():
    registry = AlgorithmRegistry()
    registry.register(
        AlgorithmSpec("first", "First", FixedTimeAlgorithm, False, ("legacy",))
    )

    with pytest.raises(ValueError, match="legacy"):
        registry.register(
            AlgorithmSpec("second", "Second", FixedTimeAlgorithm, False, ("legacy",))
        )


def test_process_registry_is_read_only_after_builtin_registration():
    with pytest.raises(RuntimeError, match="read-only"):
        get_algorithm_registry().register(
            AlgorithmSpec("extra", "Extra", FixedTimeAlgorithm, False, ())
        )
