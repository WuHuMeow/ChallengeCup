from __future__ import annotations

import csv
import hashlib
import json
import stat
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.run_models import RunStatus
from core.types import MetricSummary, SafetyEvent
from engine.artifacts import RunArtifacts
from engine.events import EVENT_FIELDS
from experiments.evidence import (
    EvidenceReader,
    EvidenceWriter,
    RunManifest,
    canonical_mapping_sha256,
)
from experiments.summary import metric_summary_payload, write_run_summary
from scripts.run_pdf_matrix import is_complete
from visualization.report import collect_summaries


SAFETY_TYPES = (
    "collision",
    "red_light",
    "illegal_transition",
    "harsh_braking",
    "teleport",
    "potential_conflict",
)


def _write_tripinfo(path: Path) -> None:
    path.write_text(
        "<tripinfos>"
        '<tripinfo id="warmup-done" depart="10" arrival="100" duration="90" '
        'timeLoss="9" waitingCount="9"><emissions fuel_abs="90" CO2_abs="9000"/>'
        "</tripinfo>"
        '<tripinfo id="done-a" depart="600" arrival="620" duration="20" '
        'timeLoss="4" waitingCount="2"><emissions fuel_abs="10" CO2_abs="1000"/>'
        "</tripinfo>"
        '<tripinfo id="done-b" depart="700" arrival="740" duration="40" '
        'timeLoss="8" waitingCount="4"><emissions fuel_abs="20" CO2_abs="3000"/>'
        "</tripinfo>"
        '<tripinfo id="active" depart="650" arrival="-1" duration="999" '
        'timeLoss="999" waitingCount="999"><emissions fuel_abs="999" CO2_abs="999000"/>'
        "</tripinfo>"
        '<tripinfo id="warmup-active" depart="100" arrival="-1" duration="999" '
        'timeLoss="999" waitingCount="999"><emissions fuel_abs="999" CO2_abs="999000"/>'
        "</tripinfo></tripinfos>",
        encoding="utf-8",
    )


def _write_metrics(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["step", "timestamp", "avg_queue_length", "max_queue_length"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"step": 0, "timestamp": 599, "avg_queue_length": 100, "max_queue_length": 100},
                {"step": 1, "timestamp": 600, "avg_queue_length": 2, "max_queue_length": 5},
                {"step": 2, "timestamp": 601, "avg_queue_length": 4, "max_queue_length": 9},
            ]
        )


def _write_events(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=list(EVENT_FIELDS),
        )
        writer.writeheader()
        writer.writerow(
            {
                "run_id": path.parent.name,
                "intersection_id": "1",
                "algorithm": "fixed_time",
                "step": 0,
                "simulation_seconds": 599,
                "type": "collision",
                "entity_ids": "[]",
                "source": "test_fixture",
                "confidence": 1.0,
            }
        )
        for index, event_type in enumerate(SAFETY_TYPES):
            writer.writerow(
                {
                    "run_id": path.parent.name,
                    "intersection_id": "1",
                    "algorithm": "fixed_time",
                    "step": index + 1,
                    "simulation_seconds": 600 + index,
                    "type": event_type,
                    "entity_ids": "[]",
                    "source": "test_fixture",
                    "confidence": 1.0,
                }
            )


def _manifest(run_id: str, **overrides: object) -> RunManifest:
    source_hashes = {"net": "c" * 64, "sumocfg": "d" * 64}
    values = {
        "run_id": run_id,
        "code_commit": "a" * 40,
        "scene_manifest_sha256": "d11bb49df1b2987b0f4fb44575d369c016195af9041334b62346e4ca45796e00",
        "algorithm": "fixed_time",
        "parameters": {"plan_source": "official"},
        "flow_multiplier": 1.0,
        "seed": 42,
        "duration_seconds": 3600.0,
        "warmup_seconds": 600.0,
        "derived_steps": 3600,
        "sumo_version": "1.27.1",
        "python_version": "3.12.13",
        "prediction_enabled": False,
        "scene_id": "1",
        "scene_source_sha256": source_hashes,
        "step_length": 1.0,
        "requested_seconds": 3600.0,
    }
    values.update(overrides)
    return RunManifest(**values)


