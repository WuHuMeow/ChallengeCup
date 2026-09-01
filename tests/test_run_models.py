from pathlib import Path

from core.run_models import RunRequest, RunStatus, VariantSpec


def test_run_request_has_pdf_defaults():
    request = RunRequest(intersection_id="1", algorithm="fixed_time")

    assert request.steps == 36000
    assert request.flow_multiplier == 1.0
    assert request.seed == 42
    assert request.output_root is None
    assert request.variant == VariantSpec()


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


def test_disturbance_spec_validates_bounds():
    from core.run_models import DisturbanceSpec
    import pytest

    spec = DisturbanceSpec("construction", 10, 20, "E0_0", 1.0)
    assert spec.kind == "construction"
    with pytest.raises(ValueError, match="end_seconds"):
        DisturbanceSpec("event_demand", 20, 10, "E0_0", 1.0)
    with pytest.raises(ValueError, match="intensity"):
        DisturbanceSpec("vehicle_failure", 0, 10, "E0_0", 0)
    with pytest.raises(ValueError, match="intensity"):
        DisturbanceSpec("construction", 0, 10, "E0_0", 1.01)
    with pytest.raises(ValueError, match="kind"):
        DisturbanceSpec("flood", 0, 10, "E0_0", 0.5)


def test_run_request_routes_disturbance_into_variant():
    from core.run_models import DisturbanceSpec

    disturbance = DisturbanceSpec("construction", 10, 20, "E0_0", 1.0)
    request = RunRequest("1", "fixed_time", steps=10, disturbance=disturbance)
    assert request.variant.disturbance is disturbance


def test_run_request_accepts_explicit_output_root(tmp_path):
    request = RunRequest(
        intersection_id="16",
        algorithm="ca_maxpressure",
        output_root=tmp_path,
    )

    assert request.output_root == Path(tmp_path)
