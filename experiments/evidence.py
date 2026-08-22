"""Versioned, run-scoped evidence contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import csv
import hashlib
import json
from pathlib import Path
from collections.abc import Mapping
from pathlib import PurePosixPath
import math
import re
import stat
import platform
import subprocess
import threading
from uuid import uuid4

from core.run_models import RunStatus
from core.types import MetricSummary, SafetyEvent
from engine.artifacts import RunArtifacts


MANIFEST_SCHEMA = "challenge-cup.run-manifest"
PROVENANCE_SCHEMA = "challenge-cup.run-provenance"
HASHES_SCHEMA = "challenge-cup.run-hashes"
SCHEMA_VERSION = 1
_TERMINAL = frozenset({
    "completed",
    "ended_early",
    "disconnected",
    "interrupted",
    "failed",
})
_PUBLISHABLE = frozenset({"completed", "ended_early"})
_PARTIAL_REQUIRED = (
    "manifest.json",
    "provenance.json",
    "status.json",
    "run_metadata.json",
)
_EVIDENCE_LOCK = threading.RLock()
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _atomic_bytes(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    _atomic_bytes(
        path,
        (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8"),
    )


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_sha256_file(path: Path) -> str:
    before = path.stat()
    digest = _sha256_file(path)
    after = path.stat()
    identity_before = (before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after:
        raise OSError(f"evidence file changed while hashing: {path.name}")
    return digest


def _json_non_finite_paths(value: object, prefix: str = "$") -> list[str]:
    """Return JSON paths containing Python's non-standard NaN/Infinity values."""
    if type(value) is float and not math.isfinite(value):
        return [prefix]
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, nested in value.items():
            paths.extend(_json_non_finite_paths(nested, f"{prefix}.{key}"))
        return paths
    if isinstance(value, list):
        paths = []
        for index, nested in enumerate(value):
            paths.extend(_json_non_finite_paths(nested, f"{prefix}[{index}]"))
        return paths
    return []


def _is_finite_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value))


def _is_link_or_junction(path: Path) -> bool:
    """Reject links and every Windows reparse point on all supported Pythons."""
    try:
        details = path.lstat()
    except FileNotFoundError:
        # Missing optional partial-evidence outputs are handled by their
        # callers; they are not links.  Preserve other I/O failures so the
        # reader can surface them as evidence issues.
        return False
    if stat.S_ISLNK(details.st_mode):
        return True
    # pathlib.Path.is_junction() is only present in Python 3.12+.  The
    # Windows file attribute is available from lstat on every supported
    # interpreter and identifies junctions and every other reparse point.
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
    return bool(getattr(details, "st_file_attributes", 0) & reparse_flag)