def _write_completed_inputs(artifacts: RunArtifacts) -> MetricSummary:
    _write_tripinfo(artifacts.tripinfo)
    _write_metrics(artifacts.metrics)
    _write_events(artifacts.events)
    artifacts.step_log.write_text(
        "step,timestamp,current_phase\n0,600,0\n",
        encoding="utf-8",
    )
    artifacts.stats.write_text('<summary><step time="3600"/></summary>', encoding="utf-8")
    artifacts.trajectory.write_text("<fcd-export><timestep time=\"600\"/></fcd-export>", encoding="utf-8")
    artifacts.collisions.write_text("<collisions/>", encoding="utf-8")
    return MetricSummary.from_raw_outputs(artifacts.run_dir, warmup_seconds=600)


def _finish_status_and_metadata(
    artifacts: RunArtifacts,
    status: RunStatus,
    reason: str,
) -> None:
    artifacts.write_status("queued", "")
    artifacts.write_status("starting", "")
    artifacts.write_status("running", "")
    artifacts.write_metadata(
        status.value,
        reason,
        [path for path in artifacts.run_dir.iterdir() if path.is_file()],
        started_at="2026-08-22T00:00:00+00:00",
        ended_at="2026-08-22T01:00:00+00:00",
        sumo_version="1.27.1",
        requested_steps=3600,
        requested_seconds=3600.0,
        warmup_seconds=600.0,
        final_simulation_time=3600.0,
        step_length=1.0,
    )


def _completed_evidence(tmp_path: Path) -> tuple[RunArtifacts, MetricSummary]:
    artifacts = RunArtifacts.create(
        tmp_path, "1", "fixed_time", 1.0, 42, run_id="run-1"
    )
    writer = EvidenceWriter(artifacts.run_dir)
    writer.begin(_manifest(artifacts.run_id))
    summary = _write_completed_inputs(artifacts)
    writer.finalize(RunStatus.COMPLETED, summary)
    assert not artifacts.hashes.exists()
    _finish_status_and_metadata(artifacts, RunStatus.COMPLETED, "")
    writer.seal()
    return artifacts, summary


def _rehash(artifacts: RunArtifacts, name: str) -> None:
    hashes = json.loads(artifacts.hashes.read_text(encoding="utf-8"))
    hashes["files"][name] = hashlib.sha256(
        (artifacts.run_dir / name).read_bytes()
    ).hexdigest()
    artifacts.hashes.write_text(json.dumps(hashes), encoding="utf-8")


def _rewrite_json_and_rehash(
    artifacts: RunArtifacts,
    name: str,
    mutate,
) -> None:
    path = artifacts.run_dir / name
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")
    _rehash(artifacts, name)


