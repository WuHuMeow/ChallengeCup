from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from core.run_models import (
    DisturbanceSpec,
    RunRequest,
    RunStatus,
    SUPPORTED_ALGORITHMS,
    VariantSpec,
)
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
        (100, None),
        (36000, SimulationWindow(3600, 600)),
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
    if expected_window is None:
        with pytest.raises(ValueError, match="warmup_seconds"):
            RunService._window(replaced, 0.1)
    else:
        assert RunService._window(replaced, 0.1) == expected_window


def test_replacing_compatibility_duration_rederives_replayable_steps():
    request = RunRequest(
        "1",
        "fixed_time",
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )

    replaced = replace(request, duration_seconds=7200)
    replayed = RunRequest.from_payload(
        json.loads(json.dumps(replaced.to_payload()))
    )

    assert replaced.steps == 72000
    assert replaced.steps_origin == "compatibility"
    assert replayed == replaced
    assert RunService._window(replayed, 0.1) == SimulationWindow(7200, 600)


def test_removing_compatibility_override_removes_derived_steps_for_replay():
    request = RunRequest(
        "1",
        "fixed_time",
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )

    replaced = replace(request, step_length_override=None)
    replayed = RunRequest.from_payload(
        json.loads(json.dumps(replaced.to_payload()))
    )

    assert replaced.steps is None
    assert replaced.steps_origin == "none"
    assert replayed == replaced
    assert RunService._window(replayed, 0.1) == SimulationWindow(3600, 600)


def test_steps_origin_distinguishes_requests_with_different_windows():
    formal = RunRequest(
        "1",
        "fixed_time",
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )
    explicit = RunRequest(
        "1",
        "fixed_time",
        steps=36000,
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )

    assert formal != explicit
    assert asdict(formal) != asdict(explicit)
    assert formal.steps_origin == "compatibility"
    assert explicit.steps_origin == "explicit"


@pytest.mark.parametrize(
    ("steps", "expected_origin", "expected_window"),
    [
        (None, "compatibility", SimulationWindow(3600, 600)),
        (36000, "explicit", SimulationWindow(3600, 600)),
    ],
)
def test_request_json_roundtrip_preserves_steps_origin_and_window(
    steps, expected_origin, expected_window
):
    request = RunRequest(
        "1",
        "fixed_time",
        steps=steps,
        duration_seconds=3600,
        warmup_seconds=600,
        step_length_override=0.1,
    )

    payload = json.loads(json.dumps(request.to_payload()))
    replayed = RunRequest.from_payload(payload)

    assert payload["steps_origin"] == expected_origin
    assert replayed == request
    assert RunService._window(replayed, 0.1) == expected_window


def test_request_json_roundtrip_rebuilds_nested_and_path_values(tmp_path):
    disturbance = DisturbanceSpec(
        "construction",
        begin_seconds=10,
        end_seconds=20,
        target="lane-a",
        intensity=0.5,
    )
    request = RunRequest(
        "1",
        "capacity_aware_maxpressure",
        steps=100,
        output_root=tmp_path,
        edge_directions=("north", "south"),
        variant=VariantSpec(
            vehicle_type_overrides={"car": {"accel": "2.0"}},
            closed_lanes=("lane-a",),
        ),
        disturbance=disturbance,
        algorithm_params={"prediction_weight": 0.15, "base_green": 35},
    )

    replayed = RunRequest.from_payload(
        json.loads(json.dumps(request.to_payload()))
    )

    assert replayed == request
    assert replayed.output_root == Path(tmp_path)
    assert replayed.edge_directions == ("north", "south")
    assert replayed.variant.closed_lanes == ("lane-a",)
    assert replayed.variant.disturbance == disturbance
    assert replayed.algorithm_params == {
        "prediction_weight": 0.15,
        "base_green": 35.0,
    }


def test_request_json_roundtrip_preserves_none_steps_origin():
    request = RunRequest(
        "1", "fixed_time", duration_seconds=120, warmup_seconds=20
    )

    replayed = RunRequest.from_payload(
        json.loads(json.dumps(request.to_payload()))
    )

    assert replayed == request
    assert replayed.steps is None
    assert replayed.steps_origin == "none"
    assert RunService._window(replayed, 0.1) == SimulationWindow(120, 20)


@pytest.mark.parametrize(
    "payload",
    [
        {"steps": None, "steps_origin": "unknown"},
        {"steps": 100, "steps_origin": "none"},
        {"steps": None, "steps_origin": "explicit"},
        {
            "steps": None,
            "steps_origin": "none",
            "step_length_override": 0.1,
        },
        {
            "steps": 100,
            "steps_origin": "compatibility",
            "duration_seconds": 3600,
            "step_length_override": 0.1,
        },
        {
            "steps": 36000,
            "steps_origin": "compatibility",
            "duration_seconds": 3600,
            "step_length_override": None,
        },
    ],
    ids=(
        "unknown-origin",
        "none-with-steps",
        "explicit-without-steps",
        "none-with-override",
        "compatibility-mismatch",
        "compatibility-without-override",
    ),
)
def test_request_payload_rejects_inconsistent_steps_origin(payload):
    with pytest.raises(ValueError, match="steps_origin"):
        RunRequest.from_payload({
            "intersection_id": "1",
            "algorithm": "fixed_time",
            **payload,
        })


def test_legacy_request_payload_treats_plain_steps_as_explicit():
    replayed = RunRequest.from_payload(
        {"intersection_id": "1", "algorithm": "fixed_time", "steps": 100}
    )

    assert replayed.steps_origin == "explicit"
    assert RunService._window(replayed, 0.1) == SimulationWindow(10, 0)


@pytest.mark.parametrize("invalid_version", [2, True, 1.0])
def test_request_payload_schema_version_is_explicit_and_validated(invalid_version):
    request = RunRequest("1", "fixed_time", steps=100)

    payload = request.to_payload()

    assert payload["schema_version"] == 1
    with pytest.raises(ValueError, match="schema_version"):
        RunRequest.from_payload({**payload, "schema_version": invalid_version})


def test_versioned_request_payload_requires_steps_origin():
    payload = RunRequest(
        "1", "fixed_time", step_length_override=0.1
    ).to_payload()
    payload.pop("steps_origin")

    with pytest.raises(ValueError, match="steps_origin"):
        RunRequest.from_payload(payload)


def test_request_payload_preserves_distinct_variant_and_request_disturbances():
    variant_disturbance = DisturbanceSpec(
        "construction", 10, 20, "lane-a", 0.5
    )
    request_disturbance = DisturbanceSpec(
        "event_demand", 30, 40, "flow-a", 2.0
    )
    request = RunRequest(
        "1",
        "fixed_time",
        variant=VariantSpec(disturbance=variant_disturbance),
        disturbance=request_disturbance,
    )

    replayed = RunRequest.from_payload(
        json.loads(json.dumps(request.to_payload()))
    )

    assert replayed.variant.disturbance == variant_disturbance
    assert replayed.disturbance == request_disturbance


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