def _json_exact_equal(left: object, right: object) -> bool:
    """Compare decoded JSON without treating booleans as integers."""
    if type(left) is not type(right):
        return False
    if isinstance(left, Mapping):
        return set(left) == set(right) and all(
            _json_exact_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_exact_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    code_commit: str
    scene_manifest_sha256: str
    algorithm: str
    parameters: Mapping[str, object]
    flow_multiplier: float
    seed: int
    duration_seconds: float
    warmup_seconds: float
    derived_steps: int | None
    sumo_version: str
    python_version: str
    prediction_enabled: bool
    scene_id: str = ""
    scene_source_sha256: Mapping[str, str] = field(default_factory=dict)
    step_length: float | None = None
    requested_seconds: float = 0.0
    request_dimensions: Mapping[str, object] = field(default_factory=dict)

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["parameters"] = dict(self.parameters)
        payload["scene_source_sha256"] = dict(self.scene_source_sha256)
        payload["request_dimensions"] = dict(self.request_dimensions)
        payload.update({
            "schema": MANIFEST_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "intersection_id": self.scene_id,
        })
        return payload


@dataclass(frozen=True)
class EvidenceIssue:
    code: str
    detail: str
    path: str | None = None


def canonical_mapping_sha256(values: Mapping[str, str]) -> str:
    encoded = json.dumps(
        dict(values),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_code_commit(repo_root: Path | None = None) -> str:
    """Resolve the checked-out commit, returning explicit unknown on failure."""
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        commit = completed.stdout.strip().lower()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return commit if _COMMIT_PATTERN.fullmatch(commit) else "unknown"


def runtime_python_version() -> str:
    return platform.python_version()


class EvidenceWriter:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self._events: list[SafetyEvent] = []
        self._warmup_seconds = 0.0
        self._materialized_status: str | None = None
        manifest_path = self.run_dir / "manifest.json"
        if manifest_path.exists():
            try:
                self._warmup_seconds = float(
                    _load_json(manifest_path).get("warmup_seconds", 0.0)
                )
            except (OSError, TypeError, ValueError):
                self._warmup_seconds = 0.0

    def begin(self, manifest: RunManifest) -> None:
        with _EVIDENCE_LOCK:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            if (self.run_dir / "hashes.json").exists():
                raise ValueError("sealed evidence cannot be begun again")
            manifest_path = self.run_dir / "manifest.json"
            existing = _load_json(manifest_path) if manifest_path.exists() else {}
            incoming = manifest.to_payload()
            identity_pairs = (
                ("run_id", "run_id"),
                ("algorithm", "algorithm"),
                ("intersection_id", "intersection_id"),
                ("flow_multiplier", "flow_multiplier"),
                ("seed", "seed"),
            )
            for existing_name, incoming_name in identity_pairs:
                if (
                    existing_name in existing
                    and existing[existing_name] != incoming[incoming_name]
                ):
                    raise ValueError(
                        f"existing manifest identity conflict for {existing_name}"
                    )
            merged = {**existing, **incoming}
            _atomic_json(manifest_path, merged)
            _atomic_json(
                self.run_dir / "provenance.json",
                {
                    "schema": PROVENANCE_SCHEMA,
                    "schema_version": SCHEMA_VERSION,
                    "run_id": manifest.run_id,
                    "code_commit": manifest.code_commit,
                    "scene_manifest_sha256": manifest.scene_manifest_sha256,
                    "scene_source_sha256": dict(manifest.scene_source_sha256),
                    "sumo_version": manifest.sumo_version,
                    "python_version": manifest.python_version,
                },
            )
            self._warmup_seconds = float(manifest.warmup_seconds)

    def record_event(self, event: SafetyEvent) -> None:
        manifest = _load_json(self.run_dir / "manifest.json")
        if event.run_id != manifest.get("run_id"):
            raise ValueError("safety event run_id does not match evidence run_id")
        self._events.append(event)

    def update_runtime(
        self,
        *,
        parameters: Mapping[str, object],
        prediction_enabled: bool,
    ) -> None:
        """Record the actual initialized algorithm contract before materialization."""
        with _EVIDENCE_LOCK:
            if (self.run_dir / "hashes.json").exists():
                raise ValueError("sealed evidence cannot be updated")
            manifest_path = self.run_dir / "manifest.json"
            manifest = _load_json(manifest_path)
            manifest["parameters"] = dict(parameters)
            manifest["prediction_enabled"] = bool(prediction_enabled)
            _atomic_json(manifest_path, manifest)

    def record_error(self, detail: str) -> None:
        """Record an unsealed evidence commit failure without rewriting status."""
        with _EVIDENCE_LOCK:
            if (self.run_dir / "hashes.json").exists():
                raise ValueError("sealed evidence cannot record a late error")
            manifest_path = self.run_dir / "manifest.json"
            manifest = _load_json(manifest_path)
            manifest["evidence_error"] = str(detail)
            _atomic_json(manifest_path, manifest)

    def finalize(
        self,
        status: RunStatus,
        summary: MetricSummary | None,
    ) -> None:
        if (self.run_dir / "hashes.json").exists():
            raise ValueError("sealed evidence cannot be materialized again")
        value = status.value if isinstance(status, RunStatus) else str(status)
        if value not in _TERMINAL:
            raise ValueError(f"evidence status must be terminal: {value}")
        if value in _PUBLISHABLE and summary is None:
            raise ValueError("publishable evidence requires MetricSummary")
        if value not in _PUBLISHABLE and summary is not None:
            raise ValueError("non-publishable evidence cannot contain a completed summary")

        if self._events:
            self._write_buffered_events()
        for name in ("metrics.csv", "simulation_log.csv", "events.csv"):
            path = self.run_dir / name
            if path.exists():
                _atomic_bytes(path, path.read_bytes())
        manifest_path = self.run_dir / "manifest.json"
        manifest = _load_json(manifest_path)
        manifest["end_status"] = value
        _atomic_json(manifest_path, manifest)
        if summary is not None:
            from experiments.summary import metric_summary_payload

            _atomic_json(
                self.run_dir / "summary.json",
                metric_summary_payload(
                    str(manifest["run_id"]),
                    summary,
                    self._warmup_seconds,
                ),
            )
        else:
            (self.run_dir / "summary.json").unlink(missing_ok=True)
        self._materialized_status = value

    def seal(self) -> None:
        """Commit hashes only after Task 12 status and metadata are terminal."""
        with _EVIDENCE_LOCK:
            for candidate in (self.run_dir, *self.run_dir.parents):
                if _is_link_or_junction(candidate):
                    raise ValueError(
                        f"terminal evidence path crosses a reparse point: {candidate}"
                    )
            hashes_path = self.run_dir / "hashes.json"
            if hashes_path.exists():
                issues = EvidenceReader.validate(self.run_dir)
                if issues:
                    raise ValueError("sealed evidence is invalid and cannot be resealed")
                return
            manifest_path = self.run_dir / "manifest.json"
            provenance_path = self.run_dir / "provenance.json"
            status = _load_json(self.run_dir / "status.json")
            metadata = _load_json(self.run_dir / "run_metadata.json")
            value = status.get("status")
            if value not in _TERMINAL or metadata.get("status") != value:
                raise ValueError("status and run_metadata must agree on a terminal state")
            manifest = _load_json(manifest_path)
            if str(manifest.get("evidence_error", "")).strip():
                raise ValueError("manifest records an evidence error and cannot be sealed")
            run_id = manifest.get("run_id")
            if status.get("run_id") != run_id or metadata.get("run_id") != run_id:
                raise ValueError("terminal artifacts have mismatched run_id")
            if self._materialized_status not in (None, value):
                raise ValueError("materialized evidence status does not match terminal status")

            manifest.update({
                "end_status": value,
                "failure_reason": status.get("reason", ""),
                "final_seconds": metadata.get("final_simulation_time"),
                "sumo_version": metadata.get("sumo_version", manifest.get("sumo_version")),
            })
            _atomic_json(manifest_path, manifest)
            provenance = _load_json(provenance_path)
            provenance["sumo_version"] = manifest.get("sumo_version", "unknown")
            _atomic_json(provenance_path, provenance)

            required = (
                RunArtifacts.evidence_required_output_names()[:-1]
                if value in _PUBLISHABLE
                else _PARTIAL_REQUIRED
            )
            if value not in _PUBLISHABLE and (self.run_dir / "summary.json").exists():
                raise ValueError("non-publishable evidence cannot contain summary.json")
            for name in required:
                path = self.run_dir / name
                if _is_link_or_junction(path):
                    raise ValueError(f"terminal evidence cannot use symlink {name}")
                if not path.is_file() or path.stat().st_size <= 0:
                    raise ValueError(f"terminal evidence missing non-empty {name}")

            candidates = RunArtifacts.evidence_required_output_names()[:-1]
            files: dict[str, str] = {}
            for name in candidates:
                path = self.run_dir / name
                if _is_link_or_junction(path):
                    raise ValueError(f"terminal evidence cannot hash symlink {name}")
                if path.is_file() and path.stat().st_size > 0:
                    files[name] = _stable_sha256_file(path)
            _atomic_json(
                hashes_path,
                {
                    "schema": HASHES_SCHEMA,
                    "schema_version": SCHEMA_VERSION,
                    "run_id": run_id,
                    "algorithm": "sha256",
                    "files": files,
                },
            )

    def _write_buffered_events(self) -> None:
        path = self.run_dir / "events.csv"
        existing: list[dict[str, str]] = []
        from engine.events import EVENT_FIELDS

        fieldnames = list(EVENT_FIELDS)
        manifest = _load_json(self.run_dir / "manifest.json")
        if path.exists() and path.stat().st_size > 0:
            with path.open(newline="", encoding="utf-8") as source:
                reader = csv.DictReader(source)
                existing = list(reader)
                if reader.fieldnames:
                    fieldnames = list(reader.fieldnames)
        rows = list(existing)
        for event in self._events:
            row = {name: "" for name in fieldnames}
            row.update({
                "run_id": event.run_id,
                "intersection_id": str(manifest.get("scene_id", "")),
                "algorithm": str(manifest.get("algorithm", "")),
                "step": str(event.step),
                "simulation_seconds": str(event.simulation_seconds),
                "type": event.event_type,
                "detail": event.detail,
                "entity_ids": json.dumps(event.entity_ids, ensure_ascii=False),
                "source": event.source,
                "confidence": str(event.confidence),
            })
            rows.append(row)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        self._events.clear()


class EvidenceReader:
    @staticmethod
    def validate(run_dir: Path) -> list[EvidenceIssue]:
        run_dir = Path(run_dir)
        issues: list[EvidenceIssue] = []

        def issue(code: str, detail: str, path: str | None = None) -> None:
            issues.append(EvidenceIssue(code, detail, path))

        def unsafe_link(path: Path, label: str | None = None) -> bool:
            try:
                linked = _is_link_or_junction(path)
            except OSError as exc:
                issue("evidence_io", str(exc), label or str(path))
                return True
            if linked:
                issue(
                    "symlink_output",
                    f"contract path is a symlink or junction: {path}",
                    label,
                )
            return linked

        try:
            for candidate in (run_dir, *run_dir.parents):
                if _is_link_or_junction(candidate):
                    return [EvidenceIssue(
                        "reparse_point",
                        f"run directory ancestry crosses a reparse point: {candidate}",
                    )]
            is_directory = run_dir.is_dir()
        except OSError as exc:
            return [EvidenceIssue("evidence_io", str(exc), str(run_dir))]
        if not is_directory:
            return [EvidenceIssue("missing_run_dir", "run directory does not exist")]
        try:
            temporary_paths = (
                sorted(run_dir.glob("*.tmp"))
                + sorted(run_dir.glob(".*.tmp"))
            )
        except OSError as exc:
            issue("evidence_io", str(exc), str(run_dir))
            temporary_paths = []
        for temporary in temporary_paths:
            issue("temporary_file", "atomic temporary file remains", temporary.name)

        payloads: dict[str, dict[str, object]] = {}
        for name in (*_PARTIAL_REQUIRED, "hashes.json"):
            path = run_dir / name
            if unsafe_link(path, name):
                continue
            try:
                present = path.is_file() and path.stat().st_size > 0
            except OSError as exc:
                issue("evidence_io", str(exc), name)
                continue
            if not present:
                issue("missing_file", f"missing non-empty {name}", name)
                continue
            try:
                payloads[name] = _load_json(path)
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                issue("invalid_json", str(exc), name)

        if any(name not in payloads for name in (*_PARTIAL_REQUIRED, "hashes.json")):
            return issues

        manifest = payloads["manifest.json"]
        provenance = payloads["provenance.json"]
        status = payloads["status.json"]
        metadata = payloads["run_metadata.json"]
        hashes = payloads["hashes.json"]
        for name, payload in payloads.items():
            non_finite = _json_non_finite_paths(payload)
            if non_finite:
                issue(
                    "non_finite_json",
                    f"non-finite JSON numbers at {non_finite}",
                    name,
                )
        schemas = (
            (manifest, MANIFEST_SCHEMA, "manifest.json"),
            (provenance, PROVENANCE_SCHEMA, "provenance.json"),
            (hashes, HASHES_SCHEMA, "hashes.json"),
        )
        for payload, expected, name in schemas:
            if (
                payload.get("schema") != expected
                or type(payload.get("schema_version")) is not int
                or payload.get("schema_version") != 1
            ):
                issue("schema_mismatch", f"invalid schema/version for {name}", name)

        run_id = manifest.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            issue("required_field", "manifest run_id is required", "manifest.json")
        for name, payload in (
            ("provenance.json", provenance),
            ("status.json", status),
            ("run_metadata.json", metadata),
            ("hashes.json", hashes),
        ):
            if payload.get("run_id") != run_id:
                issue("run_id_mismatch", f"{name} run_id does not match", name)
        if run_id != run_dir.name:
            issue("run_id_mismatch", "manifest run_id does not match directory", "manifest.json")

        value = status.get("status")
        if value not in _TERMINAL:
            issue("non_terminal_status", "status is not terminal", "status.json")
        if metadata.get("status") != value or manifest.get("end_status") != value:
            issue("status_mismatch", "terminal status fields do not agree")
        if value not in _PUBLISHABLE and not str(status.get("reason", "")).strip():
            issue("failure_reason", "non-publishable terminal status requires a reason")
        if metadata.get("reason") != status.get("reason"):
            issue("failure_reason", "status and metadata failure reasons differ")
        if manifest.get("failure_reason") != status.get("reason"):
            issue(
                "failure_reason",
                "manifest and status failure reasons differ",
                "manifest.json",
            )

        manifest_required = {
            "run_id",
            "code_commit",
            "scene_manifest_sha256",
            "algorithm",
            "parameters",
            "flow_multiplier",
            "seed",
            "duration_seconds",
            "warmup_seconds",
            "derived_steps",
            "sumo_version",
            "python_version",
            "prediction_enabled",
            "scene_id",
            "scene_source_sha256",
            "step_length",
            "requested_seconds",
            "end_status",
            "failure_reason",
            "final_seconds",
        }
        missing_fields = sorted(manifest_required - set(manifest))
        if missing_fields:
            issue("required_field", f"manifest missing fields: {missing_fields}", "manifest.json")
        if str(manifest.get("evidence_error", "")).strip():
            issue(
                "evidence_commit_error",
                "manifest records an evidence commit error",
                "manifest.json",
            )
        provenance_required = {
            "run_id",
            "code_commit",
            "scene_manifest_sha256",
            "scene_source_sha256",
            "sumo_version",
            "python_version",
        }
        missing_provenance = sorted(provenance_required - set(provenance))
        if missing_provenance:
            issue(
                "required_field",
                f"provenance missing fields: {missing_provenance}",
                "provenance.json",
            )

        if type(manifest.get("prediction_enabled")) is not bool:
            issue(
                "manifest_type",
                "prediction_enabled must be a JSON boolean",
                "manifest.json",
            )
        if type(manifest.get("seed")) is not int:
            issue("manifest_type", "seed must be an integer", "manifest.json")
        elif manifest["seed"] < 0:
            issue("manifest_type", "seed must be non-negative", "manifest.json")
        for field_name in (
            "algorithm",
            "scene_id",
            "intersection_id",
            "sumo_version",
            "python_version",
        ):
            field_value = manifest.get(field_name)
            if not isinstance(field_value, str) or not field_value.strip():
                issue(
                    "manifest_type",
                    f"{field_name} must be a non-empty string",
                    "manifest.json",
                )
        if (
            isinstance(manifest.get("scene_id"), str)
            and manifest.get("intersection_id") != manifest.get("scene_id")
        ):
            issue(
                "manifest_type",
                "intersection_id must equal scene_id",
                "manifest.json",
            )
        derived_steps = manifest.get("derived_steps")
        if derived_steps is not None and (
            type(derived_steps) is not int or derived_steps <= 0
        ):
            issue(
                "manifest_type",
                "derived_steps must be null or an integer > 0",
                "manifest.json",
            )
        numeric_manifest_fields = (
            "flow_multiplier",
            "duration_seconds",
            "warmup_seconds",
            "requested_seconds",
        )
        for field_name in numeric_manifest_fields:
            field_value = manifest.get(field_name)
            if not _is_finite_number(field_value):
                issue(
                    "manifest_type",
                    f"{field_name} must be a finite JSON number",
                    "manifest.json",
                )
            elif (
                field_name == "warmup_seconds" and float(field_value) < 0
            ) or (
                field_name != "warmup_seconds" and float(field_value) <= 0
            ):
                issue(
                    "manifest_type",
                    f"{field_name} is outside its valid range",
                    "manifest.json",
                )
        for field_name in ("step_length", "final_seconds"):
            field_value = manifest.get(field_name)
            if field_value is not None and not _is_finite_number(field_value):
                issue(
                    "manifest_type",
                    f"{field_name} must be null or a finite JSON number",
                    "manifest.json",
                )
            elif field_value is not None and (
                (field_name == "step_length" and float(field_value) <= 0)
                or (field_name == "final_seconds" and float(field_value) < 0)
            ):
                issue(
                    "manifest_type",
                    f"{field_name} is outside its valid range",
                    "manifest.json",
                )
        if not isinstance(manifest.get("parameters"), Mapping):
            issue("manifest_type", "parameters must be a mapping", "manifest.json")
        if not isinstance(manifest.get("request_dimensions", {}), Mapping):
            issue(
                "manifest_type",
                "request_dimensions must be a mapping",
                "manifest.json",
            )

        for field_name in ("algorithm", "intersection_id", "sumo_version"):
            field_value = metadata.get(field_name)
            if not isinstance(field_value, str) or not field_value.strip():
                issue(
                    "metadata_type",
                    f"{field_name} must be a non-empty string",
                    "run_metadata.json",
                )
        if type(metadata.get("seed")) is not int or metadata.get("seed", -1) < 0:
            issue(
                "metadata_type",
                "seed must be a non-negative integer",
                "run_metadata.json",
            )
        flow_multiplier = metadata.get("flow_multiplier")
        if not _is_finite_number(flow_multiplier) or float(flow_multiplier) <= 0:
            issue(
                "metadata_type",
                "flow_multiplier must be finite and > 0",
                "run_metadata.json",
            )
        for field_name in (
            "requested_seconds",
            "warmup_seconds",
            "final_simulation_time",
            "step_length",
        ):
            field_value = metadata.get(field_name)
            if field_value is not None and not _is_finite_number(field_value):
                issue(
                    "metadata_type",
                    f"{field_name} must be null or a finite JSON number",
                    "run_metadata.json",
                )
            elif field_value is not None and (
                (field_name in ("requested_seconds", "step_length") and float(field_value) <= 0)
                or (
                    field_name in ("warmup_seconds", "final_simulation_time")
                    and float(field_value) < 0
                )
            ):
                issue(
                    "metadata_type",
                    f"{field_name} is outside its valid range",
                    "run_metadata.json",
                )
        requested_steps = metadata.get("requested_steps")
        if requested_steps is not None and (
            type(requested_steps) is not int or requested_steps <= 0
        ):
            issue(
                "metadata_type",
                "requested_steps must be null or an integer > 0",
                "run_metadata.json",
            )

        if value in _PUBLISHABLE:
            code_commit = manifest.get("code_commit")
            if not isinstance(code_commit, str) or not _COMMIT_PATTERN.fullmatch(
                code_commit
            ):
                issue(
                    "commit_format",
                    "completed evidence code_commit must be 40 lowercase hex characters",
                    "manifest.json",
                )
            source_hashes = manifest.get("scene_source_sha256")
            if not isinstance(source_hashes, Mapping) or not source_hashes:
                issue(
                    "digest_format",
                    "completed evidence scene_source_sha256 must be a non-empty mapping",
                    "manifest.json",
                )
            else:
                for source_name, digest in source_hashes.items():
                    if (
                        not isinstance(source_name, str)
                        or not source_name
                        or not isinstance(digest, str)
                        or not _SHA256_PATTERN.fullmatch(digest)
                    ):
                        issue(
                            "digest_format",
                            f"invalid scene source SHA-256 for {source_name!r}",
                            "manifest.json",
                        )
            scene_digest = manifest.get("scene_manifest_sha256")
            if not isinstance(scene_digest, str) or not _SHA256_PATTERN.fullmatch(
                scene_digest
            ):
                issue(
                    "digest_format",
                    "scene_manifest_sha256 must be 64 lowercase hex characters",
                    "manifest.json",
                )
            for field in (
                "code_commit",
                "scene_manifest_sha256",
                "sumo_version",
                "python_version",
            ):
                if manifest.get(field) in (None, "", "unknown"):
                    issue("unknown_provenance", f"completed evidence has unknown {field}")
            for name in RunArtifacts.evidence_required_output_names():
                path = run_dir / name
                if unsafe_link(path, name):
                    continue
                try:
                    present = path.is_file() and path.stat().st_size > 0
                except OSError as exc:
                    issue("evidence_io", str(exc), name)
                    continue
                if not present:
                    issue("missing_file", f"missing non-empty {name}", name)

            from defusedxml import ElementTree as ET

            for name in (
                "tripinfo.xml",
                "stats.xml",
                "traj.xml",
                "collisions.xml",
            ):
                path = run_dir / name
                if unsafe_link(path, name) or not path.is_file():
                    continue
                try:
                    ET.parse(path)
                except Exception as exc:
                    issue("xml_invalid", str(exc), name)

            def validate_timeseries_csv(
                name: str,
                required_fields: tuple[str, ...],
                numeric_fields: tuple[str, ...],
            ) -> None:
                path = run_dir / name
                if unsafe_link(path, name) or not path.is_file():
                    return
                try:
                    with path.open(newline="", encoding="utf-8") as source:
                        reader = csv.DictReader(source)
                        fieldnames = set(reader.fieldnames or ())
                        if not set(required_fields) <= fieldnames:
                            issue(
                                "csv_schema",
                                f"{name} header lacks required fields",
                                name,
                            )
                            return
                        row_count = 0
                        for row in reader:
                            row_count += 1
                            step_raw = row.get("step", "")
                            if not re.fullmatch(r"\d+", step_raw or ""):
                                issue(
                                    "csv_schema",
                                    f"{name} step must be a non-negative integer",
                                    name,
                                )
                            for field_name in ("timestamp", *numeric_fields):
                                raw = row.get(field_name, "")
                                try:
                                    numeric = float(raw)
                                    if not math.isfinite(numeric) or numeric < 0:
                                        raise ValueError
                                except (TypeError, ValueError):
                                    issue(
                                        "csv_schema",
                                        f"{name} {field_name} must be finite and non-negative",
                                        name,
                                    )
                            if "current_phase" in required_fields and not re.fullmatch(
                                r"\d+", row.get("current_phase", "") or ""
                            ):
                                issue(
                                    "csv_schema",
                                    f"{name} current_phase must be a non-negative integer",
                                    name,
                                )
                        if row_count == 0:
                            issue(
                                "csv_schema",
                                f"{name} must contain at least one data row",
                                name,
                            )
                except Exception as exc:
                    issue("csv_schema", str(exc), name)

            validate_timeseries_csv(
                "metrics.csv",
                (
                    "step",
                    "timestamp",
                    "avg_queue_length",
                    "max_queue_length",
                ),
                ("avg_queue_length", "max_queue_length"),
            )
            validate_timeseries_csv(
                "simulation_log.csv",
                ("step", "timestamp", "current_phase"),
                (),
            )

            summary_path = run_dir / "summary.json"
            summary: dict[str, object] | None = None
            try:
                summary_present = (
                    not unsafe_link(summary_path, "summary.json")
                    and summary_path.is_file()
                    and summary_path.stat().st_size > 0
                )
            except OSError as exc:
                issue("evidence_io", str(exc), "summary.json")
                summary_present = False
            if summary_present:
                try:
                    summary = _load_json(summary_path)
                    non_finite = _json_non_finite_paths(summary)
                    if non_finite:
                        issue(
                            "non_finite_json",
                            f"non-finite JSON numbers at {non_finite}",
                            "summary.json",
                        )
                    metrics = summary.get("metrics", {})
                    units = summary.get("units", {})
                    required_metrics = {
                        "completed_vehicle_count",
                        "unfinished_vehicle_count",
                        "throughput",
                        "avg_travel_time_seconds",
                        "avg_delay_seconds",
                        "fuel_ml",
                        "co2_g",
                        *(f"{name}_count" for name in (
                            "collision",
                            "red_light",
                            "illegal_transition",
                            "harsh_braking",
                            "teleport",
                            "potential_conflict",
                        )),
                    }
                    if not isinstance(metrics, Mapping) or required_metrics - set(metrics):
                        issue("summary_schema", "summary lacks canonical metrics", "summary.json")
                    if not isinstance(units, Mapping) or units.get("fuel_ml") != "ml" or units.get("co2_g") != "g":
                        issue("summary_schema", "summary lacks explicit metric units", "summary.json")
                    if summary.get("run_id") != run_id:
                        issue("run_id_mismatch", "summary run_id does not match", "summary.json")
                    if summary.get("warmup_seconds") != manifest.get("warmup_seconds"):
                        issue("summary_schema", "summary warmup does not match manifest", "summary.json")
                except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    issue("invalid_json", str(exc), "summary.json")
            try:
                derived_summary = MetricSummary.from_raw_outputs(
                    run_dir,
                    float(manifest.get("warmup_seconds")),
                )
                if summary is not None:
                    from experiments.summary import metric_summary_payload

                    expected_summary = metric_summary_payload(
                        str(run_id),
                        derived_summary,
                        float(manifest.get("warmup_seconds")),
                    )
                    for section in (
                        "schema",
                        "schema_version",
                        "run_id",
                        "warmup_seconds",
                        "metrics",
                        "units",
                        "sources",
                    ):
                        if not _json_exact_equal(
                            summary.get(section),
                            expected_summary.get(section),
                        ):
                            issue(
                                "summary_mismatch",
                                f"summary {section} does not match raw outputs",
                                "summary.json",
                            )
                            break
            except Exception as exc:
                issue("raw_output_invalid", str(exc))
        elif (run_dir / "summary.json").exists():
            issue(
                "unexpected_summary",
                "non-publishable evidence must not contain summary.json",
                "summary.json",
            )

        consistency_fields = (
            "code_commit",
            "scene_manifest_sha256",
            "scene_source_sha256",
            "sumo_version",
            "python_version",
        )
        for field_name in consistency_fields:
            if provenance.get(field_name) != manifest.get(field_name):
                issue(
                    "provenance_mismatch",
                    f"manifest and provenance differ for {field_name}",
                    "provenance.json",
                )
        metadata_identity = (
            ("algorithm", "algorithm"),
            ("intersection_id", "scene_id"),
            ("flow_multiplier", "flow_multiplier"),
            ("seed", "seed"),
            ("sumo_version", "sumo_version"),
            ("requested_steps", "derived_steps"),
            ("requested_seconds", "requested_seconds"),
            ("warmup_seconds", "warmup_seconds"),
            ("step_length", "step_length"),
            ("final_simulation_time", "final_seconds"),
        )
        for metadata_field, manifest_field in metadata_identity:
            if (
                value not in _PUBLISHABLE
                and (
                    manifest.get(manifest_field) is None
                    or metadata.get(metadata_field) is None
                )
            ):
                continue
            if not _json_exact_equal(
                metadata.get(metadata_field),
                manifest.get(manifest_field),
            ):
                issue(
                    "metadata_mismatch",
                    f"metadata {metadata_field} does not match manifest {manifest_field}",
                    "run_metadata.json",
                )
        if metadata.get("reason") != status.get("reason"):
            issue(
                "metadata_mismatch",
                "status and metadata reasons differ",
                "run_metadata.json",
            )
        source_hashes = manifest.get("scene_source_sha256")
        if isinstance(source_hashes, Mapping):
            canonical_matches: bool | None = None
            try:
                canonical_source_hash = canonical_mapping_sha256(source_hashes)
            except (TypeError, ValueError) as exc:
                issue(
                    "digest_format",
                    f"scene source mapping is not canonical JSON: {exc}",
                    "manifest.json",
                )
            else:
                canonical_matches = manifest.get("scene_manifest_sha256") in (
                    "unknown",
                    canonical_source_hash,
                )
            if canonical_matches is False:
                issue(
                    "provenance_mismatch",
                    "scene manifest hash does not cover source hash mapping",
                    "manifest.json",
                )

        events_path = run_dir / "events.csv"
        try:
            events_present = (
                not unsafe_link(events_path, "events.csv")
                and events_path.is_file()
                and events_path.stat().st_size > 0
            )
        except OSError as exc:
            issue("evidence_io", str(exc), "events.csv")
            events_present = False
        if events_present:
            from engine.events import EVENT_FIELDS

            try:
                with events_path.open(newline="", encoding="utf-8") as source:
                    reader = csv.DictReader(source)
                    if tuple(reader.fieldnames or ()) != EVENT_FIELDS:
                        issue(
                            "events_schema",
                            "events.csv header does not match the canonical schema",
                            "events.csv",
                        )
                    for row in reader:
                        if (
                            set(row) != set(EVENT_FIELDS)
                            or any(not isinstance(row.get(field), str) for field in EVENT_FIELDS)
                        ):
                            issue(
                                "events_schema",
                                "events.csv contains a malformed row",
                                "events.csv",
                            )
                            continue
                        event_type = row.get("type")
                        if row.get("run_id") != run_id:
                            issue(
                                "event_run_id_mismatch",
                                "event run_id does not match evidence",
                                "events.csv",
                            )
                        if not re.fullmatch(r"\d+", row.get("step", "") or ""):
                            issue(
                                "events_schema",
                                "event step must be a non-negative integer",
                                "events.csv",
                            )
                        if not event_type:
                            issue(
                                "events_schema",
                                "event type is required",
                                "events.csv",
                            )
                        accepted = row.get("accepted", "")
                        if accepted not in ("", "true", "false"):
                            issue(
                                "events_schema",
                                "event accepted must be true, false, or empty",
                                "events.csv",
                            )
                        action_value = row.get("action_value", "")
                        if action_value:
                            try:
                                decoded_action = json.loads(action_value)
                                if _json_non_finite_paths(decoded_action):
                                    raise ValueError("action_value contains non-finite JSON")
                            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                                issue("events_schema", str(exc), "events.csv")
                        entity_ids = row.get("entity_ids", "")
                        decoded_entities: object | None = None
                        if entity_ids:
                            try:
                                decoded_entities = json.loads(entity_ids)
                                if (
                                    not isinstance(decoded_entities, list)
                                    or any(
                                        not isinstance(entity_id, str)
                                        for entity_id in decoded_entities
                                    )
                                ):
                                    raise ValueError(
                                        "entity_ids must be a JSON array of strings"
                                    )
                            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                                issue("events_schema", str(exc), "events.csv")
                        confidence_raw = row.get("confidence", "")
                        if confidence_raw:
                            try:
                                confidence = float(confidence_raw)
                                if (
                                    not math.isfinite(confidence)
                                    or not 0.0 <= confidence <= 1.0
                                ):
                                    raise ValueError
                            except (TypeError, ValueError):
                                issue(
                                    "events_schema",
                                    "event confidence must be finite and within [0, 1]",
                                    "events.csv",
                                )
                        event_time_raw = row.get("simulation_seconds", "")
                        if event_time_raw not in (None, ""):
                            try:
                                event_time = float(event_time_raw)
                                if not math.isfinite(event_time) or event_time < 0:
                                    raise ValueError
                            except (TypeError, ValueError):
                                issue(
                                    "events_schema",
                                    "event simulation_seconds is invalid",
                                    "events.csv",
                                )
                        if event_type not in {
                            "collision",
                            "red_light",
                            "illegal_transition",
                            "harsh_braking",
                            "teleport",
                            "potential_conflict",
                        }:
                            continue
                        if event_time_raw in (None, ""):
                            issue(
                                "events_schema",
                                "safety event simulation_seconds is invalid",
                                "events.csv",
                            )
                        if not row.get("source", ""):
                            issue(
                                "events_schema",
                                "safety event source is required",
                                "events.csv",
                            )
                        if not entity_ids or not isinstance(decoded_entities, list):
                            issue(
                                "events_schema",
                                "safety event entity_ids must be a JSON array",
                                "events.csv",
                            )
                        if not confidence_raw:
                            issue(
                                "events_schema",
                                "safety event confidence is required",
                                "events.csv",
                            )
                        if row.get("intersection_id") != manifest.get("scene_id"):
                            issue(
                                "events_schema",
                                "safety event intersection_id does not match manifest",
                                "events.csv",
                            )
                        if row.get("algorithm") != manifest.get("algorithm"):
                            issue(
                                "events_schema",
                                "safety event algorithm does not match manifest",
                                "events.csv",
                            )
            except Exception as exc:
                issue("events_schema", str(exc), "events.csv")

        if hashes.get("algorithm") != "sha256":
            issue(
                "hash_schema",
                "hashes algorithm must be sha256",
                "hashes.json",
            )
        files = hashes.get("files")
        if not isinstance(files, Mapping):
            issue("hash_schema", "hashes files must be a mapping", "hashes.json")
            return issues
        allowed_names = set(RunArtifacts.evidence_required_output_names()[:-1])
        safe_files: dict[str, object] = {}
        for relative, expected in files.items():
            safe = (
                isinstance(relative, str)
                and "\\" not in relative
                and PurePosixPath(relative).name == relative
                and not PurePosixPath(relative).is_absolute()
                and relative in allowed_names
            )
            if not safe:
                issue("unsafe_hash_path", f"unsafe hash path: {relative!r}", "hashes.json")
                continue
            if not isinstance(expected, str) or not _SHA256_PATTERN.fullmatch(
                expected
            ):
                issue(
                    "hash_schema",
                    f"invalid SHA-256 digest for {relative}",
                    "hashes.json",
                )
            safe_files[relative] = expected
        expected_names: set[str] = set()
        for name in RunArtifacts.evidence_required_output_names()[:-1]:
            path = run_dir / name
            if unsafe_link(path, name):
                continue
            try:
                if path.is_file() and path.stat().st_size > 0:
                    expected_names.add(name)
            except OSError as exc:
                issue("evidence_io", str(exc), name)
        if set(safe_files) != expected_names:
            issue("hash_coverage", "hash file coverage does not match evidence files", "hashes.json")
        for relative, expected in safe_files.items():
            path = run_dir / str(relative)
            if unsafe_link(path, str(relative)):
                continue
            if not path.is_file():
                issue("missing_file", f"hashed file is missing: {relative}", str(relative))
                continue
            try:
                if (
                    isinstance(expected, str)
                    and _SHA256_PATTERN.fullmatch(expected)
                    and _sha256_file(path) != expected
                ):
                    issue("hash_mismatch", f"SHA-256 mismatch for {relative}", str(relative))
            except OSError as exc:
                issue("evidence_io", str(exc), str(relative))
        return issues