def test_metric_summary_separates_unfinished_and_filters_all_sources_by_warmup(tmp_path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    _write_tripinfo(run_dir / "tripinfo.xml")
    _write_metrics(run_dir / "metrics.csv")
    _write_events(run_dir / "events.csv")

    summary = MetricSummary.from_raw_outputs(run_dir, warmup_seconds=600)

    assert summary.completed_vehicle_count == 2
    assert summary.unfinished_vehicle_count == 1
    assert summary.throughput == 2
    assert summary.avg_travel_time_seconds == 30.0
    assert summary.avg_delay_seconds == 6.0
    assert summary.total_stops == 6
    assert summary.fuel_ml == 30.0
    assert summary.co2_g == 4.0
    assert summary.fuel_ml_per_completed == 15.0
    assert summary.co2_g_per_completed == 2.0
    assert summary.avg_queue_length_vehicles == 3.0
    assert summary.max_queue_length_vehicles == 9.0
    assert summary.safety_counts == {event_type: 1 for event_type in SAFETY_TYPES}


def test_scene_mapping_hash_is_order_independent_and_hashes_the_complete_mapping():
    first = {"net": "a" * 64, "route": "b" * 64}
    reordered = {"route": "b" * 64, "net": "a" * 64}

    assert canonical_mapping_sha256(first) == canonical_mapping_sha256(reordered)
    assert canonical_mapping_sha256(first) != canonical_mapping_sha256(
        {"net": "a" * 64}
    )


def test_run_manifest_keeps_legacy_constructor_arguments_compatible():
    manifest = RunManifest(
        run_id="legacy-run",
        code_commit="a" * 40,
        scene_manifest_sha256="unknown",
        algorithm="fixed_time",
        parameters={},
        flow_multiplier=1.0,
        seed=42,
        duration_seconds=1.0,
        warmup_seconds=0.0,
        derived_steps=1,
        sumo_version="unknown",
        python_version="3.10",
        prediction_enabled=False,
    )

    assert manifest.scene_id == ""
    assert manifest.scene_source_sha256 == {}
    assert manifest.step_length is None
    assert manifest.requested_seconds == 0.0


def test_completed_evidence_is_atomic_hashed_and_preserves_legacy_summary_aliases(tmp_path):
    artifacts, summary = _completed_evidence(tmp_path)

    assert EvidenceReader.validate(artifacts.run_dir) == []
    payload = json.loads(artifacts.summary.read_text(encoding="utf-8"))
    assert payload["metrics"]["avg_travel_time_seconds"] == 30.0
    assert payload["metrics"]["avg_travel_time"] == 30.0
    assert payload["metrics"]["avg_delay"] == 6.0
    assert payload["metrics"]["fuel_consumption"] == 30.0
    assert payload["metrics"]["fuel_ml"] == 30.0
    assert payload["metrics"]["co2_g"] == 4.0
    assert payload["metrics"]["collision_count"] == 1
    assert payload["units"]["fuel_ml"] == "ml"
    assert payload["units"]["fuel_consumption"] == "ml"
    assert payload["units"]["co2_g"] == "g"
    assert payload["units"]["avg_travel_time_seconds"] == "s"
    assert payload["units"]["avg_travel_time"] == "s"
    assert payload["units"]["avg_delay"] == "s"
    assert payload["units"]["avg_queue_length"] == "vehicles"
    assert payload["units"]["max_queue_length"] == "vehicles"
    assert summary.completed_vehicle_count == 2

    hashes = json.loads(artifacts.hashes.read_text(encoding="utf-8"))
    assert "hashes.json" not in hashes["files"]
    assert set(hashes["files"]) == set(
        RunArtifacts.evidence_required_output_names()
    ) - {"hashes.json"}
    assert not list(artifacts.run_dir.glob("*.tmp"))
    assert not list(artifacts.run_dir.glob(".*.tmp"))


def test_hash_tampering_and_run_id_mismatch_fail_closed(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)
    artifacts.metrics.write_text("tampered\n", encoding="utf-8")

    issues = EvidenceReader.validate(artifacts.run_dir)

    assert {issue.code for issue in issues} >= {"hash_mismatch"}

    hashes = json.loads(artifacts.hashes.read_text(encoding="utf-8"))
    hashes["run_id"] = "different-run"
    artifacts.hashes.write_text(json.dumps(hashes), encoding="utf-8")
    issues = EvidenceReader.validate(artifacts.run_dir)
    assert {issue.code for issue in issues} >= {"run_id_mismatch"}


def test_failed_evidence_is_verifiable_without_fabricating_completed_outputs(tmp_path):
    artifacts = RunArtifacts.create(
        tmp_path, "1", "fixed_time", 1.0, 42, run_id="run-failed"
    )
    writer = EvidenceWriter(artifacts.run_dir)
    writer.begin(
        _manifest(
            artifacts.run_id,
            sumo_version="unknown",
            scene_manifest_sha256="unknown",
            derived_steps=None,
            step_length=None,
        )
    )
    writer.finalize(RunStatus.FAILED, None)
    assert not artifacts.hashes.exists()
    _finish_status_and_metadata(artifacts, RunStatus.FAILED, "SUMO start failed")
    writer.seal()

    assert EvidenceReader.validate(artifacts.run_dir) == []
    assert not artifacts.summary.exists()
    assert not artifacts.tripinfo.exists()
    hashes = json.loads(artifacts.hashes.read_text(encoding="utf-8"))
    assert set(hashes["files"]) == {
        "manifest.json",
        "provenance.json",
        "status.json",
        "run_metadata.json",
    }


def test_legacy_required_outputs_remain_stable_but_strict_evidence_contract_is_additive():
    assert RunArtifacts.required_output_names() == (
        "metrics.csv",
        "simulation_log.csv",
        "events.csv",
        "tripinfo.xml",
        "stats.xml",
        "traj.xml",
        "collisions.xml",
        "summary.json",
    )
    assert RunArtifacts.evidence_required_output_names() == (
        "manifest.json",
        "provenance.json",
        "status.json",
        "run_metadata.json",
        *RunArtifacts.required_output_names(),
        "hashes.json",
    )


def test_write_run_summary_uses_metric_summary_and_writes_json_atomically(tmp_path):
    artifacts = RunArtifacts.create(
        tmp_path, "1", "fixed_time", 1.0, 42, run_id="run-summary"
    )
    _write_completed_inputs(artifacts)

    payload = write_run_summary(artifacts, warmup_seconds=600)

    assert payload["metrics"]["completed_vehicle_count"] == 2
    assert payload["metrics"]["unfinished_vehicle_count"] == 1
    assert payload["metrics"]["potential_conflict_count"] == 1
    assert not list(artifacts.run_dir.glob("*.tmp"))
    assert not list(artifacts.run_dir.glob(".*.tmp"))


def test_record_event_rejects_other_run_and_atomically_preserves_safety_fields(tmp_path):
    run_dir = tmp_path / "run-events"
    writer = EvidenceWriter(run_dir)
    writer.begin(_manifest("run-events"))
    event = SafetyEvent(
        run_id="run-events",
        step=12,
        simulation_seconds=612.5,
        event_type="potential_conflict",
        entity_ids=("veh-a", "veh-b"),
        source="derived_foes",
        confidence=0.75,
        detail="post-warmup conflict",
    )
    writer.record_event(event)
    with pytest.raises(ValueError, match="run_id"):
        writer.record_event(replace(event, run_id="other-run"))

    writer.finalize(RunStatus.FAILED, None)

    rows = list(csv.DictReader((run_dir / "events.csv").open(encoding="utf-8")))
    assert rows == [{
        **{name: "" for name in EVENT_FIELDS},
        "run_id": "run-events",
        "intersection_id": "1",
        "algorithm": "fixed_time",
        "step": "12",
        "simulation_seconds": "612.5",
        "type": "potential_conflict",
        "detail": "post-warmup conflict",
        "entity_ids": '["veh-a", "veh-b"]',
        "source": "derived_foes",
        "confidence": "0.75",
    }]
    assert not list(run_dir.glob("*.tmp"))
    assert not list(run_dir.glob(".*.tmp"))


def test_manifest_serializes_request_dimensions_and_rejects_non_finite_json(tmp_path):
    run_dir = tmp_path / "run-request"
    writer = EvidenceWriter(run_dir)
    dimensions = {
        "variant": {"signal_duration_scale": 1.1},
        "disturbance": {"kind": "construction", "begin_seconds": 900.0},
        "edge_delay_steps": 2,
        "edge_directions": ["uplink"],
        "steps_origin": "explicit",
        "requested_steps": 3600,
    }

    writer.begin(_manifest("run-request", request_dimensions=dimensions))

    payload = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["request_dimensions"] == dimensions
    assert payload["schema"] == "challenge-cup.run-manifest"
    assert type(payload["schema_version"]) is int

    invalid_dir = tmp_path / "run-invalid"
    with pytest.raises(ValueError):
        EvidenceWriter(invalid_dir).begin(
            _manifest("run-invalid", parameters={"prediction_weight": float("nan")})
        )
    assert not list(invalid_dir.glob("*.tmp"))
    assert not list(invalid_dir.glob(".*.tmp"))


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("depart", None),
        ("depart", "not-a-time"),
        ("arrival", None),
        ("arrival", "not-a-time"),
    ],
)
def test_strict_raw_parser_rejects_missing_or_malformed_vehicle_times(
    tmp_path,
    attribute,
    value,
):
    run_dir = tmp_path / "run-strict"
    run_dir.mkdir()
    attributes = {
        "id": "v0",
        "depart": "600",
        "arrival": "620",
        "duration": "20",
        "timeLoss": "4",
        "waitingCount": "2",
    }
    if value is None:
        attributes.pop(attribute)
    else:
        attributes[attribute] = value
    serialized = " ".join(f'{key}="{raw}"' for key, raw in attributes.items())
    (run_dir / "tripinfo.xml").write_text(
        f"<tripinfos><tripinfo {serialized}/></tripinfos>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=attribute):
        MetricSummary.from_raw_outputs(run_dir, warmup_seconds=600)


def test_new_evidence_rejects_stopped_and_existing_identity_conflicts(tmp_path):
    artifacts = RunArtifacts.create(
        tmp_path, "1", "fixed_time", 1.0, 42, run_id="run-identity"
    )
    writer = EvidenceWriter(artifacts.run_dir)
    artifacts.write_manifest({"requested_seconds": 3600.0})

    with pytest.raises(ValueError, match="identity"):
        writer.begin(_manifest("run-identity", algorithm="classic_maxpressure"))
    writer.begin(_manifest("run-identity"))
    with pytest.raises(ValueError, match="terminal"):
        writer.finalize(RunStatus.STOPPED, None)


def test_reader_checks_semantics_even_when_tampered_files_are_rehashed(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)
    provenance = json.loads(artifacts.provenance.read_text(encoding="utf-8"))
    provenance["code_commit"] = "e" * 40
    artifacts.provenance.write_text(json.dumps(provenance), encoding="utf-8")
    _rehash(artifacts, "provenance.json")

    events = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    events[0]["run_id"] = "other-run"
    with artifacts.events.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(EVENT_FIELDS))
        writer.writeheader()
        writer.writerows(events)
    _rehash(artifacts, "events.csv")

    issues = EvidenceReader.validate(artifacts.run_dir)

    assert {issue.code for issue in issues} >= {
        "provenance_mismatch",
        "event_run_id_mismatch",
    }
    assert "hash_mismatch" not in {issue.code for issue in issues}


