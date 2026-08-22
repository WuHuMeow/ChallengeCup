"""Frozen, deterministic contracts for the judge-facing experiment matrix."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from contextlib import contextmanager
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import threading
from collections.abc import Mapping, Sequence
import xml.etree.ElementTree as ET
from uuid import uuid4

from core.config import get_config
from core.run_models import DisturbanceSpec, RunRequest, RunStatus
from engine.artifacts import CorruptStatusArtifactError, RunArtifacts
from engine.run_service import RunService
from experiments.evidence import EvidenceReader
from scenes.registry import SceneRegistry


FORMAL_ALGORITHMS = (
    "fixed_time",
    "classic_maxpressure",
    "capacity_aware_maxpressure",
)
FORMAL_FLOWS = (1.0, 1.25)
FORMAL_SEEDS = (42, 43, 44)
FORMAL_DURATION_SECONDS = 3600.0
FORMAL_WARMUP_SECONDS = 600.0
MATRIX_METRIC_COLUMNS = (
    "avg_travel_time",
    "avg_delay",
    "avg_queue_length",
    "throughput",
    "total_stops",
    "fuel_consumption",
)
MATRIX_SAFETY_COLUMNS = (
    "collision_count",
    "red_light_count",
    "illegal_transition_count",
    "harsh_braking_count",
    "teleport_count",
    "potential_conflict_count",
)


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass(frozen=True)
class RunSpec:
    """One immutable unit of the frozen formal experiment matrix."""

    scene_id: str
    algorithm: str
    flow_multiplier: float
    seed: int
    duration_seconds: float = FORMAL_DURATION_SECONDS
    warmup_seconds: float = FORMAL_WARMUP_SECONDS
    disturbance: DisturbanceSpec | None = None
    algorithm_params: dict[str, float] = field(default_factory=dict)
    steps: int | None = None

    def __post_init__(self) -> None:
        # Reuse the public request validator without binding an output path.
        request = self.to_request(None)
        object.__setattr__(self, "scene_id", request.intersection_id)
        object.__setattr__(self, "algorithm", request.algorithm)
        object.__setattr__(self, "flow_multiplier", request.flow_multiplier)
        object.__setattr__(self, "seed", request.seed)
        object.__setattr__(self, "duration_seconds", request.duration_seconds)
        object.__setattr__(self, "warmup_seconds", request.warmup_seconds)
        object.__setattr__(self, "algorithm_params", request.algorithm_params)
        object.__setattr__(
            self,
            "steps",
            int(request.steps) if request.steps is not None else None,
        )

    @property
    def intersection_id(self) -> str:
        return self.scene_id

    @property
    def matrix_kind(self) -> str:
        return "disturbance" if self.disturbance is not None else "normal"

    @property
    def run_key(self) -> str:
        return _canonical_json(self.to_payload())

    def to_payload(self) -> dict[str, object]:
        payload = {
            "scene_id": self.scene_id,
            "algorithm": self.algorithm,
            "flow_multiplier": self.flow_multiplier,
            "seed": self.seed,
            "duration_seconds": self.duration_seconds,
            "warmup_seconds": self.warmup_seconds,
            "disturbance": (
                asdict(self.disturbance) if self.disturbance is not None else None
            ),
            "algorithm_params": dict(sorted(self.algorithm_params.items())),
        }
        if self.steps is not None:
            payload["steps"] = self.steps
            payload["steps_origin"] = "explicit"
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "RunSpec":
        values = dict(payload)
        steps_present = "steps" in values
        steps_origin = values.pop("steps_origin", None)
        if steps_present and values["steps"] is None:
            if steps_origin not in (None, "none"):
                raise ValueError("null RunSpec steps require steps_origin 'none'")
        elif steps_present and steps_origin != "explicit":
            raise ValueError("RunSpec explicit steps require steps_origin 'explicit'")
        if not steps_present and steps_origin is not None:
            raise ValueError("RunSpec steps_origin requires explicit steps")
        disturbance = values.get("disturbance")
        if isinstance(disturbance, dict):
            values["disturbance"] = DisturbanceSpec(**disturbance)
        return cls(**values)

    def to_request(self, output_root: Path | None) -> RunRequest:
        return RunRequest(
            intersection_id=self.scene_id,
            algorithm=self.algorithm,
            flow_multiplier=self.flow_multiplier,
            seed=self.seed,
            duration_seconds=self.duration_seconds,
            warmup_seconds=self.warmup_seconds,
            output_root=output_root,
            disturbance=self.disturbance,
            algorithm_params=self.algorithm_params,
            steps=self.steps,
        )


def _select_disturbance_targets(
    network_file: Path,
    manifest_lane_ids: tuple[str, ...],
) -> tuple[str, str]:
    """Select the first stable reachable ``(lane, edge)`` formal target."""
    root = ET.parse(network_file).getroot()
    formal_lanes = set(manifest_lane_ids)
    continuations: dict[str, set[str]] = {}
    for connection in root.findall("connection"):
        source = connection.get("from", "")
        target = connection.get("to", "")
        if source and target and not source.startswith(":") and not target.startswith(":"):
            continuations.setdefault(source, set()).add(target)

    candidates: list[tuple[str, str, str]] = []
    for edge_node in root.findall("edge"):
        edge = edge_node.get("id", "")
        if not edge or edge.startswith(":"):
            continue
        for lane_node in edge_node.findall("lane"):
            lane = lane_node.get("id", "")
            if not lane or lane.startswith(":") or lane not in formal_lanes:
                continue
            try:
                length = float(lane_node.get("length", "nan"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(length) or length <= 0:
                continue
            for continuation in continuations.get(edge, ()):
                candidates.append((edge, lane, continuation))

    if not candidates:
        raise ValueError(f"scene network has no reachable formal lane: {network_file}")
    edge, lane, _ = min(candidates)
    return lane, edge


class FormalMatrix:
    """Factory for the 360 normal and 180 disturbance frozen specs."""

    @staticmethod
    def normal() -> tuple[RunSpec, ...]:
        return tuple(
            RunSpec(str(scene), algorithm, flow, seed)
            for scene in range(1, 21)
            for algorithm in FORMAL_ALGORITHMS
            for flow in FORMAL_FLOWS
            for seed in FORMAL_SEEDS
        )

    @staticmethod
    def disturbance() -> tuple[RunSpec, ...]:
        config = get_config()
        registry = SceneRegistry()
        manifests = {
            manifest.scene_id: manifest
            for manifest in registry.list_scenes(formal_only=True)
        }
        expected = {str(scene) for scene in range(1, 21)}
        if set(manifests) != expected:
            raise ValueError("all 20 validated formal scene manifests are required")

        specs: list[RunSpec] = []
        for scene in range(1, 21):
            scene_id = str(scene)
            manifest = manifests[scene_id]
            lane, edge = _select_disturbance_targets(
                registry.get_meta(scene_id).sumo_net,
                manifest.lane_ids,
            )
            for algorithm in FORMAL_ALGORITHMS:
                for kind in ("construction", "event_demand", "vehicle_failure"):
                    prefix = f"scene.disturbance_defaults.{kind}"
                    disturbance = DisturbanceSpec(
                        kind=kind,
                        begin_seconds=float(config.get(f"{prefix}.begin_seconds")),
                        end_seconds=float(config.get(f"{prefix}.end_seconds")),
                        target=edge if kind == "event_demand" else lane,
                        intensity=float(config.get(f"{prefix}.intensity")),
                    )
                    specs.append(
                        RunSpec(
                            scene_id,
                            algorithm,
                            1.0,
                            42,
                            disturbance=disturbance,
                        )
                    )
        return tuple(specs)

    @classmethod
    def all(cls) -> tuple[RunSpec, ...]:
        return cls.normal() + cls.disturbance()


class MatrixLockedError(RuntimeError):
    """The output root already has an active matrix writer."""


class CorruptCompletedRunError(RuntimeError):
    """A completed attempt is not valid strict evidence for its exact spec."""


class MatrixIntegrityError(RuntimeError):
    """Persisted matrix state is malformed or does not match the request."""


class MatrixEvidenceError(ValueError):
    """A matrix result row is not bound to its frozen sealed evidence."""


@dataclass(frozen=True)
class MatrixEntry:
    run_key: str
    run_id: str
    status: str
    reason: str
    run_dir: Path
    parent_failure: dict[str, str] | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "run_key": self.run_key,
            "run_id": self.run_id,
            "status": self.status,
            "reason": self.reason,
            "run_dir": str(self.run_dir),
            "parent_failure": self.parent_failure,
        }


@dataclass(frozen=True)
class MatrixReport:
    entries: tuple[MatrixEntry, ...]
    manifest_path: Path
    results_path: Path
    expected_keys: tuple[str, ...]
    skipped: int = 0
    retried: int = 0

    @property
    def completed(self) -> int:
        return sum(entry.status == RunStatus.COMPLETED.value for entry in self.entries)

    @property
    def failed(self) -> int:
        return sum(entry.status != RunStatus.COMPLETED.value for entry in self.entries)


_ACTIVE_MATRIX_ROOTS: set[str] = set()
_ACTIVE_MATRIX_ROOTS_GUARD = threading.Lock()


@contextmanager
def _matrix_lock(output_root: Path):
    """Hold a process- and OS-exclusive non-blocking lock for one output root."""
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    resolved = os.path.normcase(str(output_root.resolve()))
    with _ACTIVE_MATRIX_ROOTS_GUARD:
        if resolved in _ACTIVE_MATRIX_ROOTS:
            raise MatrixLockedError(f"matrix output root is locked: {output_root}")
        _ACTIVE_MATRIX_ROOTS.add(resolved)

    lock_path = output_root / ".matrix.lock"
    handle = None
    locked = False
    try:
        handle = lock_path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - exercised by Linux CI only
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise MatrixLockedError(
                f"matrix output root is locked: {output_root}"
            ) from exc
        locked = True
        yield
    finally:
        if handle is not None:
            if locked:
                try:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:  # pragma: no cover - exercised by Linux CI only
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            handle.close()
        with _ACTIVE_MATRIX_ROOTS_GUARD:
            _ACTIVE_MATRIX_ROOTS.discard(resolved)


def _atomic_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: object) -> None:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    _atomic_bytes(path, encoded)


def _matrix_digest(specs: Sequence[RunSpec]) -> str:
    encoded = _canonical_json([spec.to_payload() for spec in specs]).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _new_manifest(specs: tuple[RunSpec, ...]) -> dict[str, object]:
    return {
        "schema": "challenge-cup-formal-matrix",
        "schema_version": 1,
        "expected_run_count": len(specs),
        "matrix_digest": _matrix_digest(specs),
        "specs": [
            {"run_key": spec.run_key, "request": spec.to_payload()}
            for spec in specs
        ],
        "attempt_chains": {spec.run_key: [] for spec in specs},
    }


def _load_manifest(path: Path, specs: tuple[RunSpec, ...]) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise MatrixIntegrityError(f"matrix manifest is corrupt: {exc}") from exc
    expected = _new_manifest(specs)
    for manifest_field in (
        "schema",
        "schema_version",
        "expected_run_count",
        "matrix_digest",
        "specs",
    ):
        if payload.get(manifest_field) != expected[manifest_field]:
            raise MatrixIntegrityError(
                f"matrix manifest {manifest_field} does not match request"
            )
    attempts = payload.get("attempt_chains")
    if not isinstance(attempts, dict) or set(attempts) != {
        spec.run_key for spec in specs
    }:
        raise MatrixIntegrityError("matrix manifest attempt chains are malformed")
    if any(not isinstance(chain, list) for chain in attempts.values()):
        raise MatrixIntegrityError("matrix manifest attempt chain must be a list")
    _validate_manifest_attempts(payload, specs, path.parent / "runs")
    return payload


def _status_for_attempt(spec: RunSpec, attempt: dict[str, object]) -> dict[str, object] | None:
    run_dir = Path(str(attempt.get("run_dir", "")))
    run_id = str(attempt.get("run_id", ""))
    if not run_id or not run_dir.exists():
        return None
    artifacts = RunArtifacts(
        run_dir=run_dir,
        intersection_id=spec.scene_id,
        algorithm=spec.algorithm,
        flow_multiplier=spec.flow_multiplier,
        seed=spec.seed,
        run_id=run_id,
    )
    if not artifacts.status.exists():
        return None
    try:
        return artifacts.read_status()
    except CorruptStatusArtifactError as exc:
        raise MatrixIntegrityError(str(exc)) from exc


def _validate_manifest_attempts(
    manifest: dict[str, object],
    specs: tuple[RunSpec, ...],
    runs_root: Path,
) -> None:
    retryable = {
        RunStatus.FAILED.value,
        RunStatus.INTERRUPTED.value,
        RunStatus.STOPPED.value,
        RunStatus.ENDED_EARLY.value,
        RunStatus.DISCONNECTED.value,
    }
    valid_statuses = {status.value for status in RunStatus}
    seen_run_ids: set[str] = set()
    seen_run_dirs: set[str] = set()
    attempts = manifest["attempt_chains"]
    for spec in specs:
        chain = attempts[spec.run_key]
        previous: dict[str, object] | None = None
        for index, attempt in enumerate(chain):
            if not isinstance(attempt, dict):
                raise MatrixIntegrityError("matrix manifest attempt must be an object")
            run_id = str(attempt.get("run_id", "")).strip()
            status = str(attempt.get("status", ""))
            if not run_id:
                raise MatrixIntegrityError("matrix manifest attempt has empty run id")
            if status not in valid_statuses:
                raise MatrixIntegrityError(
                    f"matrix manifest attempt has invalid status: {status}"
                )
            try:
                run_dir = _validate_run_directory(
                    spec,
                    Path(str(attempt.get("run_dir", ""))),
                    run_id,
                    runs_root,
                )
            except MatrixIntegrityError as exc:
                if status == RunStatus.COMPLETED.value:
                    raise CorruptCompletedRunError(
                        "completed run has invalid manifest directory"
                    ) from exc
                raise
            normalized_dir = os.path.normcase(str(run_dir))
            if run_id in seen_run_ids:
                raise MatrixIntegrityError(
                    f"matrix manifest has duplicate run id: {run_id}"
                )
            if normalized_dir in seen_run_dirs:
                raise MatrixIntegrityError(
                    f"matrix manifest has duplicate attempt directory: {run_dir}"
                )
            seen_run_ids.add(run_id)
            seen_run_dirs.add(normalized_dir)

            expected_parent = None
            if previous is not None:
                expected_parent = {
                    "run_id": str(previous["run_id"]),
                    "status": str(previous["status"]),
                }
            if attempt.get("parent_failure") != expected_parent:
                raise MatrixIntegrityError(
                    "matrix manifest attempt parent does not match previous failure"
                )
            if previous is not None and str(previous["status"]) not in retryable:
                raise MatrixIntegrityError(
                    "matrix manifest attempt follows a non-retryable parent"
                )
            try:
                disk_status = _status_for_attempt(spec, attempt)
            except MatrixIntegrityError as exc:
                if status == RunStatus.COMPLETED.value:
                    raise CorruptCompletedRunError(
                        "completed run has corrupt status artifact"
                    ) from exc
                raise
            if disk_status is None:
                if status == RunStatus.COMPLETED.value:
                    raise CorruptCompletedRunError(
                        "completed run is missing its status artifact"
                    )
                raise MatrixIntegrityError(
                    "matrix manifest attempt is missing its status artifact"
                )
            if str(disk_status.get("status", "")) != status:
                if status == RunStatus.COMPLETED.value:
                    raise CorruptCompletedRunError(
                        "completed run disk status is not completed"
                    )
                raise MatrixIntegrityError(
                    "matrix manifest attempt status differs from disk status"
                )
            if status == RunStatus.COMPLETED.value:
                request = spec.to_request(Path(runs_root))
                if not _strict_is_complete(run_dir, request):
                    raise CorruptCompletedRunError(
                        "completed run is not strict evidence for exact request"
                    )
            elif index < len(chain) - 1 and status not in retryable:
                raise MatrixIntegrityError(
                    "matrix manifest attempt chain contains non-retryable history"
                )
            previous = attempt


def _validate_run_directory(
    spec: RunSpec,
    run_dir: Path,
    run_id: str,
    runs_root: Path,
) -> Path:
    reserved_names = {"CON", "PRN", "AUX", "NUL"}
    invalid_chars = set('<>:"/\\|?*')
    if (
        not run_id
        or run_id in {".", ".."}
        or "/" in run_id
        or "\\" in run_id
        or any(ord(char) < 32 or char in invalid_chars for char in run_id)
        or run_id[-1] in {".", " "}
    ):
        raise MatrixIntegrityError(
            "matrix attempt run id must be a safe single path component"
        )
    windows_stem = run_id.split(".", 1)[0].upper()
    if (
        windows_stem in reserved_names
        or (
            len(windows_stem) == 4
            and windows_stem[:3] in {"COM", "LPT"}
            and windows_stem[3] in "123456789"
        )
    ):
        raise MatrixIntegrityError(
            "matrix attempt run id must be a safe single path component"
        )
    resolved_root = Path(runs_root).resolve()
    expected = (
        resolved_root
        / f"i{spec.scene_id}"
        / spec.algorithm
        / f"x{spec.flow_multiplier:g}"
        / f"s{spec.seed}"
        / run_id
    ).resolve()
    resolved = Path(run_dir).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise MatrixIntegrityError(
            "attempt run directory is outside the matrix runs root"
        ) from exc
    if resolved != expected:
        raise MatrixIntegrityError(
            f"attempt run directory does not match frozen spec: {resolved}"
        )
    return resolved


def _strict_is_complete(run_dir: Path, request: RunRequest) -> bool:
    # Kept lazy so scripts.run_pdf_matrix can remain a backwards-compatible
    # adapter without creating an import cycle.
    from scripts.run_pdf_matrix import is_complete

    return is_complete(run_dir, request)


def _identity_float(row: Mapping[str, str], name: str, expected: float) -> None:
    try:
        actual = float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise MatrixEvidenceError(f"matrix row identity has invalid {name}") from exc
    if not math.isfinite(actual) or actual != float(expected):
        raise MatrixEvidenceError(f"matrix row identity differs for {name}")


def _identity_int(row: Mapping[str, str], name: str, expected: int) -> None:
    try:
        actual = float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise MatrixEvidenceError(f"matrix row identity has invalid {name}") from exc
    if not math.isfinite(actual) or not actual.is_integer() or int(actual) != expected:
        raise MatrixEvidenceError(f"matrix row identity differs for {name}")


def _validate_result_identity(spec: RunSpec, row: Mapping[str, str]) -> None:
    expected_text = {
        "run_key": spec.run_key,
        "scene_id": spec.scene_id,
        "intersection_id": spec.intersection_id,
        "algorithm": spec.algorithm,
        "matrix_kind": spec.matrix_kind,
        "steps": str(spec.steps) if spec.steps is not None else "",
        "steps_origin": "explicit" if spec.steps is not None else "none",
    }
    for name, expected in expected_text.items():
        if str(row.get(name, "")) != expected:
            raise MatrixEvidenceError(f"matrix row identity differs for {name}")
    _identity_float(row, "flow_multiplier", spec.flow_multiplier)
    _identity_int(row, "seed", spec.seed)
    _identity_float(row, "duration_seconds", spec.duration_seconds)
    _identity_float(row, "warmup_seconds", spec.warmup_seconds)
    try:
        parameters = json.loads(row.get("algorithm_params", ""))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MatrixEvidenceError(
            "matrix row identity has invalid algorithm_params"
        ) from exc
    if parameters != dict(sorted(spec.algorithm_params.items())):
        raise MatrixEvidenceError(
            "matrix row identity differs for algorithm_params"
        )

    disturbance = spec.disturbance
    if disturbance is None:
        for name in (
            "disturbance_kind",
            "disturbance_begin_seconds",
            "disturbance_end_seconds",
            "disturbance_target",
            "disturbance_intensity",
        ):
            if str(row.get(name, "")) != "":
                raise MatrixEvidenceError(f"matrix row identity differs for {name}")
        return
    if str(row.get("disturbance_kind", "")) != disturbance.kind:
        raise MatrixEvidenceError(
            "matrix row identity differs for disturbance_kind"
        )
    if str(row.get("disturbance_target", "")) != disturbance.target:
        raise MatrixEvidenceError(
            "matrix row identity differs for disturbance_target"
        )
    _identity_float(
        row, "disturbance_begin_seconds", disturbance.begin_seconds
    )
    _identity_float(row, "disturbance_end_seconds", disturbance.end_seconds)
    _identity_float(row, "disturbance_intensity", disturbance.intensity)


def load_sealed_matrix_rows(
    matrix_csv: Path,
    specs: Sequence[RunSpec],
) -> list[dict[str, object]]:
    """Return canonical rows only after binding CSV, manifest, and sealed evidence."""
    matrix_csv = Path(matrix_csv)
    matrix_root = matrix_csv.parent.resolve()
    frozen_specs = tuple(specs)
    expected = {spec.run_key: spec for spec in frozen_specs}
    if len(expected) != len(frozen_specs):
        raise MatrixEvidenceError("frozen matrix contains duplicate run key")
    try:
        with matrix_csv.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
    except OSError as exc:
        raise MatrixEvidenceError(f"cannot read matrix CSV: {exc}") from exc
    actual_keys = [row.get("run_key", "") for row in rows]
    if len(set(actual_keys)) != len(actual_keys):
        raise MatrixEvidenceError("matrix contains duplicate run key")
    if len(rows) != len(frozen_specs) or set(actual_keys) != set(expected):
        raise MatrixEvidenceError(
            "matrix rows do not match the expected frozen run keys"
        )

    manifest_path = matrix_root / "matrix_manifest.json"
    try:
        manifest = _load_manifest(manifest_path, frozen_specs)
    except (MatrixIntegrityError, CorruptCompletedRunError) as exc:
        raise MatrixEvidenceError(str(exc)) from exc
    runs_root = (matrix_root / "runs").resolve()
    canonical_rows: list[dict[str, object]] = []
    for row in rows:
        spec = expected[str(row["run_key"])]
        _validate_result_identity(spec, row)
        chain = manifest["attempt_chains"][spec.run_key]
        if not chain or not isinstance(chain[-1], dict):
            raise MatrixEvidenceError("matrix manifest has no latest attempt")
        latest = chain[-1]
        if str(latest.get("status", "")) != RunStatus.COMPLETED.value:
            raise MatrixEvidenceError("matrix manifest latest attempt is not completed")
        if str(row.get("status", "")) != RunStatus.COMPLETED.value:
            raise MatrixEvidenceError("matrix CSV status is not completed")
        run_id = str(row.get("run_id", ""))
        if not run_id or run_id != str(latest.get("run_id", "")):
            raise MatrixEvidenceError("matrix row differs from manifest latest attempt")

        raw_run_dir = str(row.get("run_dir", ""))
        if not raw_run_dir:
            raise MatrixEvidenceError("matrix row has no run directory")
        candidate = Path(raw_run_dir)
        if not candidate.is_absolute():
            if ".." in candidate.parts:
                raise MatrixEvidenceError(
                    "matrix run directory is outside control via parent traversal"
                )
            candidate = matrix_root / candidate
        run_dir = candidate.resolve()
        try:
            run_dir.relative_to(runs_root)
        except ValueError as exc:
            raise MatrixEvidenceError(
                "matrix run directory is outside the controlled matrix root"
            ) from exc
        manifest_run_dir = Path(str(latest.get("run_dir", ""))).resolve()
        if run_dir != manifest_run_dir:
            raise MatrixEvidenceError("matrix row differs from manifest latest attempt")
        try:
            _validate_run_directory(spec, run_dir, run_id, runs_root)
        except MatrixIntegrityError as exc:
            raise MatrixEvidenceError(str(exc)) from exc
        if not run_dir.is_dir():
            raise MatrixEvidenceError("matrix run directory is missing")

        request = spec.to_request(runs_root)
        if not _strict_is_complete(run_dir, request):
            raise MatrixEvidenceError(
                "matrix run is not strict sealed evidence for exact request"
            )
        try:
            summary = EvidenceReader.load_summary(run_dir)
        except Exception as exc:
            raise MatrixEvidenceError(f"cannot load sealed summary: {exc}") from exc
        metrics = summary.get("metrics") if isinstance(summary, dict) else None
        if not isinstance(metrics, Mapping):
            raise MatrixEvidenceError("sealed summary has no canonical metrics")

        canonical = dict(row)
        canonical["run_dir"] = str(run_dir)
        for name in MATRIX_METRIC_COLUMNS:
            try:
                sealed_value = float(metrics[name])
                csv_value = float(row[name])
            except (KeyError, TypeError, ValueError) as exc:
                raise MatrixEvidenceError(
                    f"sealed summary has invalid metric {name}"
                ) from exc
            if not math.isfinite(sealed_value) or csv_value != sealed_value:
                raise MatrixEvidenceError(
                    f"matrix CSV {name} differs from sealed summary"
                )
            canonical[name] = sealed_value
        for name in MATRIX_SAFETY_COLUMNS:
            sealed_value = metrics.get(name)
            if (
                isinstance(sealed_value, bool)
                or not isinstance(sealed_value, int)
                or str(row.get(name, "")) != str(sealed_value)
            ):
                raise MatrixEvidenceError(
                    f"matrix CSV {name} differs from sealed summary"
                )
            canonical[name] = sealed_value
        canonical_rows.append(canonical)
    return canonical_rows


def _entry_from_attempt(run_key: str, attempt: dict[str, object]) -> MatrixEntry:
    parent = attempt.get("parent_failure")
    return MatrixEntry(
        run_key=run_key,
        run_id=str(attempt["run_id"]),
        status=str(attempt["status"]),
        reason=str(attempt.get("reason", "")),
        run_dir=Path(str(attempt["run_dir"])),
        parent_failure=dict(parent) if isinstance(parent, dict) else None,
    )


def _result_rows(
    specs: tuple[RunSpec, ...],
    entries: dict[str, MatrixEntry],
) -> list[dict[str, object]]:
    rows = []
    for spec in specs:
        entry = entries.get(spec.run_key)
        if entry is None:
            continue
        summary = (
            EvidenceReader.load_summary(entry.run_dir)
            if entry.status == RunStatus.COMPLETED.value
            else None
        )
        metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}
        disturbance = spec.disturbance
        rows.append(
            {
                "run_key": spec.run_key,
                "scene_id": spec.scene_id,
                "intersection_id": spec.scene_id,
                "algorithm": spec.algorithm,
                "flow_multiplier": spec.flow_multiplier,
                "seed": spec.seed,
                "matrix_kind": spec.matrix_kind,
                "disturbance_kind": disturbance.kind if disturbance else "",
                "disturbance_begin_seconds": (
                    disturbance.begin_seconds if disturbance else ""
                ),
                "disturbance_end_seconds": disturbance.end_seconds if disturbance else "",
                "disturbance_target": disturbance.target if disturbance else "",
                "disturbance_intensity": disturbance.intensity if disturbance else "",
                "duration_seconds": spec.duration_seconds,
                "warmup_seconds": spec.warmup_seconds,
                "steps": spec.steps if spec.steps is not None else "",
                "steps_origin": (
                    "explicit" if spec.steps is not None else "none"
                ),
                "algorithm_params": _canonical_json(spec.algorithm_params),
                "run_id": entry.run_id,
                "status": entry.status,
                "reason": entry.reason,
                "run_dir": str(entry.run_dir),
                **metrics,
            }
        )
    return rows


def _write_results(
    output_root: Path,
    specs: tuple[RunSpec, ...],
    entries: dict[str, MatrixEntry],
) -> None:
    rows = _result_rows(specs, entries)
    _atomic_json(output_root / "matrix_results.json", {"rows": rows})
    if not rows:
        return
    from io import StringIO

    buffer = StringIO(newline="")
    fieldnames: list[str] = []
    for row in rows:
        for column_name in row:
            if column_name not in fieldnames:
                fieldnames.append(column_name)
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    _atomic_bytes(output_root / "matrix.csv", buffer.getvalue().encode("utf-8"))


def run_matrix(
    matrix: Sequence[RunSpec],
    output_root: Path,
    resume: bool,
    *,
    run_service: RunService | None = None,
) -> MatrixReport:
    """Execute a frozen matrix while preserving strict completed evidence."""
    specs = tuple(matrix)
    keys = [spec.run_key for spec in specs]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate run key in matrix")
    if not specs:
        raise ValueError("matrix must contain at least one spec")

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "matrix_manifest.json"
    results_path = output_root / "matrix_results.json"
    with _matrix_lock(output_root):
        if manifest_path.exists():
            if not resume:
                raise MatrixIntegrityError(
                    "matrix manifest already exists; use resume to preserve prior runs"
                )
            manifest = _load_manifest(manifest_path, specs)
        else:
            manifest = _new_manifest(specs)
            _atomic_json(manifest_path, manifest)

        service = run_service
        owns_service = False
        entries: dict[str, MatrixEntry] = {}
        skipped = 0
        retried = 0
        try:
            for spec in specs:
                chain = manifest["attempt_chains"][spec.run_key]
                latest = chain[-1] if chain else None
                parent_failure = None
                if latest is not None:
                    manifest_status = str(latest.get("status", ""))
                    try:
                        _validate_run_directory(
                            spec,
                            Path(str(latest.get("run_dir", ""))),
                            str(latest.get("run_id", "")),
                            output_root / "runs",
                        )
                        disk_status = _status_for_attempt(spec, latest)
                    except MatrixIntegrityError as exc:
                        if manifest_status == RunStatus.COMPLETED.value:
                            raise CorruptCompletedRunError(
                                "completed run has corrupt disk state"
                            ) from exc
                        raise
                    if manifest_status == RunStatus.COMPLETED.value:
                        if (
                            disk_status is None
                            or str(disk_status.get("status", ""))
                            != RunStatus.COMPLETED.value
                        ):
                            raise CorruptCompletedRunError(
                                "completed run is missing completed disk status"
                            )
                        request = spec.to_request(output_root / "runs")
                        run_dir = Path(str(latest["run_dir"]))
                        if not _strict_is_complete(run_dir, request):
                            raise CorruptCompletedRunError(
                                "completed run is not strict evidence for exact request"
                            )
                        entry = _entry_from_attempt(spec.run_key, latest)
                        entries[spec.run_key] = entry
                        skipped += 1
                        continue
                    if disk_status is None:
                        raise MatrixIntegrityError(
                            "existing matrix attempt is missing canonical status"
                        )
                    status = str(disk_status.get("status", ""))
                    if status != manifest_status:
                        raise MatrixIntegrityError(
                            "matrix attempt manifest status differs from disk status"
                        )
                    retryable_statuses = {
                        RunStatus.FAILED.value,
                        RunStatus.INTERRUPTED.value,
                        RunStatus.STOPPED.value,
                        RunStatus.ENDED_EARLY.value,
                        RunStatus.DISCONNECTED.value,
                    }
                    if status not in retryable_statuses:
                        raise MatrixIntegrityError(
                            f"cannot resume non-terminal attempt {latest['run_id']}: {status}"
                        )
                    parent_failure = {
                        "run_id": str(latest["run_id"]),
                        "status": status,
                    }
                    retried += 1

                if service is None:
                    service = RunService(output_root=output_root / "runs")
                    owns_service = True
                request = spec.to_request(output_root / "runs")
                result = service.run_sync(request)
                prior_attempts = [
                    attempt
                    for attempt_chain in manifest["attempt_chains"].values()
                    for attempt in attempt_chain
                ]
                prior_run_ids = {
                    str(attempt.get("run_id", "")) for attempt in prior_attempts
                }
                prior_run_dirs = {
                    str(Path(str(attempt.get("run_dir", ""))).resolve())
                    for attempt in prior_attempts
                }
                if (
                    result.run_id in prior_run_ids
                    or str(Path(result.run_dir).resolve()) in prior_run_dirs
                ):
                    raise MatrixIntegrityError(
                        "retry must return a unique run id and run directory"
                    )
                _validate_run_directory(
                    spec,
                    result.run_dir,
                    result.run_id,
                    output_root / "runs",
                )
                if result.status is RunStatus.COMPLETED and not _strict_is_complete(
                    result.run_dir, request
                ):
                    raise CorruptCompletedRunError(
                        "live completed run is not strict evidence for exact request"
                    )
                status_payload = _status_for_attempt(
                    spec,
                    {"run_id": result.run_id, "run_dir": str(result.run_dir)},
                )
                if status_payload is None:
                    raise MatrixIntegrityError("run result has no canonical status artifact")
                disk_status = str(status_payload["status"])
                if disk_status != result.status.value:
                    raise MatrixIntegrityError("run result status differs from disk status")
                terminal_statuses = {
                    RunStatus.COMPLETED.value,
                    RunStatus.FAILED.value,
                    RunStatus.INTERRUPTED.value,
                    RunStatus.STOPPED.value,
                    RunStatus.ENDED_EARLY.value,
                    RunStatus.DISCONNECTED.value,
                }
                if disk_status not in terminal_statuses:
                    raise MatrixIntegrityError(
                        "run result must have a terminal status"
                    )
                attempt = {
                    "run_id": result.run_id,
                    "run_dir": str(Path(result.run_dir).resolve()),
                    "status": disk_status,
                    "reason": str(status_payload.get("reason", result.reason)),
                    "parent_failure": parent_failure,
                }
                chain.append(attempt)
                _atomic_json(manifest_path, manifest)
                entry = _entry_from_attempt(spec.run_key, attempt)
                entries[spec.run_key] = entry
                _write_results(output_root, specs, entries)
            _write_results(output_root, specs, entries)
            return MatrixReport(
                entries=tuple(entries[key] for key in keys if key in entries),
                manifest_path=manifest_path,
                results_path=results_path,
                expected_keys=tuple(keys),
                skipped=skipped,
                retried=retried,
            )
        finally:
            if owns_service and service is not None:
                service.shutdown()
