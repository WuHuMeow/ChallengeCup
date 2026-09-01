import json

import pytest

from engine.artifacts import CorruptStatusArtifactError, RunArtifacts


def test_run_artifacts_create_collision_safe_layout(tmp_path):
    first = RunArtifacts.create(tmp_path, "16", "actuated", 1.5, 42)
    second = RunArtifacts.create(tmp_path, "16", "actuated", 1.5, 42)

    expected_parent = tmp_path / "i16" / "actuated" / "x1.5" / "s42"
    assert first.run_dir.parent == expected_parent
    assert second.run_dir.parent == expected_parent
    assert first.run_id != second.run_id
    assert first.run_dir.name == first.run_id
    assert first.metrics.name == "metrics.csv"
    assert first.events.name == "events.csv"
    assert first.tripinfo.name == "tripinfo.xml"
    assert first.collisions.name == "collisions.xml"
    assert first.summary.name == "summary.json"
    assert first.figures.name == "figures"


def test_required_output_contract_is_shared_by_runners_and_checker():
    from scripts.check_outputs import REQUIRED
    from scripts.run_pdf_matrix import REQUIRED_ARTIFACTS

    expected = (
        "metrics.csv",
        "simulation_log.csv",
        "events.csv",
        "tripinfo.xml",
        "stats.xml",
        "traj.xml",
        "collisions.xml",
        "summary.json",
    )
    assert RunArtifacts.required_output_names() == expected
    assert REQUIRED_ARTIFACTS == expected
    assert tuple(REQUIRED) == ("run_metadata.json", *expected)


def test_write_metadata_is_atomic_and_structured(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    artifacts.metrics.write_text("step\n0\n", encoding="utf-8")

    artifacts.write_metadata(
        "completed",
        "",
        [artifacts.metrics],
        started_at="2026-07-25T10:00:00+08:00",
        ended_at="2026-07-25T10:01:00+08:00",
        sumo_version="1.27.1",
        requested_steps=36000,
        final_simulation_time=3600.0,
        step_length=0.1,
        configured_end_time=3600.0,
    )

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["run_id"] == artifacts.run_id
    assert payload["intersection_id"] == "1"
    assert payload["generated_files"] == ["metrics.csv"]
    assert payload["sumo_version"] == "1.27.1"
    assert payload["started_at"] < payload["ended_at"]
    assert payload["requested_steps"] == 36000
    assert payload["final_simulation_time"] == 3600.0
    assert payload["step_length"] == 0.1
    assert payload["configured_end_time"] == 3600.0


def test_run_metadata_records_movement_capacity_inputs(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)

    artifacts.write_metadata(
        "completed",
        "",
        [],
        started_at="start",
        ended_at="end",
        sumo_version="1.27.1",
        movement_capacity_inputs={
            "vehicle_length_m": 5.0,
            "minimum_gap_m": 2.5,
            "capacity_spacing_m": 7.5,
        },
    )

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["movement_capacity_inputs"] == {
        "vehicle_length_m": 5.0,
        "minimum_gap_m": 2.5,
        "capacity_spacing_m": 7.5,
    }


def test_manifest_and_status_are_atomic_and_terminal_status_is_immutable(tmp_path):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)

    artifacts.write_manifest({
        "run_id": "cannot-replace",
        "requested_seconds": 10.0,
        "derived_steps": 100,
    })
    artifacts.write_status("queued", "")
    artifacts.write_status("starting", "")
    artifacts.write_status("running", "")
    artifacts.write_status("completed", "")

    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))
    status = json.loads(artifacts.status.read_text(encoding="utf-8"))
    assert manifest["run_id"] == artifacts.run_id
    assert manifest["requested_seconds"] == 10.0
    assert status["status"] == "completed"
    assert status["started_at"]
    assert status["ended_at"]
    assert not list(artifacts.run_dir.glob("*.tmp"))

    with pytest.raises(ValueError, match="terminal"):
        artifacts.write_status("failed", "late failure")
    assert json.loads(artifacts.status.read_text(encoding="utf-8"))["status"] == "completed"

    with pytest.raises(ValueError, match="terminal"):
        artifacts.write_metadata(
            "failed",
            "late failure",
            [],
            started_at="start",
            ended_at="end",
            sumo_version="test",
        )
    assert not artifacts.metadata.exists()


@pytest.mark.parametrize(
    "payload",
    [
        [],
        None,
        7,
        {"run_id": "CURRENT"},
        {"run_id": "CURRENT", "status": "unknown"},
        {"run_id": "CURRENT", "status": 7},
        {"run_id": "different-run", "status": "running"},
        {"status": "running"},
    ],
    ids=(
        "list",
        "null",
        "scalar",
        "missing-status",
        "unknown-status",
        "non-string-status",
        "mismatched-run-id",
        "missing-run-id",
    ),
)
def test_malformed_status_records_are_recoverable_corruption(tmp_path, payload):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    if isinstance(payload, dict):
        payload = dict(payload)
        if payload.get("run_id") == "CURRENT":
            payload["run_id"] = artifacts.run_id
    artifacts.status.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CorruptStatusArtifactError, match="status artifact is corrupt"):
        artifacts.write_metadata(
            "failed",
            "runner failed",
            [],
            started_at="start",
            ended_at="end",
            sumo_version="test",
        )

    assert not artifacts.metadata.exists()
    artifacts.recover_corrupt_status("status schema corruption")
    recovered = json.loads(artifacts.status.read_text(encoding="utf-8"))
    assert recovered["run_id"] == artifacts.run_id
    assert recovered["status"] == "failed"
    assert recovered["reason"] == "status schema corruption"


@pytest.mark.parametrize(
    "status",
    [
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
    ],
)
def test_recovery_refuses_every_valid_status_record(tmp_path, status):
    artifacts = RunArtifacts.create(tmp_path, "1", "fixed_time", 1.0, 42)
    original = {"run_id": artifacts.run_id, "status": status}
    artifacts.status.write_text(json.dumps(original), encoding="utf-8")

    with pytest.raises(ValueError, match="status artifact is valid"):
        artifacts.recover_corrupt_status("must not overwrite")

    assert json.loads(artifacts.status.read_text(encoding="utf-8")) == original