def test_reader_rejects_rehashed_manifest_failure_reason_mismatch(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)

    def corrupt_manifest(payload):
        payload["failure_reason"] = "invented terminal reason"

    _rewrite_json_and_rehash(artifacts, "manifest.json", corrupt_manifest)

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "failure_reason" in codes
    assert "hash_mismatch" not in codes


def test_reader_rejects_unsafe_hash_paths_and_unexpected_failed_summary(tmp_path):
    artifacts = RunArtifacts.create(
        tmp_path, "1", "fixed_time", 1.0, 42, run_id="run-failed-path"
    )
    writer = EvidenceWriter(artifacts.run_dir)
    writer.begin(
        _manifest(
            artifacts.run_id,
            sumo_version="unknown",
            scene_manifest_sha256="unknown",
            derived_steps=None,
            step_length=None,
        )
    )
    writer.finalize(RunStatus.FAILED, None)
    _finish_status_and_metadata(artifacts, RunStatus.FAILED, "start failed")
    writer.seal()
    artifacts.summary.write_text("{}", encoding="utf-8")
    hashes = json.loads(artifacts.hashes.read_text(encoding="utf-8"))
    hashes["files"]["../summary.json"] = hashlib.sha256(b"{}").hexdigest()
    artifacts.hashes.write_text(json.dumps(hashes), encoding="utf-8")

    issues = EvidenceReader.validate(artifacts.run_dir)

    assert {issue.code for issue in issues} >= {
        "unsafe_hash_path",
        "unexpected_summary",
    }


