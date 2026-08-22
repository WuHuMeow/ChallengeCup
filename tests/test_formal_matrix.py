"""Frozen formal experiment matrix and paired-selection contracts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from core.run_models import RunResult, RunStatus


def test_formal_matrix_modules_are_available():
    """Catch a release missing either half of the frozen matrix contract."""
    assert importlib.util.find_spec("experiments.matrix") is not None
    assert importlib.util.find_spec("experiments.statistics") is not None


def test_normal_matrix_has_360_unique_specs():
    """Catch a missing factor, legacy load/seed, or colliding formal identity."""
    from experiments.matrix import FormalMatrix

    specs = FormalMatrix.normal()

    assert len(specs) == 360
    assert len({item.run_key for item in specs}) == 360
    assert {item.scene_id for item in specs} == {str(i) for i in range(1, 21)}
    assert {item.algorithm for item in specs} == {
        "fixed_time",
        "classic_maxpressure",
        "capacity_aware_maxpressure",
    }
    assert {item.flow_multiplier for item in specs} == {1.0, 1.25}
    assert {item.seed for item in specs} == {42, 43, 44}
    assert all(item.duration_seconds == 3600 for item in specs)
    assert all(item.warmup_seconds == 600 for item in specs)
    assert all(item.disturbance is None for item in specs)


def test_disturbance_matrix_has_180_specs_and_fixed_seed():
    """Catch an unfrozen disturbance load, seed, parameter, or target."""
    from experiments.matrix import FormalMatrix

    specs = FormalMatrix.disturbance()

    assert len(specs) == 180
    assert len({item.run_key for item in specs}) == 180
    assert {item.disturbance.kind for item in specs} == {
        "construction",
        "event_demand",
        "vehicle_failure",
    }
    assert {item.seed for item in specs} == {42}
    assert {item.flow_multiplier for item in specs} == {1.0}
    assert all(item.duration_seconds == 3600 for item in specs)
    assert all(item.warmup_seconds == 600 for item in specs)
    assert all(item.disturbance.target for item in specs)
    assert all(item.disturbance.begin_seconds == 600 for item in specs)
    assert all(item.disturbance.end_seconds == 1200 for item in specs)


def test_all_matrix_has_540_globally_unique_keys():
    """Catch identity collisions between normal and disturbance cases."""
    from experiments.matrix import FormalMatrix

    specs = FormalMatrix.all()

    assert len(specs) == 540
    assert len({item.run_key for item in specs}) == 540
    payload = json.loads(specs[-1].run_key)
    assert payload["disturbance"] == {
        "begin_seconds": 600.0,
        "end_seconds": 1200.0,
        "intensity": 1.0,
        "kind": "vehicle_failure",
        "target": specs[-1].disturbance.target,
    }


def test_target_selection_is_stable_and_uses_reachable_formal_lanes(tmp_path):
    """Catch XML-order dependence and selection of internal/unreachable lanes."""
    from experiments.matrix import _select_disturbance_targets

    network = tmp_path / "scene.net.xml"
    network.write_text(
        """<net>
        <edge id="B"><lane id="B_0" length="20"/></edge>
        <edge id=":internal"><lane id=":internal_0" length="20"/></edge>
        <edge id="A"><lane id="A_1" length="20"/><lane id="A_0" length="20"/></edge>
        <connection from="B" to=":internal"/>
        <connection from="A" to="C"/>
        </net>""",
        encoding="utf-8",
    )

    lane, edge = _select_disturbance_targets(
        network, ("B_0", ":internal_0", "A_1", "A_0")
    )

    assert (lane, edge) == ("A_0", "A")


@pytest.mark.parametrize(
    "length,connection",
    [("nan", '<connection from="A" to="C"/>'), ("20", "")],
)
def test_target_selection_fails_closed_without_valid_reachable_lane(
    tmp_path, length, connection
):
    """Catch non-finite lane geometry and absent continuations."""
    from experiments.matrix import _select_disturbance_targets

    network = tmp_path / "scene.net.xml"
    network.write_text(
        f'<net><edge id="A"><lane id="A_0" length="{length}"/></edge>'
        f"{connection}</net>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="reachable formal lane"):
        _select_disturbance_targets(network, ("A_0",))


def _paired_frame(candidate_delta: float = -10.0) -> pd.DataFrame:
    from experiments.matrix import FormalMatrix

    rows = []
    for scene in range(1, 21):
        for load in (1.0, 1.25):
            for seed in (42, 43, 44):
                baseline = 100.0 + scene + load + seed / 1000
                for algorithm, travel in (
                    ("fixed_time", baseline),
                    ("capacity_aware_maxpressure", baseline + candidate_delta),
                ):
                    rows.append(
                        {
                            "scene_id": str(scene),
                            "algorithm": algorithm,
                            "flow_multiplier": load,
                            "seed": seed,
                            "matrix_kind": "normal",
                            "avg_travel_time": travel,
                            "collision_count": 0,
                            "red_light_count": 0,
                            "illegal_transition_count": 0,
                            "harsh_braking_count": 3,
                            "teleport_count": 2,
                            "potential_conflict_count": 1,
                        }
                    )
    disturbance_specs = {
        (spec.scene_id, spec.disturbance.kind): spec
        for spec in FormalMatrix.disturbance()
        if spec.algorithm == "capacity_aware_maxpressure"
    }
    for scene in range(1, 21):
        for kind in ("construction", "event_demand", "vehicle_failure"):
            spec = disturbance_specs[(str(scene), kind)]
            disturbance = spec.disturbance
            rows.append(
                {
                    "run_key": spec.run_key,
                    "scene_id": str(scene),
                    "algorithm": "capacity_aware_maxpressure",
                    "flow_multiplier": 1.0,
                    "seed": 42,
                    "matrix_kind": "disturbance",
                    "disturbance_kind": kind,
                    "disturbance_begin_seconds": disturbance.begin_seconds,
                    "disturbance_end_seconds": disturbance.end_seconds,
                    "disturbance_target": disturbance.target,
                    "disturbance_intensity": disturbance.intensity,
                    "duration_seconds": spec.duration_seconds,
                    "warmup_seconds": spec.warmup_seconds,
                    "avg_travel_time": 110.0,
                    "collision_count": 0,
                    "red_light_count": 0,
                    "illegal_transition_count": 0,
                    "harsh_braking_count": 9,
                    "teleport_count": 8,
                    "potential_conflict_count": 7,
                }
            )
    return pd.DataFrame(rows)


def test_paired_statistics_uses_candidate_minus_baseline_and_degenerate_sd():
    """Catch reversed differences and non-JSON-safe zero-SD effect sizes."""
    from experiments.statistics import paired_statistics

    result = paired_statistics(
        _paired_frame(), "capacity_aware_maxpressure", "fixed_time"
    )

    assert result.mean_difference == pytest.approx(-10.0)
    assert result.differences == pytest.approx((-10.0,) * 120)
    assert result.relative_change < 0
    assert result.confidence_interval == pytest.approx((-10.0, -10.0))
    assert result.cohen_dz is None
    assert "zero_standard_deviation" in result.flags
    assert result.improved_unit_count == 40
    assert result.worst_unit == {"scene_id": "1", "flow_multiplier": 1.0}
    assert result.safety_eligible is True
    assert result.eligible is True


@pytest.mark.parametrize("bad_value", [0.0, -1.0, float("nan"), None])
def test_paired_statistics_rejects_invalid_baseline_values(bad_value):
    """Catch undefined relative changes being silently dropped or normalized."""
    from experiments.statistics import paired_statistics

    frame = _paired_frame()
    frame.loc[frame["algorithm"] == "fixed_time", "avg_travel_time"] = bad_value

    with pytest.raises(ValueError, match="baseline.*finite and > 0"):
        paired_statistics(frame, "capacity_aware_maxpressure", "fixed_time")


def test_paired_statistics_rejects_duplicate_pairs():
    """Catch a many-to-many merge inflating statistical significance."""
    from experiments.statistics import paired_statistics

    frame = _paired_frame()
    duplicate = frame[
        (frame["algorithm"] == "fixed_time")
        & (frame["scene_id"] == "1")
        & (frame["flow_multiplier"] == 1.0)
        & (frame["seed"] == 42)
    ]

    with pytest.raises(ValueError, match="duplicate paired unit"):
        paired_statistics(
            pd.concat([frame, duplicate], ignore_index=True),
            "capacity_aware_maxpressure",
            "fixed_time",
        )


@pytest.mark.parametrize("unsafe_value", [1, 0.0, True, "0"])
def test_candidate_safety_requires_strict_integer_zero(unsafe_value):
    """Catch observed safety fields or loosely typed zeroes passing the hard gate."""
    from experiments.statistics import paired_statistics

    frame = _paired_frame()
    frame["collision_count"] = frame["collision_count"].astype(object)
    candidate_index = frame.index[
        frame["algorithm"] == "capacity_aware_maxpressure"
    ][0]
    frame.loc[candidate_index, "collision_count"] = unsafe_value

    result = paired_statistics(
        frame, "capacity_aware_maxpressure", "fixed_time"
    )

    assert result.safety_eligible is False
    assert result.eligible is False


def test_candidate_safety_rejects_duplicate_disturbance_coverage():
    """Catch one missing disturbance unit hidden by a duplicate safety row."""
    from experiments.statistics import paired_statistics

    frame = _paired_frame()
    candidate_disturbance = frame[
        (frame["algorithm"] == "capacity_aware_maxpressure")
        & (frame["matrix_kind"] == "disturbance")
    ]
    missing_index = candidate_disturbance.index[-1]
    duplicate = candidate_disturbance.iloc[[0]]
    frame = pd.concat([frame.drop(index=missing_index), duplicate], ignore_index=True)

    result = paired_statistics(
        frame, "capacity_aware_maxpressure", "fixed_time"
    )

    assert result.safety_eligible is False
    assert result.eligible is False


@pytest.mark.parametrize(
    "column,bad_value",
    (
        ("flow_multiplier", 1.25),
        ("seed", 43),
        ("seed", 42.5),
        ("disturbance_begin_seconds", 601.0),
        ("disturbance_end_seconds", 1199.0),
        ("disturbance_target", "wrong-target"),
        ("disturbance_intensity", 0.5),
        ("duration_seconds", 3599),
        ("warmup_seconds", 599),
        ("run_key", "spoofed-key"),
    ),
)
def test_candidate_safety_requires_exact_frozen_disturbance_identity(
    column, bad_value
):
    """Catch malformed disturbance coverage passing by scene/kind alone."""
    from experiments.statistics import paired_statistics

    frame = _paired_frame()
    index = frame.index[frame["matrix_kind"] == "disturbance"][0]
    if column == "seed" and isinstance(bad_value, float):
        frame[column] = frame[column].astype(float)
    frame.loc[index, column] = bad_value

    result = paired_statistics(
        frame, "capacity_aware_maxpressure", "fixed_time"
    )

    assert result.safety_eligible is False
    assert result.eligible is False


def test_default_selection_falls_back_without_improvement_claim():
    """Catch publication of a candidate whose confidence interval is not below zero."""
    from experiments.statistics import select_default

    frame = _paired_frame(candidate_delta=10.0)
    selection = select_default(
        frame,
        candidates=("capacity_aware_maxpressure",),
        baseline="fixed_time",
    )

    assert selection.algorithm == "fixed_time"
    assert selection.improvement_claim is False


class _FailedMatrixService:
    def __init__(self, root: Path):
        self.root = root
        self.requests = []

    def run_sync(self, request):
        self.requests.append(request)
        manifest = json.loads(
            (self.root.parent / "matrix_manifest.json").read_text(encoding="utf-8")
        )
        assert len(manifest["specs"]) == manifest["expected_run_count"]
        run_id = (
            "failed-"
            f"{len(list(self.root.rglob('failed-*'))) + 1}"
        )
        run_dir = (
            self.root
            / f"i{request.intersection_id}"
            / request.algorithm
            / f"x{request.flow_multiplier:g}"
            / f"s{request.seed}"
            / run_id
        )
        run_dir.mkdir(parents=True)
        (run_dir / "status.json").write_text(
            json.dumps(
                {"run_id": run_id, "status": "failed", "reason": "synthetic"}
            ),
            encoding="utf-8",
        )
        return RunResult(
            run_id=run_id,
            status=RunStatus.FAILED,
            reason="synthetic",
            run_dir=run_dir,
            algorithm=request.algorithm,
        )


def test_run_matrix_rejects_duplicates_before_output_or_service(tmp_path):
    """Catch duplicate keys after manifest creation or RunService construction."""
    from experiments.matrix import FormalMatrix, run_matrix

    spec = FormalMatrix.normal()[0]
    output_root = tmp_path / "must-not-exist"
    service = _FailedMatrixService(output_root / "runs")

    with pytest.raises(ValueError, match="duplicate run key"):
        run_matrix((spec, spec), output_root, resume=False, run_service=service)

    assert service.requests == []
    assert not output_root.exists()


def test_failed_run_is_retried_with_parent_attempt_chain(tmp_path):
    """Catch failed evidence being overwritten or losing retry lineage."""
    from experiments.matrix import FormalMatrix, run_matrix

    spec = FormalMatrix.normal()[0]
    first_service = _FailedMatrixService(tmp_path / "runs")
    first = run_matrix(
        (spec,), tmp_path, resume=False, run_service=first_service
    )
    first_manifest = json.loads(
        (tmp_path / "matrix_manifest.json").read_text(encoding="utf-8")
    )
    first_run_dir = Path(
        first_manifest["attempt_chains"][spec.run_key][0]["run_dir"]
    )
    first_run_bytes = {
        path.relative_to(first_run_dir): path.read_bytes()
        for path in first_run_dir.rglob("*")
        if path.is_file()
    }
    second_service = _FailedMatrixService(tmp_path / "runs")
    second = run_matrix(
        (spec,), tmp_path, resume=True, run_service=second_service
    )

    manifest = json.loads(
        (tmp_path / "matrix_manifest.json").read_text(encoding="utf-8")
    )
    attempts = manifest["attempt_chains"][spec.run_key]
    assert len(attempts) == 2
    assert attempts[0]["run_id"] != attempts[1]["run_id"]
    assert attempts[1]["parent_failure"] == {
        "run_id": attempts[0]["run_id"],
        "status": "failed",
    }
    assert first.failed == 1
    assert second.retried == 1
    assert {
        path.relative_to(first_run_dir): path.read_bytes()
        for path in first_run_dir.rglob("*")
        if path.is_file()
    } == first_run_bytes
    assert not list(tmp_path.glob(".*.tmp"))


def test_corrupt_completed_attempt_stops_without_retry(tmp_path):
    """Catch a completed status with invalid strict evidence being treated as missing."""
    from experiments.matrix import CorruptCompletedRunError, FormalMatrix, run_matrix

    spec = FormalMatrix.normal()[0]
    service = _FailedMatrixService(tmp_path / "runs")
    run_matrix((spec,), tmp_path, resume=False, run_service=service)
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attempt = manifest["attempt_chains"][spec.run_key][0]
    attempt["status"] = "completed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    status_path = Path(attempt["run_dir"]) / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["status"] = "completed"
    status_path.write_text(json.dumps(status), encoding="utf-8")
    retry_service = _FailedMatrixService(tmp_path / "runs")

    with pytest.raises(CorruptCompletedRunError, match="strict evidence"):
        run_matrix((spec,), tmp_path, resume=True, run_service=retry_service)

    assert retry_service.requests == []
    unchanged = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(unchanged["attempt_chains"][spec.run_key]) == 1


@pytest.mark.parametrize(
    "disk_corruption",
    ("missing_run_directory", "missing_status", "failed_status"),
)
def test_manifest_completed_attempt_never_degrades_into_retry(
    tmp_path, disk_corruption
):
    """Catch disk damage overwriting a completed manifest state before retry logic."""
    from experiments.matrix import CorruptCompletedRunError, FormalMatrix, run_matrix

    spec = FormalMatrix.normal()[0]
    service = _FailedMatrixService(tmp_path / "runs")
    run_matrix((spec,), tmp_path, resume=False, run_service=service)
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attempt = manifest["attempt_chains"][spec.run_key][0]
    attempt["status"] = "completed"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    run_dir = Path(attempt["run_dir"])
    if disk_corruption == "missing_run_directory":
        run_dir.rename(tmp_path / "held-completed-run")
    elif disk_corruption == "missing_status":
        (run_dir / "status.json").unlink()
    manifest_before = manifest_path.read_bytes()
    retry_service = _FailedMatrixService(tmp_path / "runs")

    with pytest.raises(CorruptCompletedRunError, match="completed"):
        run_matrix((spec,), tmp_path, resume=True, run_service=retry_service)

    assert retry_service.requests == []
    assert manifest_path.read_bytes() == manifest_before


class _DuplicateRunService:
    def __init__(self, previous_attempt):
        self.previous_attempt = previous_attempt
        self.requests = []

    def run_sync(self, request):
        self.requests.append(request)
        return RunResult(
            run_id=self.previous_attempt["run_id"],
            status=RunStatus.FAILED,
            reason="synthetic duplicate",
            run_dir=Path(self.previous_attempt["run_dir"]),
            algorithm=request.algorithm,
        )


class _CrossSpecDuplicateRunService:
    def __init__(self, root: Path):
        self.root = root
        self.requests = []

    def run_sync(self, request):
        self.requests.append(request)
        run_id = "shared-run-id"
        run_dir = (
            self.root
            / f"i{request.intersection_id}"
            / request.algorithm
            / f"x{request.flow_multiplier:g}"
            / f"s{request.seed}"
            / run_id
        )
        run_dir.mkdir(parents=True)
        (run_dir / "status.json").write_text(
            json.dumps({"run_id": run_id, "status": "failed", "reason": ""}),
            encoding="utf-8",
        )
        return RunResult(
            run_id=run_id,
            status=RunStatus.FAILED,
            reason="synthetic duplicate",
            run_dir=run_dir,
            algorithm=request.algorithm,
        )


class _NonTerminalRunService(_CrossSpecDuplicateRunService):
    def run_sync(self, request):
        result = super().run_sync(request)
        status_path = result.run_dir / "status.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["status"] = "running"
        status_path.write_text(json.dumps(status), encoding="utf-8")
        return RunResult(
            run_id=result.run_id,
            status=RunStatus.RUNNING,
            reason="still running",
            run_dir=result.run_dir,
            algorithm=request.algorithm,
        )


def test_retry_rejects_reused_run_id_and_directory(tmp_path):
    """Catch a retry aliasing an earlier immutable attempt directory."""
    from experiments.matrix import FormalMatrix, MatrixIntegrityError, run_matrix

    spec = FormalMatrix.normal()[0]
    run_matrix(
        (spec,),
        tmp_path,
        resume=False,
        run_service=_FailedMatrixService(tmp_path / "runs"),
    )
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    previous_attempt = manifest["attempt_chains"][spec.run_key][0]
    manifest_before = manifest_path.read_bytes()
    service = _DuplicateRunService(previous_attempt)

    with pytest.raises(MatrixIntegrityError, match="unique run id"):
        run_matrix((spec,), tmp_path, resume=True, run_service=service)

    assert len(service.requests) == 1
    assert manifest_path.read_bytes() == manifest_before


def test_live_result_run_id_must_be_unique_across_all_specs(tmp_path):
    """Catch a service returning one run identity for two frozen matrix units."""
    from experiments.matrix import FormalMatrix, MatrixIntegrityError, run_matrix

    specs = FormalMatrix.normal()[:2]
    service = _CrossSpecDuplicateRunService(tmp_path / "runs")

    with pytest.raises(MatrixIntegrityError, match="unique run id"):
        run_matrix(specs, tmp_path, resume=False, run_service=service)

    assert len(service.requests) == 2
    manifest = json.loads(
        (tmp_path / "matrix_manifest.json").read_text(encoding="utf-8")
    )
    assert len(manifest["attempt_chains"][specs[0].run_key]) == 1
    assert manifest["attempt_chains"][specs[1].run_key] == []


def test_live_non_terminal_result_is_not_recorded_as_an_attempt(tmp_path):
    """Catch a still-running service result becoming retryable manifest history."""
    from experiments.matrix import FormalMatrix, MatrixIntegrityError, run_matrix

    spec = FormalMatrix.normal()[0]

    with pytest.raises(MatrixIntegrityError, match="terminal"):
        run_matrix(
            (spec,),
            tmp_path,
            resume=False,
            run_service=_NonTerminalRunService(tmp_path / "runs"),
        )

    manifest = json.loads(
        (tmp_path / "matrix_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["attempt_chains"][spec.run_key] == []


@pytest.mark.parametrize(
    "corruption",
    (
        "duplicate_attempt",
        "bad_parent",
        "historical_status_mismatch",
        "historical_status_missing",
    ),
)
def test_resume_validates_entire_attempt_lineage_before_service(
    tmp_path, corruption
):
    """Catch a valid-looking latest attempt hiding corrupt immutable history."""
    from experiments.matrix import FormalMatrix, MatrixIntegrityError, run_matrix

    spec = FormalMatrix.normal()[0]
    run_matrix(
        (spec,),
        tmp_path,
        resume=False,
        run_service=_FailedMatrixService(tmp_path / "runs"),
    )
    run_matrix(
        (spec,),
        tmp_path,
        resume=True,
        run_service=_FailedMatrixService(tmp_path / "runs"),
    )
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attempts = manifest["attempt_chains"][spec.run_key]
    if corruption == "duplicate_attempt":
        attempts[1]["run_id"] = attempts[0]["run_id"]
        attempts[1]["run_dir"] = attempts[0]["run_dir"]
    elif corruption == "bad_parent":
        attempts[1]["parent_failure"]["run_id"] = "wrong-parent"
    elif corruption == "historical_status_mismatch":
        status_path = Path(attempts[0]["run_dir"]) / "status.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        status["status"] = "interrupted"
        status_path.write_text(json.dumps(status), encoding="utf-8")
    else:
        (Path(attempts[0]["run_dir"]) / "status.json").unlink()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_before = manifest_path.read_bytes()
    service = _FailedMatrixService(tmp_path / "runs")

    with pytest.raises(MatrixIntegrityError, match="attempt|parent|status|duplicate"):
        run_matrix((spec,), tmp_path, resume=True, run_service=service)

    assert service.requests == []
    assert manifest_path.read_bytes() == manifest_before


def test_resume_rejects_cross_spec_duplicate_run_id_before_service(tmp_path):
    """Catch globally aliased attempt identities across otherwise valid spec paths."""
    from experiments.matrix import FormalMatrix, MatrixIntegrityError, run_matrix

    specs = FormalMatrix.normal()[:2]
    run_matrix(
        specs,
        tmp_path,
        resume=False,
        run_service=_FailedMatrixService(tmp_path / "runs"),
    )
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first = manifest["attempt_chains"][specs[0].run_key][0]
    second = manifest["attempt_chains"][specs[1].run_key][0]
    old_dir = Path(second["run_dir"])
    new_dir = old_dir.with_name(first["run_id"])
    old_dir.rename(new_dir)
    status_path = new_dir / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["run_id"] = first["run_id"]
    status_path.write_text(json.dumps(status), encoding="utf-8")
    second["run_id"] = first["run_id"]
    second["run_dir"] = str(new_dir)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    service = _FailedMatrixService(tmp_path / "runs")

    with pytest.raises(MatrixIntegrityError, match="duplicate run id"):
        run_matrix(specs, tmp_path, resume=True, run_service=service)

    assert service.requests == []


def test_resume_rejects_attempt_run_directory_outside_matrix_root(tmp_path):
    """Catch a valid-looking attempt redirected to unrelated evidence."""
    from experiments.matrix import FormalMatrix, MatrixIntegrityError, run_matrix

    spec = FormalMatrix.normal()[0]
    service = _FailedMatrixService(tmp_path / "runs")
    run_matrix((spec,), tmp_path, resume=False, run_service=service)
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attempt = manifest["attempt_chains"][spec.run_key][0]
    outside = tmp_path.parent / "outside-attempt"
    outside.mkdir(exist_ok=True)
    (outside / "status.json").write_text(
        json.dumps({
            "run_id": attempt["run_id"],
            "status": "failed",
            "reason": "redirected",
        }),
        encoding="utf-8",
    )
    attempt["run_dir"] = str(outside)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(MatrixIntegrityError, match="run directory"):
        run_matrix(
            (spec,),
            tmp_path,
            resume=True,
            run_service=_FailedMatrixService(tmp_path / "runs"),
        )


def test_output_root_lock_fails_closed_without_mutating_manifest(tmp_path):
    """Catch two writers concurrently publishing the same matrix root."""
    from experiments.matrix import MatrixLockedError, _matrix_lock

    tmp_path.mkdir(exist_ok=True)
    manifest_path = tmp_path / "matrix_manifest.json"
    manifest_path.write_text("sentinel", encoding="utf-8")

    with _matrix_lock(tmp_path):
        with pytest.raises(MatrixLockedError):
            with _matrix_lock(tmp_path):
                pass

    assert manifest_path.read_text(encoding="utf-8") == "sentinel"


def test_formal_cli_profile_builds_exact_frozen_540_specs(tmp_path):
    """Catch formal CLI overrides of seeds or time windows."""
    from scripts.run_pdf_matrix import build_profile_matrix, parse_matrix_args

    args = parse_matrix_args(
        ["--profile", "formal", "--output-root", str(tmp_path), "--resume"]
    )
    specs = build_profile_matrix(args)

    assert len(specs) == 540
    assert {spec.seed for spec in specs if spec.matrix_kind == "normal"} == {
        42,
        43,
        44,
    }
    assert all(spec.duration_seconds == 3600 for spec in specs)
    assert all(spec.warmup_seconds == 600 for spec in specs)
    assert all("steps" not in spec.to_payload() for spec in specs)
    assert all("steps_origin" not in spec.to_payload() for spec in specs)
    assert all(spec.to_request(tmp_path / "runs").steps is None for spec in specs)
    assert all(
        spec.to_request(tmp_path / "runs").steps_origin == "none"
        for spec in specs
    )
    assert args.resume is True


def test_formal_runspec_roundtrip_accepts_explicit_none_steps(tmp_path):
    """Catch legacy seconds-first payloads with an explicit null step field."""
    from experiments.matrix import FormalMatrix, RunSpec

    spec = FormalMatrix.normal()[0]
    payload = spec.to_payload()
    payload["steps"] = None
    payload["steps_origin"] = "none"

    restored = RunSpec.from_payload(payload)

    assert restored.run_key == spec.run_key
    assert restored.to_request(tmp_path / "runs").steps is None


@pytest.mark.parametrize(
    "override",
    [
        ["--seed", "42"],
        ["--duration-seconds", "600"],
        ["--warmup-seconds", "60"],
    ],
)
def test_formal_cli_rejects_seed_or_window_override(tmp_path, override):
    """Catch a formal invocation that is not the frozen judge-facing design."""
    from scripts.run_pdf_matrix import build_profile_matrix, parse_matrix_args

    args = parse_matrix_args(
        ["--profile", "formal", "--output-root", str(tmp_path), *override]
    )
    with pytest.raises(ValueError, match="formal profile"):
        build_profile_matrix(args)


def test_smoke_cli_accepts_explicit_seed_and_seconds(tmp_path):
    """Catch formal restrictions leaking into bounded developer profiles."""
    from scripts.run_pdf_matrix import build_profile_matrix, parse_matrix_args

    args = parse_matrix_args([
        "--profile", "smoke",
        "--output-root", str(tmp_path),
        "--seed", "7",
        "--duration-seconds", "20",
        "--warmup-seconds", "5",
    ])

    specs = build_profile_matrix(args)
    assert {spec.seed for spec in specs} == {7}
    assert {spec.duration_seconds for spec in specs} == {20}
    assert {spec.warmup_seconds for spec in specs} == {5}
    requests = [spec.to_request(tmp_path / "runs") for spec in specs]
    assert {request.steps for request in requests} == {None}
    assert {request.steps_origin for request in requests} == {"none"}


def test_default_smoke_cli_requests_100_actual_steps(tmp_path):
    """Catch smoke duration being converted through a scene-specific timebase."""
    from scripts.run_pdf_matrix import build_profile_matrix, parse_matrix_args

    args = parse_matrix_args([
        "--profile", "smoke", "--output-root", str(tmp_path)
    ])

    specs = build_profile_matrix(args)
    requests = [spec.to_request(tmp_path / "runs") for spec in specs]

    assert len(specs) == 1
    assert specs[0].to_payload()["steps"] == 100
    assert specs[0].to_payload()["steps_origin"] == "explicit"
    assert specs[0].duration_seconds == 100
    assert specs[0].warmup_seconds == 0
    assert {request.steps for request in requests} == {100}
    assert {request.steps_origin for request in requests} == {"explicit"}
    assert {request.duration_seconds for request in requests} == {100}
    assert {request.warmup_seconds for request in requests} == {0}
    restored = type(specs[0]).from_payload(specs[0].to_payload())
    assert restored.run_key == specs[0].run_key


@pytest.mark.parametrize(
    "override",
    (["--duration-seconds", "20"], ["--warmup-seconds", "5"]),
)
def test_any_explicit_smoke_window_flag_uses_seconds_first(tmp_path, override):
    """Catch one explicit time flag being silently ignored by 100-step smoke."""
    from scripts.run_pdf_matrix import build_profile_matrix, parse_matrix_args

    args = parse_matrix_args([
        "--profile", "smoke", "--output-root", str(tmp_path), *override
    ])

    request = build_profile_matrix(args)[0].to_request(tmp_path / "runs")

    assert request.steps is None
    assert request.steps_origin == "none"


def test_quick_cli_defaults_to_three_frozen_seeds(tmp_path):
    """Catch the quick profile silently shrinking the legacy 54-case check."""
    from scripts.run_pdf_matrix import build_profile_matrix, parse_matrix_args

    args = parse_matrix_args([
        "--profile", "quick", "--output-root", str(tmp_path)
    ])

    specs = build_profile_matrix(args)
    assert len(specs) == 54
    assert {spec.seed for spec in specs} == {42, 43, 44}
    assert all(spec.duration_seconds == 600 for spec in specs)
    assert all(spec.to_request(tmp_path / "runs").steps is None for spec in specs)
    assert all(
        spec.to_request(tmp_path / "runs").steps_origin == "none"
        for spec in specs
    )
