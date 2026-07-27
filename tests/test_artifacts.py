import json

from engine.artifacts import RunArtifacts


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
    )

    payload = json.loads(artifacts.metadata.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["run_id"] == artifacts.run_id
    assert payload["intersection_id"] == "1"
    assert payload["generated_files"] == ["metrics.csv"]
    assert payload["sumo_version"] == "1.27.1"
    assert payload["started_at"] < payload["ended_at"]