def test_seal_is_idempotent_only_while_evidence_remains_byte_identical(tmp_path):
    artifacts, summary = _completed_evidence(tmp_path)
    writer = EvidenceWriter(artifacts.run_dir)

    writer.seal()
    with pytest.raises(ValueError, match="sealed"):
        writer.finalize(RunStatus.COMPLETED, summary)

    artifacts.metrics.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sealed evidence"):
        writer.seal()


def test_non_publishable_refinalize_removes_prior_completed_summary(tmp_path):
    artifacts = RunArtifacts.create(
        tmp_path, "1", "fixed_time", 1.0, 42, run_id="run-downgrade"
    )
    writer = EvidenceWriter(artifacts.run_dir)
    writer.begin(_manifest(artifacts.run_id))
    summary = _write_completed_inputs(artifacts)
    writer.finalize(RunStatus.COMPLETED, summary)

    writer.finalize(RunStatus.FAILED, None)

    assert not artifacts.summary.exists()
    manifest = json.loads(artifacts.manifest.read_text(encoding="utf-8"))
    assert manifest["end_status"] == "failed"


def test_resume_rejects_legacy_completed_run_without_strict_evidence(tmp_path):
    legacy = tmp_path / "legacy-run"
    legacy.mkdir()
    (legacy / "run_metadata.json").write_text(
        json.dumps({"status": "completed"}),
        encoding="utf-8",
    )
    for name in RunArtifacts.required_output_names():
        (legacy / name).write_text("legacy\n", encoding="utf-8")

    assert is_complete(legacy) is False

    artifacts, _ = _completed_evidence(tmp_path)
    assert is_complete(artifacts.run_dir) is True


