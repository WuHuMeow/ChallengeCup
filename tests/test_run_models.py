from dataclasses import replace
from pathlib import Path

import pytest

from core.run_models import RunRequest, RunStatus, SUPPORTED_ALGORITHMS, VariantSpec
from core.timebase import SimulationWindow
from engine.run_service import RunService


def test_run_request_defaults_to_seconds_without_hidden_step_count():
    request = RunRequest(intersection_id="1", algorithm="fixed_time")

    assert request.duration_seconds == 3600
    assert request.warmup_seconds == 600
    assert request.step_length_override is None
    assert request.steps is None
    assert request.flow_multiplier == 1.0
    assert request.seed == 42
    assert request.output_root is None
    assert request.variant == VariantSpec()


def test_run_request_derives_compatibility_steps_only_from_explicit_step_length():
    request = RunRequest(
        intersection_id="1",
        algorithm="fixed_time",
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )

    assert request.steps == 36000


def test_replacing_compatibility_request_preserves_declared_warmup():
    request = RunRequest(
        intersection_id="1",
        algorithm="fixed_time",
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )

    replaced = replace(request, seed=43)

    assert RunService._window(replaced, 0.1) == SimulationWindow(3600, 600)


@pytest.mark.parametrize(
    ("replacement_steps", "expected_window"),
    [
        (100, SimulationWindow(10, 0)),
        (36000, SimulationWindow(3600, 0)),
    ],
    ids=("different-value", "same-value-plain-int"),
)
def test_replacing_compatibility_steps_with_plain_int_makes_them_explicit(
    replacement_steps, expected_window
):
    request = RunRequest(
        intersection_id="1",
        algorithm="fixed_time",
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )

    replaced = replace(request, steps=replacement_steps)

    assert request.steps == 36000
    assert RunService._window(replaced, 0.1) == expected_window


def test_run_request_keeps_explicit_steps_for_smoke_compatibility():
    request = RunRequest(intersection_id="1", algorithm="fixed_time", steps=100)

    assert request.steps == 100
    assert request.duration_seconds == 3600


def test_run_status_values_are_stable():
    assert [item.value for item in RunStatus] == [
        "queued",
        "starting",
        "running",
        "stopping",
        "completed",
        "stopped",
        "ended_early",
        "disconnected",
        "interrupted",
        "failed",
    ]


def test_run_request_accepts_explicit_output_root(tmp_path):
    request = RunRequest(
        intersection_id="16",
        algorithm="capacity_aware_maxpressure",
        output_root=tmp_path,
    )

    assert request.output_root == Path(tmp_path)
    assert request.algorithm == "capacity_aware_maxpressure"


def test_new_run_request_rejects_migration_only_algorithm_aliases():
    with pytest.raises(ValueError, match="unknown algorithm: ca_maxpressure"):
        RunRequest(intersection_id="16", algorithm="ca_maxpressure")


def test_supported_algorithms_contain_only_canonical_keys():
    assert SUPPORTED_ALGORITHMS == frozenset({
        "fixed_time",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
        "actuated",
    })
