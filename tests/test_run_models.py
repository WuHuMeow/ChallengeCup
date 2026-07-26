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
        "running",
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
        algorithm="ca_maxpressure",
        output_root=tmp_path,
    )

    assert request.output_root == Path(tmp_path)