def test_visualization_collects_only_reader_validated_summaries(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)
    legacy = tmp_path / "legacy-run"
    legacy.mkdir()
    (legacy / "run_metadata.json").write_text(
        json.dumps({
            "run_id": "legacy-run",
            "intersection_id": "1",
            "algorithm": "fixed_time",
            "status": "completed",
        }),
        encoding="utf-8",
    )
    (legacy / "summary.json").write_text(
        json.dumps({"run_id": "legacy-run", "metrics": {"throughput": 999}}),
        encoding="utf-8",
    )

    frame = collect_summaries(tmp_path)

    assert frame["run_id"].tolist() == [artifacts.run_id]


def test_reader_rejects_symlinked_contract_output_even_when_hash_matches(
    tmp_path,
    monkeypatch,
):
    artifacts, _ = _completed_evidence(tmp_path)
    real_metrics = artifacts.run_dir / "metrics-real.csv"
    artifacts.metrics.replace(real_metrics)
    try:
        artifacts.metrics.symlink_to(real_metrics.name)
    except OSError:
        real_metrics.replace(artifacts.metrics)
        original_lstat = Path.lstat
        monkeypatch.setattr(
            Path,
            "lstat",
            lambda path, *args, **kwargs: (
                SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
                if path == artifacts.metrics
                else original_lstat(path, *args, **kwargs)
            ),
        )
    else:
        _rehash(artifacts, "metrics.csv")

    issues = EvidenceReader.validate(artifacts.run_dir)

    assert "symlink_output" in {issue.code for issue in issues}


def test_writer_refuses_to_seal_a_symlinked_required_output(tmp_path, monkeypatch):
    artifacts = RunArtifacts.create(
        tmp_path, "1", "fixed_time", 1.0, 42, run_id="run-writer-symlink"
    )
    writer = EvidenceWriter(artifacts.run_dir)
    writer.begin(_manifest(artifacts.run_id))
    summary = _write_completed_inputs(artifacts)
    writer.finalize(RunStatus.COMPLETED, summary)
    _finish_status_and_metadata(artifacts, RunStatus.COMPLETED, "")
    original_lstat = Path.lstat
    monkeypatch.setattr(
        Path,
        "lstat",
        lambda path, *args, **kwargs: (
            SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0)
            if path == artifacts.stats
            else original_lstat(path, *args, **kwargs)
        ),
    )

    with pytest.raises(ValueError, match="symlink"):
        writer.seal()

    assert not artifacts.hashes.exists()


def test_writer_never_seals_a_manifest_with_recorded_evidence_error(tmp_path):
    artifacts = RunArtifacts.create(
        tmp_path, "1", "fixed_time", 1.0, 42, run_id="run-evidence-error"
    )
    writer = EvidenceWriter(artifacts.run_dir)
    writer.begin(_manifest(artifacts.run_id))
    summary = _write_completed_inputs(artifacts)
    writer.finalize(RunStatus.COMPLETED, summary)
    _finish_status_and_metadata(artifacts, RunStatus.COMPLETED, "")
    writer.record_error("durable hash storage failed")

    with pytest.raises(ValueError, match="evidence error"):
        writer.seal()

    assert not artifacts.hashes.exists()


@pytest.mark.parametrize(
    ("run_id", "simulation_seconds"),
    [("other-run", "600"), ("run-1", "NaN")],
)
def test_reader_checks_identity_and_finite_time_on_every_event_row(
    tmp_path,
    run_id,
    simulation_seconds,
):
    artifacts, _ = _completed_evidence(tmp_path)
    with artifacts.events.open("a", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(EVENT_FIELDS))
        writer.writerow({
            "run_id": run_id,
            "step": 7,
            "simulation_seconds": simulation_seconds,
            "type": "run_note",
            "detail": "ordinary non-safety event",
        })
    _rehash(artifacts, "events.csv")

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    expected = (
        "event_run_id_mismatch"
        if run_id != artifacts.run_id
        else "events_schema"
    )
    assert expected in codes


@pytest.mark.parametrize(
    "name",
    ["tripinfo.xml", "stats.xml", "traj.xml", "collisions.xml"],
)
def test_reader_rejects_truncated_hashed_xml_outputs(tmp_path, name):
    artifacts, _ = _completed_evidence(tmp_path)
    (artifacts.run_dir / name).write_text("<truncated>", encoding="utf-8")
    _rehash(artifacts, name)

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "xml_invalid" in codes
    assert "hash_mismatch" not in codes


def test_reader_enforces_digest_algorithm_manifest_types_and_finite_json(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)

    def corrupt_manifest(payload):
        payload["code_commit"] = "not-a-commit"
        payload["scene_source_sha256"]["net"] = "NOT-A-DIGEST"
        payload["scene_manifest_sha256"] = "f" * 64
        payload["prediction_enabled"] = "false"
        payload["flow_multiplier"] = True
        payload["parameters"] = {"nested": [float("nan")]}

    _rewrite_json_and_rehash(artifacts, "manifest.json", corrupt_manifest)
    hashes = json.loads(artifacts.hashes.read_text(encoding="utf-8"))
    hashes["algorithm"] = "sha1"
    hashes["files"]["metrics.csv"] = "A" * 64
    artifacts.hashes.write_text(json.dumps(hashes), encoding="utf-8")

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert codes >= {
        "commit_format",
        "digest_format",
        "provenance_mismatch",
        "manifest_type",
        "non_finite_json",
        "hash_schema",
    }


def test_reader_compares_canonical_summary_to_raw_outputs(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)

    def corrupt_summary(payload):
        payload["metrics"]["throughput"] = 999
        payload["metrics"]["fuel_ml"] = 123.0

    _rewrite_json_and_rehash(artifacts, "summary.json", corrupt_summary)

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "summary_mismatch" in codes
    assert "hash_mismatch" not in codes


def test_reader_allows_unhashed_additive_figures_and_variant_files(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)
    (artifacts.run_dir / "figure.png").write_bytes(b"plot")
    variants = artifacts.run_dir / "variants"
    variants.mkdir()
    (variants / "generated.rou.xml").write_text("<routes/>", encoding="utf-8")

    assert EvidenceReader.validate(artifacts.run_dir) == []


def test_any_negative_arrival_is_counted_as_unfinished(tmp_path):
    run_dir = tmp_path / "run-negative-arrival"
    run_dir.mkdir()
    (run_dir / "tripinfo.xml").write_text(
        '<tripinfos><tripinfo id="active" depart="600" arrival="-0.5" '
        'duration="1" timeLoss="0" waitingCount="0"/></tripinfos>',
        encoding="utf-8",
    )

    summary = MetricSummary.from_raw_outputs(run_dir, warmup_seconds=600)

    assert summary.completed_vehicle_count == 0
    assert summary.unfinished_vehicle_count == 1


@pytest.mark.parametrize("name", ["summary.json", "events.csv"])
def test_reader_converts_contract_stat_failures_to_evidence_issues(
    tmp_path,
    monkeypatch,
    name,
):
    artifacts, _ = _completed_evidence(tmp_path)
    target = artifacts.run_dir / name
    original_stat = Path.stat

    def fail_target(path, *args, **kwargs):
        if path == target:
            raise PermissionError(f"cannot stat {name}")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", fail_target)

    issues = EvidenceReader.validate(artifacts.run_dir)

    assert "evidence_io" in {issue.code for issue in issues}


@pytest.mark.parametrize("name", ["metrics.csv", "simulation_log.csv"])
def test_reader_rejects_rehashed_garbage_timeseries_csv(tmp_path, name):
    artifacts, _ = _completed_evidence(tmp_path)
    path = artifacts.run_dir / name
    path.write_text("garbage\n", encoding="utf-8")
    if name == "metrics.csv":
        derived = MetricSummary.from_raw_outputs(
            artifacts.run_dir,
            warmup_seconds=600,
        )
        artifacts.summary.write_text(
            json.dumps(metric_summary_payload(artifacts.run_id, derived, 600)),
            encoding="utf-8",
        )
        _rehash(artifacts, "summary.json")
    _rehash(artifacts, name)

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "csv_schema" in codes
    assert "hash_mismatch" not in codes


def test_reader_closes_manifest_metadata_identity_and_timebase(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)

    def corrupt_metadata(payload):
        payload.update({
            "algorithm": "other",
            "intersection_id": "999",
            "flow_multiplier": -2,
            "seed": 999,
            "requested_steps": 999,
            "requested_seconds": -5,
            "warmup_seconds": -1,
            "step_length": -1,
            "final_simulation_time": -10,
            "sumo_version": "spoof",
        })

    _rewrite_json_and_rehash(
        artifacts,
        "run_metadata.json",
        corrupt_metadata,
    )

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert codes >= {"metadata_mismatch", "metadata_type"}


def test_reader_requires_exact_manifest_json_types(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)

    def corrupt_manifest(payload):
        payload.update({
            "algorithm": 7,
            "scene_id": False,
            "intersection_id": [],
            "request_dimensions": "oops",
            "sumo_version": 123,
            "python_version": [],
        })

    _rewrite_json_and_rehash(artifacts, "manifest.json", corrupt_manifest)

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "manifest_type" in codes


def test_reader_rejects_reparse_point_in_run_directory_ancestry(
    tmp_path,
    monkeypatch,
):
    artifacts, _ = _completed_evidence(tmp_path)
    junction = artifacts.run_dir.parent
    original_lstat = Path.lstat

    def reparse_lstat(path, *args, **kwargs):
        if path == junction:
            return SimpleNamespace(
                st_mode=stat.S_IFDIR,
                st_file_attributes=0x0400,
            )
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(
        Path,
        "lstat",
        reparse_lstat,
    )

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "reparse_point" in codes


@pytest.mark.parametrize("exception_type", [OSError, PermissionError])
def test_reader_converts_temporary_glob_failures_to_evidence_issues(
    tmp_path,
    monkeypatch,
    exception_type,
):
    artifacts, _ = _completed_evidence(tmp_path)
    original_glob = Path.glob

    def fail_run_glob(path, pattern):
        if path == artifacts.run_dir:
            raise exception_type("cannot enumerate temporary files")
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", fail_run_glob)

    issues = EvidenceReader.validate(artifacts.run_dir)

    assert "evidence_io" in {issue.code for issue in issues}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("step", "true"),
        ("type", ""),
        ("accepted", "maybe"),
        ("action_value", "not-json"),
        ("entity_ids", '{"not": "a-list"}'),
        ("entity_ids", ""),
        ("source", ""),
        ("confidence", "1.5"),
        ("confidence", "NaN"),
    ],
)
def test_reader_rejects_rehashed_malformed_event_schema_rows(
    tmp_path,
    field,
    value,
):
    artifacts, _ = _completed_evidence(tmp_path)
    rows = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    rows[0][field] = value
    with artifacts.events.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(EVENT_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    _rehash(artifacts, "events.csv")

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "events_schema" in codes
    assert "hash_mismatch" not in codes


def test_reader_rejects_event_schema_with_unexpected_column_after_rehash(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)
    rows = list(csv.DictReader(artifacts.events.open(encoding="utf-8")))
    fieldnames = [*EVENT_FIELDS, "untrusted"]
    rows[0]["untrusted"] = "extra"
    with artifacts.events.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    _rehash(artifacts, "events.csv")

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "events_schema" in codes
    assert "hash_mismatch" not in codes


def test_summary_integer_counts_do_not_accept_json_booleans(tmp_path):
    artifacts, _ = _completed_evidence(tmp_path)

    def corrupt_summary(payload):
        payload["metrics"]["collision_count"] = True

    _rewrite_json_and_rehash(artifacts, "summary.json", corrupt_summary)

    codes = {issue.code for issue in EvidenceReader.validate(artifacts.run_dir)}

    assert "summary_mismatch" in codes
