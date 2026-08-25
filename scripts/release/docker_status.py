"""Collect non-mutating Docker release evidence for the judge deployment."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import re
import shutil
import subprocess
import sys
from typing import Callable, Mapping, Sequence
from uuid import uuid4


SCHEMA = "judge-docker-evidence.v1"
VALID_STATUSES = frozenset({"pass", "fail", "not_run"})
PHASES = (
    "static_contract",
    "headless_build",
    "headless_health",
    "headless_smoke",
    "save_load",
    "gui_build",
    "gui_smoke",
    "cleanup",
)
NON_CLEANUP_PHASES = PHASES[:-1]
REASONS = frozenset(
    {
        "docker_cli_unavailable",
        "docker_daemon_unavailable",
        "live_verification_not_run",
    }
)
LIVE_PASS_REASON = "live_verification_complete"
TARGET_PLATFORM_OS = "linux"
TARGET_PLATFORM_ARCHITECTURE = "amd64"
OWNERSHIP_LABEL_KEY = "io.challengecup.task19.invocation"
SOURCE_ARCHIVE = "赛题资料.7z"
OFFICIAL_DATA_DIRECTORY = Path("data") / "intersection_data"
CommandRunner = Callable[[Sequence[str], Path], object]
MAX_DETAIL_LENGTH = 280
COMMAND_TIMEOUT_SECONDS = 15
HEADLESS_PASS_PHASES = (
    "headless_build",
    "headless_health",
    "headless_smoke",
    "save_load",
    "cleanup",
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_INVOCATION_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
_EMPTY_STREAM_SHA256 = hashlib.sha256(b"").hexdigest()
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(
    r"(?i)(?<![a-z0-9+.-])[a-z]:[\\/]"
)
_WINDOWS_UNC_PATH_PATTERN = re.compile(r"(?<!\\)\\\\(?:[?\\.]\\|[^\\])")
_POSIX_ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![a-z0-9+./-])/(?!/)"
)
_API_ENDPOINT_PATH_PATTERN = re.compile(r"^/api/runs(?:/[a-z0-9-]+)?$")
_ENV_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(?:^|[\s;])"
    r"(?:api[_-]?key|home|password|path|secret|token|user[_-]?name|"
    r"user|authorization|auth)\s*="
)
_JSON_ENVIRONMENT_KEY_PATTERN = re.compile(
    r"(?i)[{,]\s*[\"']?"
    r"(?:api[_-]?key|home|password|secret|token|user[_-]?name|user|"
    r"authorization|auth|env(?:ironment)?)\s*[\"']?\s*:"
)
_SENSITIVE_URL_QUERY_PATTERN = re.compile(
    r"(?i)[?&;](?:api[_-]?key|password|secret|token|auth(?:orization)?|"
    r"user[_-]?name)=[^&#\s]*"
)
_CLI_VERSION_PATTERN = re.compile(
    r"(?i)\bdocker version\s+([0-9][0-9a-z._+-]*)"
)
_VERSION_TOKEN_PATTERN = re.compile(
    r"\b([0-9]+(?:\.[0-9a-z]+)+)\b", re.IGNORECASE
)
_FORBIDDEN_NORMALIZED_KEYS = frozenset(
    {
        "apikey",
        "environment",
        "environ",
        "env",
        "password",
        "processlist",
        "processes",
        "secret",
        "token",
        "user",
        "username",
        "authorization",
        "auth",
    }
)
_EVIDENCE_KEYS = frozenset(
    {
        "schema",
        "checked_at",
        "status",
        "reason",
        "platform",
        "cli",
        "daemon",
        "invocation_id",
        "invocation",
        "quick_smoke",
        "save_load_proof",
        "gui_frame_proof",
        "name_collisions",
        "owned_resources",
        "exported_evidence",
        *PHASES,
    }
)
_PLATFORM_KEYS = frozenset({"os", "architecture"})
_COMMAND_RECORD_KEYS = frozenset(
    {
        "status",
        "started_at",
        "finished_at",
        "argv",
        "exit_code",
        "stdout_sha256",
        "stderr_sha256",
        "detail",
        "execution",
        "api_proof",
        "failure_proof",
    }
)
_STATIC_CONTRACT_RECORD_KEYS = _COMMAND_RECORD_KEYS | frozenset(
    {"render_proof"}
)
_RENDER_PROOF_KEYS = frozenset(
    {"status", "argv", "exit_code", "stdout_sha256", "selected_facts"}
)
_RENDER_FACT_KEYS = frozenset(
    {"source_stdout_sha256", "project", "profiles", "services"}
)
_RENDER_SERVICE_KEYS = frozenset(
    {"name", "image", "platform", "labels", "additional_contexts"}
)
_CAPABILITY_RECORD_KEYS = _COMMAND_RECORD_KEYS | frozenset({"version"})
_INVOCATION_KEYS = frozenset(
    {
        "id",
        "compose_project",
        "headless_image",
        "gui_image",
        "imported_image",
        "headless_image_id",
        "repository_digest",
        "config_digest",
        "content_digest",
        "ownership_label",
    }
)
_OWNERSHIP_LABEL_KEYS = frozenset({"key", "value"})
_QUICK_SMOKE_KEYS = frozenset(
    {
        "evidence_class",
        "requested_steps",
        "completed_steps",
        "run_id",
        "terminal_status",
        "output",
        "container",
        "image",
        "request",
        "response",
        "terminal",
    }
)
_QUICK_SMOKE_OUTPUT_KEYS = frozenset({"root", "path", "run_id"})
_API_SMOKE_PROOF_KEYS = frozenset(
    {
        "requested_steps",
        "completed_steps",
        "run_id",
        "terminal_status",
        "output",
        "container",
        "image",
        "request",
        "response",
        "terminal",
    }
)
_API_REQUEST_KEYS = frozenset({"method", "path", "body", "body_sha256"})
_API_REQUEST_BODY_KEYS = frozenset(
    {"intersection_id", "algorithm", "steps"}
)
_API_RESPONSE_KEYS = frozenset({"status", "run_id", "body_sha256"})
_API_TERMINAL_KEYS = frozenset(
    {
        "method",
        "path",
        "status",
        "run_id",
        "state",
        "completed_steps",
        "body_sha256",
    }
)
_SAVE_LOAD_PROOF_KEYS = frozenset(
    {
        "tar_path",
        "imported_image",
        "imported_container",
        "image_load",
        "image_retag",
        "imported_container_create",
        "imported_container_start",
        "repeated_health",
        "repeated_smoke",
    }
)
_COLLISION_KEYS = frozenset({"expected_resources", "before"})
_EXPECTED_RESOURCE_KEYS = frozenset(
    {"compose_project", "containers", "networks", "volumes", "images"}
)
_OWNED_RESOURCE_KEYS = frozenset(
    {"before_cleanup", "after_cleanup", "cleanup_actions"}
)
_OWNED_RESOURCE_ENTRY_KEYS = frozenset({"kind", "name", "labels"})
_OWNED_RESOURCE_LABEL_KEYS = frozenset({OWNERSHIP_LABEL_KEY})
_CLEANUP_ACTION_KEYS = frozenset(
    {
        "resource_kind",
        "resource_name",
        "required_label",
        "execution",
        "argv",
        "exit_code",
        "stdout_sha256",
        "stderr_sha256",
        "failure_proof",
    }
)
_SAFETY_REFUSAL_PROOF_KEYS = frozenset(
    {
        "kind",
        "resource_kind",
        "resource_name",
        "required_label",
        "observed_ownership",
    }
)
_INTERRUPTION_PROOF_KEYS = frozenset(
    {"kind", "interruption_kind", "phase"}
)
_OBSERVED_OWNERSHIP_RESULTS = frozenset(
    {"missing_resource", "missing_label", "mismatched_label"}
)
_INTERRUPTION_KINDS = frozenset({"keyboard_interrupt", "base_exception"})
_EXPORTED_EVIDENCE_KEYS = frozenset({"status", "path", "contents"})
_EXPORTED_CONTENT_KEYS = frozenset({"path", "sha256", "byte_length"})
_GUI_FRAME_PROOF_KEYS = frozenset({"run_id", "container", "image", "frames"})
_GUI_FRAME_KEYS = frozenset(
    {"path", "byte_length", "sha256", "sequence", "simulation_time"}
)


class DockerStatusError(ValueError):
    """Raised when evidence creation cannot safely continue."""


def _timestamp() -> str:
    current = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return current.replace("+00:00", "Z")


def _stream_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _hash_text(value: object) -> str:
    if isinstance(value, bytes):
        encoded = value
    else:
        encoded = _stream_text(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _timeout_stream(error: subprocess.TimeoutExpired, name: str) -> object:
    """Return the partial captured stream without serializing its raw text."""
    if name == "stdout":
        return getattr(error, "stdout", None) or getattr(error, "output", "")
    return getattr(error, "stderr", "")


def _sanitized_version(value: object, *, cli: bool) -> str | None:
    """Return only a version token from a Docker command stream."""
    stream = _stream_text(value)
    pattern = _CLI_VERSION_PATTERN if cli else _VERSION_TOKEN_PATTERN
    match = pattern.search(stream)
    return match.group(1) if match else None


def _record(
    status: str,
    detail: str,
    *,
    argv: Sequence[str] = (),
    exit_code: int | None = None,
    stdout: object = "",
    stderr: object = "",
    version: str | None = None,
    timestamp: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, object]:
    if timestamp is not None:
        started = timestamp
        finished = timestamp
    elif started_at is None and finished_at is None:
        started = _timestamp()
        finished = started
    else:
        started = started_at or _timestamp()
        finished = finished_at or started
    record: dict[str, object] = {
        "status": status,
        "started_at": started,
        "finished_at": finished,
        "argv": [str(item) for item in argv],
        "exit_code": exit_code,
        "stdout_sha256": _hash_text(stdout),
        "stderr_sha256": _hash_text(stderr),
        "detail": str(detail)[:MAX_DETAIL_LENGTH],
    }
    if version is not None:
        record["version"] = version
    return record


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _require_allowed_keys(
    value: Mapping[str, object], allowed: frozenset[str], name: str
) -> None:
    """Reject schema fields that the named evidence object does not define."""
    if any(not isinstance(key, str) for key in value):
        raise ValueError(f"{name} contains unexpected fields")
    if set(value).difference(allowed):
        raise ValueError(f"{name} contains unexpected fields")


def _normalized_sensitive_key(key: str) -> str:
    """Normalize case and separators before comparing sensitive field names."""
    return re.sub(r"[^a-z0-9]", "", key.casefold())


def _require_status(value: object, name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError(f"{name} status must be a string")
    if value not in VALID_STATUSES:
        raise ValueError(f"{name} status is invalid")
    return value


def _is_exact_integer(value: object, expected: int) -> bool:
    """Return whether a JSON value is the exact non-Boolean integer."""
    return (
        not isinstance(value, bool)
        and isinstance(value, int)
        and value == expected
    )


def _require_timestamp(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} timestamp is missing")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} timestamp is invalid") from exc


def _require_sha256(value: object, name: str) -> None:
    if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
        raise ValueError(f"{name} SHA-256 is invalid")


def _require_relative_path(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} path is invalid")
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if posix_path.is_absolute() or windows_path.is_absolute():
        raise ValueError(f"{name} path must be relative")
    if ".." in posix_path.parts or ".." in windows_path.parts:
        raise ValueError(f"{name} path must be relative without traversal")
    return value


def _require_canonical_relative_path(value: object, name: str) -> str:
    """Require a portable relative path with exactly one spelling."""
    path = _require_relative_path(value, name)
    if path != str(PurePosixPath(path)):
        raise ValueError(f"{name} path must be canonical")
    return path


def _portable_path_identity(path: str) -> str:
    """Return the case-insensitive identity of an already canonical path."""
    return path.casefold()


def _reject_private_values(value: object, location: str = "evidence") -> None:
    """Reject values that are non-JSON or disclose private host data."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{location} contains a non-finite number")
        return
    if isinstance(value, str):
        if (
            _WINDOWS_DRIVE_PATH_PATTERN.search(value)
            or _WINDOWS_UNC_PATH_PATTERN.search(value)
        ):
            raise ValueError(f"{location} contains an absolute path")
        if (
            _POSIX_ABSOLUTE_PATH_PATTERN.search(value)
            and not _API_ENDPOINT_PATH_PATTERN.fullmatch(value)
        ):
            raise ValueError(f"{location} contains an absolute path")
        if (
            _ENV_ASSIGNMENT_PATTERN.search(value)
            or _JSON_ENVIRONMENT_KEY_PATTERN.search(value)
        ):
            raise ValueError(f"{location} contains environment data")
        if _SENSITIVE_URL_QUERY_PATTERN.search(value):
            raise ValueError(f"{location} contains a secret URL query")
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{location} contains a non-string key")
            if _normalized_sensitive_key(key) in _FORBIDDEN_NORMALIZED_KEYS:
                raise ValueError(f"{location} contains forbidden private data")
            _reject_private_values(nested, f"{location}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _reject_private_values(nested, f"{location}[{index}]")
        return
    raise ValueError(f"{location} contains a non-JSON value")


def _validate_record(name: str, value: object) -> None:
    record = _require_mapping(value, name)
    if name in {"cli", "daemon"}:
        allowed = _CAPABILITY_RECORD_KEYS
    elif name == "static_contract":
        allowed = _STATIC_CONTRACT_RECORD_KEYS
    else:
        allowed = _COMMAND_RECORD_KEYS
    _require_allowed_keys(record, allowed, name)
    if name == "static_contract" and "render_proof" in record:
        render = _require_mapping(
            record.get("render_proof"), "static contract render proof"
        )
        _require_allowed_keys(
            render, _RENDER_PROOF_KEYS, "static contract render proof"
        )
        facts = _require_mapping(
            render.get("selected_facts"), "render selected facts"
        )
        _require_allowed_keys(
            facts, _RENDER_FACT_KEYS, "render selected facts"
        )
        services = facts.get("services")
        if not isinstance(services, list):
            raise ValueError("render selected facts services must be a list")
        for index, service_value in enumerate(services):
            service = _require_mapping(
                service_value, f"render selected service {index}"
            )
            _require_allowed_keys(
                service,
                _RENDER_SERVICE_KEYS,
                f"render selected service {index}",
            )
    status = _require_status(record.get("status"), name)
    started_at = _require_timestamp(record.get("started_at"), name)
    finished_at = _require_timestamp(record.get("finished_at"), name)
    if finished_at < started_at:
        raise ValueError(f"{name} finished before it started")
    argv = record.get("argv")
    if not isinstance(argv, list) or not all(
        isinstance(item, str) for item in argv
    ):
        raise ValueError(f"{name} argv must be a string list")
    exit_code = record.get("exit_code")
    if exit_code is not None and (
        isinstance(exit_code, bool) or not isinstance(exit_code, int)
    ):
        raise ValueError(f"{name} exit code is invalid")
    _require_sha256(record.get("stdout_sha256"), f"{name} stdout")
    _require_sha256(record.get("stderr_sha256"), f"{name} stderr")
    detail = record.get("detail")
    if not isinstance(detail, str) or len(detail) > MAX_DETAIL_LENGTH:
        raise ValueError(f"{name} detail is invalid")
    version = record.get("version")
    if version is not None and (
        not isinstance(version, str) or len(version) > MAX_DETAIL_LENGTH
    ):
        raise ValueError(f"{name} version is invalid")
    execution = record.get("execution", "command")
    if execution not in {
        "command",
        "api_result",
        "safety_refusal",
        "interruption",
    }:
        raise ValueError(f"{name} execution kind is invalid")
    if execution == "api_result":
        if "failure_proof" in record:
            raise ValueError(f"{name} API result cannot contain failure proof")
        if status != "pass":
            raise ValueError(f"{name} API result must pass")
        if argv or exit_code is not None:
            raise ValueError(f"{name} API result cannot claim a command")
        if (
            record.get("stdout_sha256") != _EMPTY_STREAM_SHA256
            or record.get("stderr_sha256") != _EMPTY_STREAM_SHA256
        ):
            raise ValueError(
                f"{name} API result must have empty stream hashes"
            )
        if not isinstance(record.get("api_proof"), Mapping):
            raise ValueError(f"{name} API result requires structured proof")
    elif execution in {"safety_refusal", "interruption"}:
        if status != "fail":
            raise ValueError(f"{name} failure execution must fail")
        if argv or exit_code is not None:
            raise ValueError(
                f"{name} failure execution cannot claim a command"
            )
        if (
            record.get("stdout_sha256") != _EMPTY_STREAM_SHA256
            or record.get("stderr_sha256") != _EMPTY_STREAM_SHA256
        ):
            raise ValueError(
                f"{name} failure execution must have empty streams"
            )
        if "api_proof" in record:
            raise ValueError(
                f"{name} failure execution cannot contain API proof"
            )
        proof = record.get("failure_proof")
        if not isinstance(proof, Mapping):
            raise ValueError(f"{name} failure execution requires proof")
        if execution == "safety_refusal":
            if name != "cleanup":
                raise ValueError("safety refusal is cleanup-only")
            _require_allowed_keys(
                proof, _SAFETY_REFUSAL_PROOF_KEYS, "safety refusal proof"
            )
            if proof.get("kind") != "cleanup_ownership_refusal":
                raise ValueError("safety refusal proof kind is invalid")
            if proof.get("resource_kind") not in {
                "container",
                "network",
                "volume",
                "image",
            }:
                raise ValueError("safety refusal resource kind is invalid")
            resource_name = proof.get("resource_name")
            if not isinstance(resource_name, str) or not resource_name:
                raise ValueError("safety refusal resource name is invalid")
            required_label = _require_mapping(
                proof.get("required_label"), "safety refusal required label"
            )
            _require_allowed_keys(
                required_label,
                _OWNERSHIP_LABEL_KEYS,
                "safety refusal required label",
            )
            if required_label.get("key") != OWNERSHIP_LABEL_KEY:
                raise ValueError("safety refusal label key is invalid")
            if proof.get("observed_ownership") not in (
                _OBSERVED_OWNERSHIP_RESULTS
            ):
                raise ValueError("safety refusal observation is invalid")
        else:
            _require_allowed_keys(
                proof, _INTERRUPTION_PROOF_KEYS, "interruption proof"
            )
            if proof.get("kind") != "interruption":
                raise ValueError("interruption proof kind is invalid")
            if proof.get("interruption_kind") not in _INTERRUPTION_KINDS:
                raise ValueError("interruption kind is invalid")
            if proof.get("phase") != name or name not in PHASES:
                raise ValueError("interruption proof phase is invalid")
    elif "api_proof" in record:
        raise ValueError(f"{name} command cannot contain API proof")
    elif "failure_proof" in record:
        raise ValueError(f"{name} command cannot contain failure proof")
    elif status == "pass":
        if exit_code != 0:
            raise ValueError(f"{name} pass record must have zero exit code")
        if not argv:
            raise ValueError(f"{name} pass record must have a command")
    elif status == "fail":
        if not argv:
            raise ValueError(f"{name} fail record must have a command")
        if exit_code is None or exit_code == 0:
            raise ValueError(
                f"{name} fail record must have a nonzero exit code"
            )
    elif exit_code == 0:
        raise ValueError(f"{name} not_run record cannot have zero exit code")
    _reject_private_values(record, name)


def _validate_untouched_not_run_phase(
    name: str, record: Mapping[str, object]
) -> None:
    """Require a live phase labeled not-run to have no execution metadata."""
    if _command_tokens(record, name) or record.get("exit_code") is not None:
        raise ValueError(f"{name} not_run phase must be untouched")
    if (
        record.get("stdout_sha256") != _EMPTY_STREAM_SHA256
        or record.get("stderr_sha256") != _EMPTY_STREAM_SHA256
    ):
        raise ValueError(f"{name} not_run phase must have empty stream hashes")


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not _DIGEST_PATTERN.fullmatch(value):
        raise ValueError(f"{name} digest is invalid")
    return value


def _normalized_platform_value(value: str, *, architecture: bool) -> str:
    normalized = value.strip().casefold().replace("_", "-")
    if architecture and normalized in {"amd64", "x64", "x86-64"}:
        return TARGET_PLATFORM_ARCHITECTURE
    return normalized


def _require_pass_record(
    payload: Mapping[str, object], name: str
) -> Mapping[str, object]:
    record = _require_mapping(payload.get(name), name)
    if record.get("status") != "pass":
        raise ValueError(f"pass evidence requires {name} to pass")
    if record.get("execution") == "api_result":
        return record
    if record.get("exit_code") != 0:
        raise ValueError(f"pass evidence requires zero-exit {name}")
    argv = record.get("argv")
    if not isinstance(argv, list) or not argv:
        raise ValueError(f"pass evidence requires a command for {name}")
    return record


def _require_cli_version_record(
    payload: Mapping[str, object]
) -> Mapping[str, object]:
    """Require the exact successful CLI capability query."""
    record = _require_pass_record(payload, "cli")
    if _require_docker_command(record, "cli") != ["docker", "--version"]:
        raise ValueError("cli must record the Docker version query")
    return record


def _require_daemon_info_record(
    payload: Mapping[str, object]
) -> Mapping[str, object]:
    """Require the exact successful daemon capability query."""
    record = _require_pass_record(payload, "daemon")
    expected = ["docker", "info", "--format", "{{json .ServerVersion}}"]
    if _require_docker_command(record, "daemon") != expected:
        raise ValueError("daemon must record the Docker info query")
    return record


def _command_tokens(record: Mapping[str, object], name: str) -> list[str]:
    argv = record.get("argv")
    if not isinstance(argv, list) or not all(
        isinstance(item, str) for item in argv
    ):
        raise ValueError(f"{name} command is invalid")
    return argv


def _require_docker_command(
    record: Mapping[str, object], name: str
) -> list[str]:
    argv = _command_tokens(record, name)
    if not argv or argv[0] != "docker":
        raise ValueError(f"{name} must record a Docker argv")
    return argv


def _argv_contains(argv: Sequence[str], *tokens: str) -> bool:
    return all(token in argv for token in tokens)


def _require_option_value(
    argv: Sequence[str], option: str, name: str
) -> str:
    """Return a required command option value from sanitized argv metadata."""
    try:
        index = argv.index(option)
    except ValueError as exc:
        raise ValueError(f"{name} must record {option}") from exc
    if index + 1 >= len(argv) or not argv[index + 1]:
        raise ValueError(f"{name} must record a value for {option}")
    return argv[index + 1]


def _option_occurrences(
    argv: Sequence[str], option: str, name: str
) -> list[tuple[str, bool]]:
    """Return each option value and whether it used ``--option=value``."""
    occurrences: list[tuple[str, bool]] = []
    alternate_prefix = f"{option}="
    for index, token in enumerate(argv):
        if token == option:
            if index + 1 >= len(argv) or not argv[index + 1]:
                raise ValueError(f"{name} must record a value for {option}")
            occurrences.append((argv[index + 1], False))
        elif token.startswith(alternate_prefix):
            value = token[len(alternate_prefix):]
            if not value:
                raise ValueError(f"{name} must record a value for {option}")
            occurrences.append((value, True))
    return occurrences


def _require_unique_label(
    argv: Sequence[str], label_key: str, name: str
) -> str:
    """Return exactly one split ``--label`` value for the requested key."""
    labels: list[str] = []
    for label, inline in _option_occurrences(argv, "--label", name):
        key, _separator, _value = label.partition("=")
        if key != label_key:
            continue
        if inline:
            raise ValueError(
                f"{name} ownership label must use --label VALUE"
            )
        labels.append(label)
    if len(labels) != 1:
        raise ValueError(
            f"{name} must record ownership label {label_key} exactly once"
        )
    return labels[0]


def _validate_phase_command(
    name: str, record: Mapping[str, object]
) -> None:
    """Ensure a claimed phase records the class of Docker action it needs."""
    if record.get("execution") == "api_result":
        if name not in {"headless_smoke", "gui_smoke"}:
            raise ValueError(f"{name} cannot use API-result execution")
        return
    argv = _require_docker_command(record, name)
    if name == "static_contract":
        if not _argv_contains(argv, "compose", "config"):
            raise ValueError("static_contract must record compose config")
    elif name in {"headless_build", "gui_build"}:
        if "build" not in argv:
            raise ValueError(f"{name} must record a platform build")
    elif name in {"headless_health", "gui_smoke"}:
        if "inspect" not in argv and "exec" not in argv:
            raise ValueError(f"{name} must record a health or smoke command")
    elif name == "headless_smoke":
        if "exec" not in argv:
            raise ValueError("headless_smoke must record a container command")
    elif name == "save_load":
        if not _argv_contains(argv, "image", "save"):
            raise ValueError("save_load must record docker image save")
    elif name == "cleanup":
        if "rm" not in argv:
            raise ValueError("cleanup must record an exact removal command")


def _validate_phase_command_identity(
    payload: Mapping[str, object],
    name: str,
    record: Mapping[str, object],
) -> None:
    """Bind a reached command phase to its exact invocation-scoped target."""
    invocation_id, invocation = _validate_invocation(payload)
    del invocation_id
    project = invocation.get("compose_project")
    primary_container = f"{project}-judge-1"
    gui_container = f"{project}-judge-gui-1"
    argv = _require_docker_command(record, name)
    expected: list[str] | None = None
    alternatives: list[list[str]] = []
    if name == "static_contract":
        expected = [
            "docker",
            "compose",
            "--project-name",
            project,
        ]
        if any(
            _require_mapping(payload.get(gui_phase), gui_phase).get("status")
            != "not_run"
            for gui_phase in ("gui_build", "gui_smoke")
        ):
            expected.extend(["--profile", "gui"])
        expected.extend(["config", "--quiet"])
    elif name == "headless_build":
        expected = [
            "docker",
            "compose",
            "--project-name",
            project,
            "build",
            "judge",
        ]
        alternatives.append(
            [
                "docker",
                "build",
                "--platform",
                f"{TARGET_PLATFORM_OS}/{TARGET_PLATFORM_ARCHITECTURE}",
                "-t",
                invocation.get("headless_image"),
                ".",
            ]
        )
    elif name == "headless_health":
        expected = [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            primary_container,
        ]
    elif name == "gui_build":
        expected = [
            "docker",
            "compose",
            "--project-name",
            project,
            "--profile",
            "gui",
            "build",
            "judge-gui",
        ]
    elif name in {"headless_smoke", "gui_smoke"}:
        target = (
            primary_container
            if name == "headless_smoke"
            else gui_container
        )
        if (
            argv[:3] != ["docker", "exec", target]
            or len(argv) < 4
            or "docker" in argv[3:]
        ):
            raise ValueError(f"{name} command target is not canonical")
        return
    else:
        return
    if argv != expected and argv not in alternatives:
        raise ValueError(f"{name} command is not canonical")


def _validate_invocation(
    payload: Mapping[str, object]
) -> tuple[str, Mapping[str, object]]:
    invocation_id = payload.get("invocation_id")
    if (
        not isinstance(invocation_id, str)
        or not _INVOCATION_ID_PATTERN.fullmatch(invocation_id)
    ):
        raise ValueError("pass evidence requires a unique invocation ID")
    invocation = _require_mapping(payload.get("invocation"), "invocation")
    _require_allowed_keys(invocation, _INVOCATION_KEYS, "invocation")
    if invocation.get("id") != invocation_id:
        raise ValueError("invocation ID does not match invocation object")

    expected_project = f"ca-mp-task19-{invocation_id}"
    expected_images = {
        "headless_image": f"{expected_project}-headless:local",
        "gui_image": f"{expected_project}-gui:local",
        "imported_image": f"{expected_project}-imported:local",
    }
    if invocation.get("compose_project") != expected_project:
        raise ValueError("invocation compose project is not unique")
    for name, expected in expected_images.items():
        if invocation.get(name) != expected:
            raise ValueError(f"invocation {name} is invalid")
    _require_digest(invocation.get("headless_image_id"), "headless image ID")
    for name in ("repository_digest", "config_digest", "content_digest"):
        _require_digest(invocation.get(name), name)

    label = _require_mapping(
        invocation.get("ownership_label"), "ownership label"
    )
    _require_allowed_keys(label, _OWNERSHIP_LABEL_KEYS, "ownership label")
    if (
        label.get("key") != OWNERSHIP_LABEL_KEY
        or label.get("value") != invocation_id
    ):
        raise ValueError("ownership label does not match invocation")
    return invocation_id, invocation


def _validate_compose_build_project(
    argv: Sequence[str], expected_project: object, name: str
) -> None:
    """Require one split long Compose project in its global position."""
    project_spellings = []
    for token in argv:
        if token in {"--project-name", "-p"} or token.startswith(
            ("--project-name=", "-p=")
        ):
            project_spellings.append(token)
    if (
        len(project_spellings) != 1
        or project_spellings[0] != "--project-name"
        or list(argv[:4])
        != ["docker", "compose", "--project-name", expected_project]
    ):
        raise ValueError(f"{name} Compose project is invalid")


def _validate_compose_build_profile(
    argv: Sequence[str], *, gui: bool, name: str
) -> None:
    """Require the exact profile scope for one Compose build axis."""
    profile_spellings = [
        token
        for token in argv
        if token == "--profile" or token.startswith("--profile=")
    ]
    if gui:
        if (
            profile_spellings != ["--profile"]
            or list(argv[4:6]) != ["--profile", "gui"]
        ):
            raise ValueError(f"{name} Compose profile is invalid")
    elif profile_spellings:
        raise ValueError(f"{name} Compose profile is forbidden")


def _reject_compose_direct_build_options(
    argv: Sequence[str], name: str
) -> None:
    """Reject metadata flags owned by direct ``docker build`` grammar."""
    direct_options = ("--platform", "-t", "--tag", "--label")
    for token in argv:
        if token in direct_options or any(
            token.startswith(f"{option}=") for option in direct_options
        ):
            raise ValueError(f"{name} has a direct-only build option")


def _validate_pass_build_projects(
    payload: Mapping[str, object], invocation: Mapping[str, object]
) -> None:
    expected_project = invocation.get("compose_project")
    for name in ("headless_build", "gui_build"):
        record = _require_mapping(payload.get(name), name)
        if record.get("status") != "pass":
            continue
        argv = _require_docker_command(record, name)
        if len(argv) > 1 and argv[1] == "compose":
            _validate_compose_build_project(argv, expected_project, name)
            _validate_compose_build_profile(
                argv, gui=name == "gui_build", name=name
            )
            _reject_compose_direct_build_options(argv, name)
            expected = [
                "docker",
                "compose",
                "--project-name",
                expected_project,
            ]
            if name == "gui_build":
                expected.extend(["--profile", "gui"])
            expected.extend(
                ["build", "judge-gui" if name == "gui_build" else "judge"]
            )
            if argv != expected:
                raise ValueError(f"{name} Compose service is invalid")
        elif name == "headless_build":
            expected = [
                "docker",
                "build",
                "--platform",
                f"{TARGET_PLATFORM_OS}/{TARGET_PLATFORM_ARCHITECTURE}",
                "-t",
                invocation.get("headless_image"),
                ".",
            ]
            if argv != expected:
                raise ValueError("direct headless build grammar is invalid")
        else:
            raise ValueError("GUI build must use canonical Compose grammar")


def _validate_static_contract_scope(
    payload: Mapping[str, object], invocation: Mapping[str, object]
) -> bool:
    """Validate quiet config argv and return whether it is GUI-scoped."""
    gui_scope = any(
        _require_mapping(payload.get(name), name).get("status") != "not_run"
        for name in ("gui_build", "gui_smoke")
    )
    expected = [
        "docker",
        "compose",
        "--project-name",
        invocation.get("compose_project"),
    ]
    if gui_scope:
        expected.extend(["--profile", "gui"])
    expected.extend(["config", "--quiet"])
    static = _require_mapping(
        payload.get("static_contract"), "static_contract"
    )
    argv = _require_docker_command(static, "static_contract")
    if argv != expected:
        raise ValueError("static_contract scope or command is invalid")
    if static.get("stdout_sha256") != _EMPTY_STREAM_SHA256:
        raise ValueError("static_contract quiet stdout must be empty")
    return gui_scope


def _validate_render_command(
    payload: Mapping[str, object],
    invocation: Mapping[str, object],
    *,
    gui_scope: bool,
) -> Mapping[str, object]:
    """Validate the independently hashed structured Compose render command."""
    static = _require_mapping(
        payload.get("static_contract"), "static_contract"
    )
    render = _require_mapping(
        static.get("render_proof"), "static contract render proof"
    )
    expected = [
        "docker",
        "compose",
        "--project-name",
        invocation.get("compose_project"),
    ]
    if gui_scope:
        expected.extend(["--profile", "gui"])
    expected.extend(["config", "--format", "json"])
    if render.get("status") != "pass" or not _is_exact_integer(
        render.get("exit_code"), 0
    ):
        raise ValueError("render proof must record a successful command")
    if render.get("argv") != expected:
        raise ValueError("render proof command scope is invalid")
    stdout_sha256 = render.get("stdout_sha256")
    _require_sha256(stdout_sha256, "render proof stdout")
    if stdout_sha256 == _EMPTY_STREAM_SHA256:
        raise ValueError("render proof stdout must be nonempty")
    facts = _require_mapping(
        render.get("selected_facts"), "render selected facts"
    )
    if facts.get("source_stdout_sha256") != stdout_sha256:
        raise ValueError("render selected facts stdout hash is mismatched")
    return facts


def _validate_render_facts(
    facts: Mapping[str, object],
    invocation_id: str,
    invocation: Mapping[str, object],
    *,
    gui_scope: bool,
) -> dict[str, Mapping[str, object]]:
    """Bind selected Compose facts to exact invocation-owned services."""
    if facts.get("project") != invocation.get("compose_project"):
        raise ValueError("render selected project is invalid")
    expected_profiles = ["gui"] if gui_scope else []
    if facts.get("profiles") != expected_profiles:
        raise ValueError("render selected profiles are invalid")
    services_value = facts.get("services")
    if not isinstance(services_value, list):
        raise ValueError("render selected services are invalid")
    expected_names = {"judge", "judge-gui"} if gui_scope else {"judge"}
    services: dict[str, Mapping[str, object]] = {}
    for index, value in enumerate(services_value):
        service = _require_mapping(value, f"render selected service {index}")
        name = service.get("name")
        if not isinstance(name, str) or name in services:
            raise ValueError("render selected services contain duplicates")
        services[name] = service
    if set(services) != expected_names:
        raise ValueError("render selected services are invalid")
    expected_label = {OWNERSHIP_LABEL_KEY: invocation_id}
    expected_images = {
        "judge": invocation.get("headless_image"),
        "judge-gui": invocation.get("gui_image"),
    }
    for name, service in services.items():
        if service.get("image") != expected_images[name]:
            raise ValueError("render selected service image is invalid")
        if service.get("platform") != (
            f"{TARGET_PLATFORM_OS}/{TARGET_PLATFORM_ARCHITECTURE}"
        ):
            raise ValueError("render selected service platform is invalid")
        if service.get("labels") != expected_label:
            raise ValueError("render selected ownership label is invalid")
        expected_contexts = (
            {"judge_base": "service:judge"} if name == "judge-gui" else {}
        )
        if service.get("additional_contexts") != expected_contexts:
            raise ValueError(
                "render selected service additional contexts are invalid"
            )
    return services


def _validate_nonpass_successful_build_claims(
    payload: Mapping[str, object],
) -> None:
    """Deeply validate successful 4.2 claims in a non-pass document."""
    static = _require_mapping(
        payload.get("static_contract"), "static_contract"
    )
    static_passed = static.get("status") == "pass"
    if "render_proof" in static and not static_passed:
        raise ValueError(
            "render proof cannot appear under non-pass static_contract"
        )

    successful_builds: list[tuple[str, Mapping[str, object]]] = []
    for name in ("headless_build", "gui_build"):
        record = _require_mapping(payload.get(name), name)
        if record.get("status") == "pass":
            successful_builds.append((name, record))
    if not static_passed and not successful_builds:
        return

    invocation_id, invocation = _validate_invocation(payload)
    _validate_pass_build_projects(payload, invocation)
    for name, record in successful_builds:
        argv = _require_docker_command(record, name)
        if len(argv) > 1 and argv[1] == "compose" and not static_passed:
            raise ValueError(
                f"{name} Compose success requires static render proof"
            )
    if not static_passed:
        return

    gui_scope = _validate_static_contract_scope(payload, invocation)
    render_facts = _validate_render_command(
        payload, invocation, gui_scope=gui_scope
    )
    _validate_render_facts(
        render_facts,
        invocation_id,
        invocation,
        gui_scope=gui_scope,
    )


def _validate_api_smoke_proof(
    value: object,
    name: str,
    *,
    expected_container: object,
    expected_image: object,
) -> Mapping[str, object]:
    """Validate one closed API-created 100-step smoke result."""
    proof = _require_mapping(value, name)
    _require_allowed_keys(proof, _API_SMOKE_PROOF_KEYS, name)
    if proof.get("container") != expected_container:
        raise ValueError(f"{name} container is invalid")
    if proof.get("image") != expected_image:
        raise ValueError(f"{name} image is invalid")

    request = _require_mapping(proof.get("request"), f"{name} request")
    _require_allowed_keys(request, _API_REQUEST_KEYS, f"{name} request")
    if request.get("method") != "POST":
        raise ValueError(f"{name} create method must be POST")
    if request.get("path") != "/api/runs":
        raise ValueError(f"{name} create endpoint must be /api/runs")
    body = _require_mapping(request.get("body"), f"{name} request body")
    _require_allowed_keys(body, _API_REQUEST_BODY_KEYS, f"{name} request body")
    intersection_id = body.get("intersection_id")
    if not isinstance(intersection_id, str) or intersection_id != "1":
        raise ValueError(f"{name} intersection_id must be the string '1'")
    algorithm = body.get("algorithm")
    if not isinstance(algorithm, str) or algorithm != "fixed_time":
        raise ValueError(
            f"{name} algorithm must be the string 'fixed_time'"
        )
    requested_steps = body.get("steps")
    if not _is_exact_integer(requested_steps, 100):
        raise ValueError(
            f"{name} API request must ask for exactly 100 steps"
        )
    _require_sha256(request.get("body_sha256"), f"{name} request body")

    response = _require_mapping(proof.get("response"), f"{name} response")
    _require_allowed_keys(response, _API_RESPONSE_KEYS, f"{name} response")
    if not _is_exact_integer(response.get("status"), 202):
        raise ValueError(f"{name} create response status must be 202")
    run_id = response.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError(f"{name} created API run ID is missing")
    _require_sha256(
        response.get("body_sha256"), f"{name} create response body"
    )

    terminal = _require_mapping(proof.get("terminal"), f"{name} terminal")
    _require_allowed_keys(terminal, _API_TERMINAL_KEYS, f"{name} terminal")
    if terminal.get("method") != "GET":
        raise ValueError(f"{name} terminal method must be GET")
    if not _is_exact_integer(terminal.get("status"), 200):
        raise ValueError(f"{name} terminal response status must be 200")
    if terminal.get("run_id") != run_id:
        raise ValueError(f"{name} terminal API run ID does not match")
    if terminal.get("path") != f"/api/runs/{run_id}":
        raise ValueError(f"{name} terminal endpoint must use the created ID")
    if terminal.get("state") != "completed":
        raise ValueError(f"{name} terminal state must be completed")
    terminal_steps = terminal.get("completed_steps")
    if not _is_exact_integer(terminal_steps, 100):
        raise ValueError(
            f"{name} API terminal must complete exactly 100 steps"
        )
    _require_sha256(
        terminal.get("body_sha256"), f"{name} terminal body"
    )

    summary_steps = proof.get("requested_steps")
    if not _is_exact_integer(summary_steps, 100):
        raise ValueError(f"{name} must record exactly 100 requested steps")
    completed_steps = proof.get("completed_steps")
    if (
        not isinstance(completed_steps, list)
        or any(
            isinstance(step, bool) or not isinstance(step, int)
            for step in completed_steps
        )
        or completed_steps != list(range(1, 101))
    ):
        raise ValueError(
            f"{name} must prove completed steps one through 100"
        )
    if proof.get("run_id") != run_id:
        raise ValueError(f"{name} API proof run ID does not match")
    if proof.get("terminal_status") != "completed":
        raise ValueError(f"{name} terminal status must be completed")

    output = _require_mapping(proof.get("output"), f"{name} output")
    _require_allowed_keys(output, _QUICK_SMOKE_OUTPUT_KEYS, f"{name} output")
    if output.get("root") != "app/output":
        raise ValueError(f"{name} output must be relative to app/output")
    output_path = _require_relative_path(output.get("path"), f"{name} output")
    if output_path.startswith("evidence/"):
        raise ValueError(f"{name} cannot use the formal evidence root")
    if output_path != f"runs/{run_id}":
        raise ValueError(f"{name} API output path does not match")
    if output.get("run_id") != run_id:
        raise ValueError(f"{name} API output run ID does not match")
    return proof


def _validate_quick_smoke(
    payload: Mapping[str, object],
    invocation: Mapping[str, object],
) -> Mapping[str, object]:
    quick_smoke = _require_mapping(payload.get("quick_smoke"), "quick smoke")
    _require_allowed_keys(quick_smoke, _QUICK_SMOKE_KEYS, "quick smoke")
    if quick_smoke.get("evidence_class") != "quick_smoke":
        raise ValueError("quick smoke evidence class is invalid")
    phase = _require_mapping(payload.get("headless_smoke"), "headless smoke")
    if phase.get("execution") != "api_result":
        raise ValueError("pass evidence requires a primary API smoke result")

    compose_project = invocation.get("compose_project")
    primary = _validate_api_smoke_proof(
        phase.get("api_proof"),
        "primary API smoke",
        expected_container=f"{compose_project}-judge-1",
        expected_image=invocation.get("headless_image"),
    )
    summary = dict(quick_smoke)
    summary.pop("evidence_class")
    if summary.get("run_id") != primary.get("run_id"):
        raise ValueError("quick smoke summary must match API proof")
    _validate_api_smoke_proof(
        summary,
        "primary API smoke summary",
        expected_container=f"{compose_project}-judge-1",
        expected_image=invocation.get("headless_image"),
    )
    if summary != dict(primary):
        raise ValueError("quick smoke summary must match API proof")
    return primary


def _validate_independent_api_smokes(
    primary: Mapping[str, object], imported: Mapping[str, object]
) -> None:
    """Require independently created primary and imported API results."""
    primary_response = _require_mapping(
        primary.get("response"), "primary API smoke response"
    )
    imported_response = _require_mapping(
        imported.get("response"), "imported API smoke response"
    )
    if imported_response.get("run_id") == primary_response.get("run_id"):
        raise ValueError("API smokes must have distinct run IDs")
    primary_output = _require_mapping(
        primary.get("output"), "primary API smoke output"
    )
    imported_output = _require_mapping(
        imported.get("output"), "imported API smoke output"
    )
    if imported_output.get("path") == primary_output.get("path"):
        raise ValueError("API smokes must have distinct output paths")
    if imported_response.get("body_sha256") == primary_response.get(
        "body_sha256"
    ):
        raise ValueError("imported API response hash must be distinct")
    primary_terminal = _require_mapping(
        primary.get("terminal"), "primary API smoke terminal"
    )
    imported_terminal = _require_mapping(
        imported.get("terminal"), "imported API smoke terminal"
    )
    if imported_terminal.get("body_sha256") == primary_terminal.get(
        "body_sha256"
    ):
        raise ValueError("imported API terminal hash must be distinct")


def _find_api_result_claims(
    value: object, path: tuple[object, ...] = ()
) -> list[tuple[tuple[object, ...], Mapping[str, object]]]:
    """Return every claim-bearing mapping and its exact document path."""
    claims: list[tuple[tuple[object, ...], Mapping[str, object]]] = []
    if isinstance(value, Mapping):
        if value.get("execution") == "api_result" or "api_proof" in value:
            claims.append((path, value))
        for key, nested in value.items():
            claims.extend(_find_api_result_claims(nested, (*path, key)))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            claims.extend(_find_api_result_claims(nested, (*path, index)))
    return claims


def _validate_present_api_results(payload: Mapping[str, object]) -> None:
    """Deeply validate every API result regardless of overall status."""
    allowed_locations = {
        ("headless_smoke",),
        ("save_load_proof", "repeated_smoke"),
        ("gui_smoke",),
    }
    claims = dict(_find_api_result_claims(payload))
    if any(location not in allowed_locations for location in claims):
        raise ValueError("API result location is invalid")
    imported_record = claims.get(
        ("save_load_proof", "repeated_smoke")
    )
    gui_record = claims.get(("gui_smoke",))

    primary_phase = _require_mapping(
        payload.get("headless_smoke"), "headless_smoke"
    )
    has_primary = primary_phase.get("execution") == "api_result"
    if (
        imported_record is not None or gui_record is not None
    ) and not has_primary:
        raise ValueError(
            "additional API smoke requires a primary API smoke result"
        )
    if not has_primary:
        return

    invocation_id, invocation = _validate_invocation(payload)
    primary = _validate_quick_smoke(payload, invocation)
    gui: Mapping[str, object] | None = None
    if gui_record is not None:
        gui = _validate_api_smoke_proof(
            gui_record.get("api_proof"),
            "GUI API smoke",
            expected_container=(
                f"{invocation.get('compose_project')}-judge-gui-1"
            ),
            expected_image=invocation.get("gui_image"),
        )
        _validate_independent_api_smokes(primary, gui)
    if imported_record is None:
        return

    _validate_save_load_proof(
        payload,
        invocation_id,
        invocation,
        primary,
        validate_phase_summary=not (
            payload.get("status") == "fail"
            and payload.get("reason") == "save_load_failed"
        ),
    )
    if gui is not None:
        imported = _validate_api_smoke_proof(
            imported_record.get("api_proof"),
            "imported API smoke",
            expected_container=(
                f"{invocation.get('compose_project')}-imported-judge-1"
            ),
            expected_image=invocation.get("imported_image"),
        )
        _validate_independent_api_smokes(imported, gui)


def _validate_save_load_nested_command(
    key: str,
    argv: list[str],
    *,
    tar_path: str,
    invocation_id: str,
    invocation: Mapping[str, object],
    imported_container: str,
) -> None:
    """Validate one save/load subcommand against its exact stage grammar."""
    headless_image = invocation.get("headless_image")
    imported_image = invocation.get("imported_image")
    expected_label = f"{OWNERSHIP_LABEL_KEY}={invocation_id}"
    exact_commands = {
        "image_load": ["docker", "image", "load", "--input", tar_path],
        "image_retag": [
            "docker",
            "image",
            "tag",
            headless_image,
            imported_image,
        ],
        "imported_container_create": [
            "docker",
            "container",
            "create",
            "--name",
            imported_container,
            "--label",
            expected_label,
            imported_image,
        ],
        "imported_container_start": [
            "docker",
            "container",
            "start",
            imported_container,
        ],
        "repeated_health": [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            imported_container,
        ],
    }
    if key == "repeated_smoke":
        if (
            argv[:3] != ["docker", "exec", imported_container]
            or len(argv) < 4
            or "docker" in argv[3:]
        ):
            raise ValueError("save/load repeated smoke command is invalid")
        return
    if argv != exact_commands.get(key):
        if key == "image_load":
            raise ValueError("save/load image load tar command is invalid")
        if key == "imported_container_create":
            raise ValueError(
                "save/load imported container create label command is invalid"
            )
        if key == "repeated_health":
            raise ValueError(
                "save/load repeated health must target the imported container"
            )
        raise ValueError(f"save/load {key} command is invalid")


def _validate_save_load_proof(
    payload: Mapping[str, object],
    invocation_id: str,
    invocation: Mapping[str, object],
    primary_api_proof: Mapping[str, object],
    *,
    validate_phase_summary: bool = True,
) -> None:
    proof = _require_mapping(payload.get("save_load_proof"), "save/load proof")
    _require_allowed_keys(proof, _SAVE_LOAD_PROOF_KEYS, "save/load proof")
    if proof.get("imported_image") != invocation.get("imported_image"):
        raise ValueError(
            "save/load proof must use the independent imported image"
        )
    tar_path = _require_relative_path(proof.get("tar_path"), "save/load tar")
    expected_tar_path = (
        f"output/evidence/docker/live/{invocation_id}/headless-image.tar"
    )
    if tar_path != expected_tar_path:
        raise ValueError("save/load tar path is invalid")
    compose_project = invocation.get("compose_project")
    imported_container = proof.get("imported_container")
    expected_container = f"{compose_project}-imported-judge-1"
    if imported_container != expected_container:
        raise ValueError("save/load imported container is invalid")

    if validate_phase_summary:
        save_record = _require_mapping(
            payload.get("save_load"), "save/load"
        )
        save_argv = _require_docker_command(save_record, "save/load")
        expected_save_argv = [
            "docker",
            "image",
            "save",
            "--output",
            tar_path,
            invocation.get("headless_image"),
        ]
        if save_argv != expected_save_argv:
            raise ValueError(
                "save/load phase does not prove the tar artifact"
            )
    records = {
        "image_load": "save/load image load",
        "image_retag": "save/load image retag",
        "imported_container_create": "save/load imported container",
        "imported_container_start": "save/load imported container start",
        "repeated_health": "save/load repeated health",
        "repeated_smoke": "save/load repeated smoke",
    }
    for key, name in records.items():
        _validate_record(name, proof.get(key))
        record = _require_mapping(proof.get(key), name)
        if record.get("execution") == "api_result":
            if key != "repeated_smoke":
                raise ValueError(f"{name} cannot use API-result execution")
            continue
        if key == "repeated_smoke":
            raise ValueError(
                "save/load requires an independent imported API smoke"
            )
        if record.get("status") != "pass" or record.get("exit_code") != 0:
            raise ValueError(f"{name} must pass")
        argv = _require_docker_command(record, name)
        _validate_save_load_nested_command(
            key,
            argv,
            tar_path=tar_path,
            invocation_id=invocation_id,
            invocation=invocation,
            imported_container=imported_container,
        )

    repeated_smoke = _require_mapping(
        proof.get("repeated_smoke"), "save/load repeated smoke"
    )
    imported = _validate_api_smoke_proof(
        repeated_smoke.get("api_proof"),
        "imported API smoke",
        expected_container=imported_container,
        expected_image=invocation.get("imported_image"),
    )
    _validate_independent_api_smokes(primary_api_proof, imported)


def _validate_save_load_failure_command(
    payload: Mapping[str, object], phase: Mapping[str, object]
) -> str:
    """Allow a failed command from a canonical save/load workflow stage."""
    invocation_id, invocation = _validate_invocation(payload)
    compose_project = invocation.get("compose_project")
    headless_image = invocation.get("headless_image")
    imported_image = invocation.get("imported_image")
    imported_container = f"{compose_project}-imported-judge-1"
    tar_path = (
        f"output/evidence/docker/live/{invocation_id}/headless-image.tar"
    )
    expected_label = f"{OWNERSHIP_LABEL_KEY}={invocation_id}"
    argv = _require_docker_command(phase, "save_load")
    exact_commands = {
        "image_save": [
            "docker",
            "image",
            "save",
            "--output",
            tar_path,
            headless_image,
        ],
        "image_load": ["docker", "image", "load", "--input", tar_path],
        "image_retag": [
            "docker",
            "image",
            "tag",
            headless_image,
            imported_image,
        ],
        "imported_container_create": [
            "docker",
            "container",
            "create",
            "--name",
            imported_container,
            "--label",
            expected_label,
            imported_image,
        ],
        "imported_container_start": [
            "docker",
            "container",
            "start",
            imported_container,
        ],
        "repeated_health": [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            imported_container,
        ],
    }
    for stage, expected in exact_commands.items():
        if argv == expected:
            return stage
    if (
        argv[:3] == ["docker", "exec", imported_container]
        and len(argv) >= 4
        and "docker" not in argv[3:]
    ):
        return "repeated_smoke"
    raise ValueError(
        "save_load failure must record a canonical workflow stage command"
    )


def _validate_save_load_failure_proof(
    payload: Mapping[str, object],
    phase: Mapping[str, object],
    failed_stage: str,
) -> None:
    """Require one truthful nested prefix matching the failed summary stage."""
    invocation_id, invocation = _validate_invocation(payload)
    proof = _require_mapping(payload.get("save_load_proof"), "save/load proof")
    _require_allowed_keys(proof, _SAVE_LOAD_PROOF_KEYS, "save/load proof")
    tar_path = _require_relative_path(proof.get("tar_path"), "save/load tar")
    expected_tar = (
        f"output/evidence/docker/live/{invocation_id}/headless-image.tar"
    )
    if tar_path != expected_tar:
        raise ValueError("save/load tar path is invalid")
    if proof.get("imported_image") != invocation.get("imported_image"):
        raise ValueError("save/load imported image is invalid")
    imported_container = (
        f"{invocation.get('compose_project')}-imported-judge-1"
    )
    if proof.get("imported_container") != imported_container:
        raise ValueError("save/load imported container is invalid")

    order = (
        "image_load",
        "image_retag",
        "imported_container_create",
        "imported_container_start",
        "repeated_health",
        "repeated_smoke",
    )
    failed_index = -1 if failed_stage == "image_save" else order.index(
        failed_stage
    )
    phase_argv = _command_tokens(phase, "save_load")
    for index, key in enumerate(order):
        name = f"save/load {key}"
        record = _require_mapping(proof.get(key), name)
        _validate_record(name, record)
        status = record.get("status")
        if index < failed_index:
            if status != "pass" or record.get("execution") == "api_result":
                raise ValueError("save/load failure predecessor must pass")
            argv = _require_docker_command(record, name)
            _validate_save_load_nested_command(
                key,
                argv,
                tar_path=tar_path,
                invocation_id=invocation_id,
                invocation=invocation,
                imported_container=imported_container,
            )
        elif index == failed_index:
            if (
                status != "fail"
                or record.get("execution", "command") != "command"
            ):
                raise ValueError("save/load failed nested stage is invalid")
            if (
                _command_tokens(record, name) != phase_argv
                or record.get("exit_code") != phase.get("exit_code")
            ):
                raise ValueError(
                    "save/load summary and nested failure mismatch"
                )
            _validate_save_load_nested_command(
                key,
                phase_argv,
                tar_path=tar_path,
                invocation_id=invocation_id,
                invocation=invocation,
                imported_container=imported_container,
            )
        else:
            if status != "not_run":
                raise ValueError(
                    "save/load failure successor must remain not_run"
                )
            _validate_untouched_not_run_phase(name, record)


def _canonical_resource_names(
    invocation: Mapping[str, object]
) -> dict[str, set[str]]:
    """Derive live-workflow resource names from the invocation identity."""
    compose_project = invocation.get("compose_project")
    headless_image = invocation.get("headless_image")
    gui_image = invocation.get("gui_image")
    imported_image = invocation.get("imported_image")
    values = (compose_project, headless_image, gui_image, imported_image)
    if not all(isinstance(value, str) and value for value in values):
        raise ValueError("invocation resource identities are invalid")
    return {
        "container": {
            f"{compose_project}-judge-1",
            f"{compose_project}-judge-gui-1",
            f"{compose_project}-imported-judge-1",
        },
        "network": {f"{compose_project}_default"},
        "volume": {
            f"{compose_project}_judge-output",
            f"{compose_project}_judge-gui-output",
        },
        "image": {headless_image, gui_image, imported_image},
    }


def _require_exact_names(
    resources: Mapping[str, object], name: str, canonical: set[str]
) -> set[str]:
    value = resources.get(name)
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"collision expected {name} is invalid")
    names = set(value)
    if len(names) != len(value) or names != canonical:
        raise ValueError(f"collision expected {name} are not canonical")
    return names


def _validate_pass_command_resource_identities(
    payload: Mapping[str, object],
    invocation: Mapping[str, object],
    invocation_id: str,
) -> dict[str, set[str]]:
    """Bind every quick-smoke/save-load command target to exact resources."""
    compose_project = invocation.get("compose_project")
    primary_container = f"{compose_project}-judge-1"
    gui_container = f"{compose_project}-judge-gui-1"
    imported_container = f"{compose_project}-imported-judge-1"
    headless_image = invocation.get("headless_image")
    gui_image = invocation.get("gui_image")
    imported_image = invocation.get("imported_image")
    headless_volume = f"{compose_project}_judge-output"
    gui_volume = f"{compose_project}_judge-gui-output"
    network = f"{compose_project}_default"

    headless_smoke = _require_mapping(
        payload.get("headless_smoke"), "headless smoke"
    )
    if headless_smoke.get("execution") != "api_result":
        smoke_argv = _require_docker_command(headless_smoke, "headless smoke")
        if _require_option_value(smoke_argv, "exec", "headless smoke") != (
            primary_container
        ):
            raise ValueError("headless smoke container is not canonical")

    headless_health = _require_mapping(
        payload.get("headless_health"), "headless health"
    )
    health_argv = _require_docker_command(headless_health, "headless health")
    if health_argv[-1] != primary_container:
        raise ValueError("headless health container is not canonical")

    save_load = _require_mapping(payload.get("save_load"), "save/load")
    save_argv = _require_docker_command(save_load, "save/load")
    if save_argv[-1] != headless_image:
        raise ValueError("save/load image is not canonical")

    proof = _require_mapping(payload.get("save_load_proof"), "save/load proof")
    image_retag = _require_mapping(
        proof.get("image_retag"), "save/load image retag"
    )
    retag_argv = _require_docker_command(image_retag, "save/load image retag")
    if retag_argv[-2:] != [headless_image, imported_image]:
        raise ValueError("save/load retag image is not canonical")

    create = _require_mapping(
        proof.get("imported_container_create"), "save/load imported container"
    )
    create_argv = _require_docker_command(
        create, "save/load imported container"
    )
    expected_label = f"{OWNERSHIP_LABEL_KEY}={invocation_id}"
    label_value = _require_option_value(
        create_argv, "--label", "save/load imported container"
    )
    if label_value != expected_label:
        raise ValueError("save/load imported container label is invalid")
    container_name = _require_option_value(
        create_argv, "--name", "save/load imported container"
    )
    if (
        container_name != imported_container
        or create_argv[-1] != imported_image
    ):
        raise ValueError("save/load imported container is not canonical")

    start = _require_mapping(
        proof.get("imported_container_start"),
        "save/load imported container start",
    )
    start_argv = _require_docker_command(
        start, "save/load imported container start"
    )
    if start_argv != [
        "docker",
        "container",
        "start",
        imported_container,
    ]:
        raise ValueError("save/load imported container start is not canonical")

    repeated_health = _require_mapping(
        proof.get("repeated_health"), "save/load repeated health"
    )
    repeated_health_argv = _require_docker_command(
        repeated_health, "save/load repeated health"
    )
    if repeated_health_argv[-1] != imported_container:
        raise ValueError(
            "save/load repeated health container is not canonical"
        )

    repeated_smoke = _require_mapping(
        proof.get("repeated_smoke"), "save/load repeated smoke"
    )
    if repeated_smoke.get("execution") != "api_result":
        repeated_smoke_argv = _require_docker_command(
            repeated_smoke, "save/load repeated smoke"
        )
        if _require_option_value(
            repeated_smoke_argv, "exec", "save/load repeated smoke"
        ) != imported_container:
            raise ValueError(
                "save/load repeated smoke container is not canonical"
            )

    required_owned = {
        "container": {primary_container, imported_container},
        "network": {network},
        "volume": {headless_volume},
        "image": {headless_image, imported_image},
    }

    gui_build = _require_mapping(payload.get("gui_build"), "gui build")
    if gui_build.get("status") == "pass":
        gui_build_argv = _require_docker_command(gui_build, "gui build")
        if len(gui_build_argv) < 2 or gui_build_argv[1] != "compose":
            gui_tag = _require_option_value(gui_build_argv, "-t", "gui build")
            if gui_tag != gui_image:
                raise ValueError("GUI image is not canonical")
            expected_label = f"{OWNERSHIP_LABEL_KEY}={invocation_id}"
            if (
                _require_unique_label(
                    gui_build_argv, OWNERSHIP_LABEL_KEY, "gui build"
                )
                != expected_label
            ):
                raise ValueError("GUI label does not match the invocation")
        required_owned["image"].add(gui_image)

    gui_smoke = _require_mapping(payload.get("gui_smoke"), "gui smoke")
    if gui_smoke.get("status") == "pass":
        if gui_smoke.get("execution") != "api_result":
            gui_smoke_argv = _require_docker_command(
                gui_smoke, "gui smoke"
            )
            if "exec" in gui_smoke_argv:
                gui_target = _require_option_value(
                    gui_smoke_argv, "exec", "gui smoke"
                )
            else:
                gui_target = gui_smoke_argv[-1]
            if gui_target != gui_container:
                raise ValueError("GUI container is not canonical")
        required_owned["container"].add(gui_container)
        required_owned["volume"].add(gui_volume)
        required_owned["image"].add(gui_image)

    return required_owned


def _validate_owned_inventory_list(
    value: object,
    name: str,
    invocation_id: str,
    canonical_names: Mapping[str, set[str]],
) -> dict[str, set[str]]:
    """Validate one current-label owned-resource inventory as a set."""
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    owned_names = {kind: set() for kind in canonical_names}
    for index, candidate in enumerate(value):
        record = _require_mapping(candidate, f"{name} resource {index}")
        _require_allowed_keys(
            record, _OWNED_RESOURCE_ENTRY_KEYS, f"{name} resource {index}"
        )
        kind = record.get("kind")
        resource_name = record.get("name")
        if (
            kind not in canonical_names
            or resource_name not in canonical_names[kind]
        ):
            raise ValueError(
                "owned resource name is not an exact expected name"
            )
        labels = _require_mapping(
            record.get("labels"), "owned resource labels"
        )
        _require_allowed_keys(
            labels, _OWNED_RESOURCE_LABEL_KEYS, "owned resource labels"
        )
        if labels.get(OWNERSHIP_LABEL_KEY) != invocation_id:
            raise ValueError(
                "owned resource lacks the current invocation label"
            )
        if resource_name in owned_names[kind]:
            raise ValueError("owned resource inventory contains duplicates")
        owned_names[kind].add(resource_name)
    return owned_names


def _inventory_identities(
    resources: Mapping[str, set[str]],
) -> set[tuple[str, str]]:
    return {
        (kind, resource_name)
        for kind, names in resources.items()
        for resource_name in names
    }


def _validate_cleanup_action_failure_proof(
    action: Mapping[str, object],
    execution: str,
    invocation_id: str,
) -> None:
    proof = _require_mapping(
        action.get("failure_proof"), "cleanup action proof"
    )
    if execution == "safety_refusal":
        _require_allowed_keys(
            proof, _SAFETY_REFUSAL_PROOF_KEYS, "cleanup action refusal proof"
        )
        if proof.get("kind") != "cleanup_ownership_refusal":
            raise ValueError("cleanup action refusal kind is invalid")
        if (
            proof.get("resource_kind") != action.get("resource_kind")
            or proof.get("resource_name") != action.get("resource_name")
        ):
            raise ValueError("cleanup action refusal resource is mismatched")
        required_label = _require_mapping(
            proof.get("required_label"), "cleanup action refusal label"
        )
        _require_allowed_keys(
            required_label,
            _OWNERSHIP_LABEL_KEYS,
            "cleanup action refusal label",
        )
        if (
            required_label.get("key") != OWNERSHIP_LABEL_KEY
            or required_label.get("value") != invocation_id
        ):
            raise ValueError("cleanup action refusal label is invalid")
        if (
            proof.get("observed_ownership")
            not in _OBSERVED_OWNERSHIP_RESULTS
        ):
            raise ValueError("cleanup action refusal observation is invalid")
        return
    _require_allowed_keys(
        proof, _INTERRUPTION_PROOF_KEYS, "cleanup action interruption proof"
    )
    if (
        proof.get("kind") != "interruption"
        or proof.get("interruption_kind") not in _INTERRUPTION_KINDS
        or proof.get("phase") != "cleanup"
    ):
        raise ValueError("cleanup action interruption proof is invalid")


def _validate_cleanup_evidence(
    payload: Mapping[str, object],
    invocation_id: str,
    invocation: Mapping[str, object],
) -> dict[str, set[str]]:
    """Close the cleanup action ledger against before/after inventories."""
    canonical_names = _canonical_resource_names(invocation)
    owned = _require_mapping(payload.get("owned_resources"), "owned resources")
    _require_allowed_keys(owned, _OWNED_RESOURCE_KEYS, "owned resources")
    before_names = _validate_owned_inventory_list(
        owned.get("before_cleanup"),
        "before cleanup",
        invocation_id,
        canonical_names,
    )
    after_names = _validate_owned_inventory_list(
        owned.get("after_cleanup"),
        "after cleanup inventory",
        invocation_id,
        canonical_names,
    )
    before = _inventory_identities(before_names)
    after = _inventory_identities(after_names)
    if not after.issubset(before):
        raise ValueError(
            "after-cleanup inventory must be a subset of before-cleanup"
        )

    actions_value = owned.get("cleanup_actions")
    if not isinstance(actions_value, list):
        raise ValueError("cleanup actions must be a list")
    actions: dict[tuple[str, str], Mapping[str, object]] = {}
    successes: set[tuple[str, str]] = set()
    failures: list[Mapping[str, object]] = []
    for index, candidate in enumerate(actions_value):
        action = _require_mapping(candidate, f"cleanup action {index}")
        _require_allowed_keys(
            action, _CLEANUP_ACTION_KEYS, f"cleanup action {index}"
        )
        kind = action.get("resource_kind")
        resource_name = action.get("resource_name")
        if (
            kind not in canonical_names
            or resource_name not in canonical_names[kind]
        ):
            raise ValueError("cleanup action resource is not canonical")
        identity = (kind, resource_name)
        if identity in actions:
            raise ValueError("cleanup action identities must be unique")
        actions[identity] = action
        required_label = _require_mapping(
            action.get("required_label"), "cleanup action required label"
        )
        _require_allowed_keys(
            required_label,
            _OWNERSHIP_LABEL_KEYS,
            "cleanup action required label",
        )
        if (
            required_label.get("key") != OWNERSHIP_LABEL_KEY
            or required_label.get("value") != invocation_id
        ):
            raise ValueError("cleanup action label does not match invocation")
        argv = action.get("argv")
        if not isinstance(argv, list) or not all(
            isinstance(item, str) for item in argv
        ):
            raise ValueError("cleanup action argv must be a string list")
        exit_code = action.get("exit_code")
        _require_sha256(action.get("stdout_sha256"), "cleanup action stdout")
        _require_sha256(action.get("stderr_sha256"), "cleanup action stderr")
        execution = action.get("execution")
        if execution == "command":
            if isinstance(exit_code, bool) or not isinstance(exit_code, int):
                raise ValueError(
                    "cleanup action exit code must be an exact integer"
                )
            expected_argv = ["docker", kind, "rm", resource_name]
            if argv != expected_argv:
                raise ValueError(
                    "cleanup action must remove one exact resource"
                )
            if "failure_proof" in action:
                raise ValueError(
                    "cleanup command action cannot contain failure proof"
                )
            if identity not in before:
                raise ValueError(
                    "cleanup command action must target owned "
                    "before-cleanup inventory"
                )
            if exit_code == 0:
                successes.add(identity)
            else:
                failures.append(action)
        elif execution in {"safety_refusal", "interruption"}:
            if argv or exit_code is not None:
                raise ValueError(
                    "cleanup non-command action cannot claim a command"
                )
            if (
                action.get("stdout_sha256") != _EMPTY_STREAM_SHA256
                or action.get("stderr_sha256") != _EMPTY_STREAM_SHA256
            ):
                raise ValueError(
                    "cleanup non-command action must have empty streams"
                )
            _validate_cleanup_action_failure_proof(
                action, execution, invocation_id
            )
            if execution == "safety_refusal":
                if identity in before or identity in after:
                    raise ValueError(
                        "cleanup refusal target cannot be current-label owned"
                    )
            elif identity not in before or identity not in after:
                raise ValueError(
                    "cleanup interruption target must remain owned"
                )
            failures.append(action)
        else:
            raise ValueError("cleanup action execution is invalid")

    if before.difference(after) != successes:
        raise ValueError("cleanup inventory does not match successful actions")
    cleanup = _require_mapping(payload.get("cleanup"), "cleanup")
    cleanup_status = cleanup.get("status")
    cleanup_execution = cleanup.get("execution", "command")
    if cleanup_status == "not_run":
        if before or after or actions:
            raise ValueError(
                "cleanup not_run requires empty inventories and ledger"
            )
        return before_names
    if cleanup_status == "pass":
        if after or set(actions) != before or failures:
            raise ValueError(
                "cleanup pass requires complete successful actions"
            )
        matching = [
            action
            for action in actions.values()
            if action.get("argv") == cleanup.get("argv")
            and action.get("exit_code") == cleanup.get("exit_code")
        ]
        if cleanup_execution != "command" or not matching:
            raise ValueError(
                "cleanup pass summary is not in the action ledger"
            )
        return before_names
    if cleanup_status != "fail" or len(failures) != 1:
        raise ValueError("cleanup fail requires one truthful failed action")
    failed_action = failures[0]
    if failed_action is not actions_value[-1]:
        raise ValueError(
            "cleanup failure action must be the final ledger entry"
        )
    if failed_action.get("execution") != cleanup_execution:
        raise ValueError(
            "cleanup failure execution mismatches the action ledger"
        )
    if cleanup_execution == "command":
        if not all(
            failed_action.get(field) == cleanup.get(field)
            for field in (
                "argv",
                "exit_code",
                "stdout_sha256",
                "stderr_sha256",
            )
        ):
            raise ValueError(
                "cleanup failed command mismatches the action ledger"
            )
    elif failed_action.get("failure_proof") != cleanup.get("failure_proof"):
        raise ValueError("cleanup failure proof mismatches the action ledger")
    return before_names


def _validate_resource_inventories(
    payload: Mapping[str, object],
    invocation_id: str,
    invocation: Mapping[str, object],
) -> None:
    collisions = _require_mapping(
        payload.get("name_collisions"), "name collisions"
    )
    _require_allowed_keys(collisions, _COLLISION_KEYS, "name collisions")
    before = collisions.get("before")
    if not isinstance(before, list) or before:
        raise ValueError("pass evidence requires an empty collision inventory")
    expected = _require_mapping(
        collisions.get("expected_resources"), "collision expected resources"
    )
    _require_allowed_keys(
        expected, _EXPECTED_RESOURCE_KEYS, "collision expected resources"
    )
    compose_project = invocation.get("compose_project")
    if expected.get("compose_project") != compose_project:
        raise ValueError("collision expected compose project is invalid")
    canonical_names = _canonical_resource_names(invocation)
    _require_exact_names(
        expected, "containers", canonical_names["container"]
    )
    _require_exact_names(expected, "networks", canonical_names["network"])
    _require_exact_names(expected, "volumes", canonical_names["volume"])
    _require_exact_names(expected, "images", canonical_names["image"])
    required_owned = _validate_pass_command_resource_identities(
        payload, invocation, invocation_id
    )

    owned_names = _validate_cleanup_evidence(
        payload, invocation_id, invocation
    )
    if not any(owned_names.values()):
        raise ValueError("pass evidence requires an owned-resource inventory")
    for kind, names in required_owned.items():
        if owned_names[kind] != names:
            raise ValueError("owned resource proof is incomplete")


def _validate_exported_evidence(
    payload: Mapping[str, object], invocation_id: str
) -> list[Mapping[str, object]]:
    exported = _require_mapping(
        payload.get("exported_evidence"), "exported evidence"
    )
    _require_allowed_keys(
        exported, _EXPORTED_EVIDENCE_KEYS, "exported evidence"
    )
    if _require_status(exported.get("status"), "exported evidence") != "pass":
        raise ValueError("pass evidence requires exported evidence")
    expected_path = f"output/evidence/docker/live/{invocation_id}"
    exported_path = _require_relative_path(
        exported.get("path"), "exported evidence"
    )
    if exported_path != expected_path:
        raise ValueError("exported evidence path is invalid")
    contents = exported.get("contents")
    if not isinstance(contents, list) or not contents:
        raise ValueError("exported evidence requires content hash proof")
    validated: list[Mapping[str, object]] = []
    for index, item in enumerate(contents):
        entry = _require_mapping(item, f"exported evidence content {index}")
        _require_allowed_keys(
            entry, _EXPORTED_CONTENT_KEYS, f"exported evidence content {index}"
        )
        _require_relative_path(
            entry.get("path"), "exported evidence content"
        )
        _require_sha256(entry.get("sha256"), "exported evidence content")
        if "byte_length" in entry:
            byte_length = entry.get("byte_length")
            if (
                isinstance(byte_length, bool)
                or not isinstance(byte_length, int)
                or byte_length <= 0
            ):
                raise ValueError(
                    "exported evidence byte length must be positive"
                )
        validated.append(entry)
    return validated


def _validate_gui_frame_proof(payload: Mapping[str, object]) -> None:
    """Bind a GUI API result to advancing exported PNG frame evidence."""
    gui_build = _require_mapping(payload.get("gui_build"), "gui_build")
    gui_smoke = _require_mapping(payload.get("gui_smoke"), "gui_smoke")
    gui_passed = (
        gui_build.get("status") == "pass"
        and gui_smoke.get("status") == "pass"
    )
    has_proof = "gui_frame_proof" in payload
    if not gui_passed:
        if has_proof:
            raise ValueError("GUI frame proof requires a complete GUI pass")
        return
    if gui_smoke.get("execution") != "api_result":
        raise ValueError("GUI frame proof requires a GUI API result")
    if not has_proof:
        raise ValueError("GUI frame proof is required for a GUI pass")

    invocation_id, invocation = _validate_invocation(payload)
    compose_project = invocation.get("compose_project")
    expected_container = f"{compose_project}-judge-gui-1"
    expected_image = invocation.get("gui_image")
    api_proof = _require_mapping(
        gui_smoke.get("api_proof"), "GUI API smoke proof"
    )
    proof = _require_mapping(
        payload.get("gui_frame_proof"), "GUI frame proof"
    )
    _require_allowed_keys(proof, _GUI_FRAME_PROOF_KEYS, "GUI frame proof")
    if proof.get("run_id") != api_proof.get("run_id"):
        raise ValueError("GUI frame proof run ID does not match")
    if proof.get("container") != expected_container:
        raise ValueError("GUI frame proof container is invalid")
    if proof.get("image") != expected_image:
        raise ValueError("GUI frame proof image is invalid")

    frames = proof.get("frames")
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("GUI frame proof requires at least two frames")
    frame_links: list[dict[str, object]] = []
    paths: set[str] = set()
    previous_sequence: int | None = None
    previous_time: int | float | None = None
    for index, candidate in enumerate(frames):
        frame = _require_mapping(candidate, f"GUI frame {index}")
        _require_allowed_keys(frame, _GUI_FRAME_KEYS, f"GUI frame {index}")
        path = _require_canonical_relative_path(
            frame.get("path"), f"GUI frame {index}"
        )
        windows_path = PureWindowsPath(path)
        if (
            path == "."
            or windows_path.drive
            or "\\" in path
            or not path.endswith(".png")
        ):
            raise ValueError("GUI frame path must be a safe relative PNG")
        identity = _portable_path_identity(path)
        if identity in paths:
            raise ValueError("GUI frame paths must be unique")
        paths.add(identity)

        byte_length = frame.get("byte_length")
        if (
            isinstance(byte_length, bool)
            or not isinstance(byte_length, int)
            or byte_length <= 0
        ):
            raise ValueError("GUI frame byte length must be positive")
        digest = frame.get("sha256")
        _require_sha256(digest, f"GUI frame {index}")
        sequence = frame.get("sequence")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 0
        ):
            raise ValueError("GUI frame sequence must be nonnegative")
        simulation_time = frame.get("simulation_time")
        if (
            isinstance(simulation_time, bool)
            or not isinstance(simulation_time, (int, float))
            or simulation_time < 0
        ):
            raise ValueError("GUI frame simulation time is invalid")
        try:
            finite_time = math.isfinite(simulation_time)
        except OverflowError:
            finite_time = False
        if not finite_time:
            raise ValueError("GUI frame simulation time must be finite")
        if previous_sequence is not None and sequence <= previous_sequence:
            raise ValueError("GUI frame sequence must strictly increase")
        if (
            previous_time is not None
            and simulation_time <= previous_time
        ):
            raise ValueError(
                "GUI frame simulation time must strictly increase"
            )
        previous_sequence = sequence
        previous_time = simulation_time
        frame_links.append(
            {"path": path, "sha256": digest, "byte_length": byte_length}
        )

    exported = _validate_exported_evidence(payload, invocation_id)
    exported_pngs: list[dict[str, object]] = []
    exported_png_paths: set[str] = set()
    for entry in exported:
        raw_path = entry.get("path")
        if not isinstance(raw_path, str) or not raw_path.lower().endswith(
            ".png"
        ):
            continue
        path = _require_canonical_relative_path(
            raw_path, "exported GUI PNG entry"
        )
        if not path.endswith(".png") or "byte_length" not in entry:
            raise ValueError("exported GUI PNG entry is invalid")
        identity = _portable_path_identity(path)
        if identity in exported_png_paths:
            raise ValueError("exported GUI PNG paths must be unique")
        exported_png_paths.add(identity)
        exported_pngs.append(
            {
                "path": path,
                "sha256": entry.get("sha256"),
                "byte_length": entry.get("byte_length"),
            }
        )
    if exported_pngs != frame_links:
        raise ValueError("GUI frame proof does not match exported PNG order")


def _validate_pass_requirements(payload: Mapping[str, object]) -> None:
    if payload.get("reason") != LIVE_PASS_REASON:
        raise ValueError(
            "pass evidence reason must be live_verification_complete"
        )
    platform_data = _require_mapping(payload.get("platform"), "platform")
    normalized_os = _normalized_platform_value(
        str(platform_data.get("os")), architecture=False
    )
    normalized_architecture = _normalized_platform_value(
        str(platform_data.get("architecture")), architecture=True
    )
    if (
        normalized_os != TARGET_PLATFORM_OS
        or normalized_architecture != TARGET_PLATFORM_ARCHITECTURE
    ):
        raise ValueError("pass evidence must target linux/amd64")

    for name in ("cli", "daemon", "static_contract", *HEADLESS_PASS_PHASES):
        record = _require_pass_record(payload, name)
        if name in PHASES:
            _validate_phase_command(name, record)
    _require_cli_version_record(payload)
    _require_daemon_info_record(payload)

    for name in ("gui_build", "gui_smoke"):
        record = _require_mapping(payload.get(name), name)
        if record.get("status") == "fail":
            raise ValueError(f"pass evidence cannot include failed {name}")
        if record.get("status") == "pass":
            _require_pass_record(payload, name)
            if record.get("execution") != "api_result":
                _validate_phase_command(name, record)

    invocation_id, invocation = _validate_invocation(payload)
    _validate_pass_build_projects(payload, invocation)
    gui_scope = _validate_static_contract_scope(payload, invocation)
    render_facts = _validate_render_command(
        payload, invocation, gui_scope=gui_scope
    )
    _validate_render_facts(
        render_facts,
        invocation_id,
        invocation,
        gui_scope=gui_scope,
    )
    primary_api_proof = _validate_quick_smoke(payload, invocation)
    _validate_save_load_proof(
        payload, invocation_id, invocation, primary_api_proof
    )
    _validate_resource_inventories(payload, invocation_id, invocation)
    _validate_exported_evidence(payload, invocation_id)


def _validate_failed_phase(
    payload: Mapping[str, object], phase_name: str
) -> None:
    """Validate one selected failure using its execution variant."""
    phase = _require_mapping(payload.get(phase_name), phase_name)
    if phase.get("status") != "fail":
        raise ValueError(
            "fail evidence reason does not match the failed phase"
        )
    if phase.get("execution") == "safety_refusal":
        invocation_id, invocation = _validate_invocation(payload)
        proof = _require_mapping(
            phase.get("failure_proof"), "safety refusal proof"
        )
        resource_kind = proof.get("resource_kind")
        canonical_names = _canonical_resource_names(invocation)
        if proof.get("resource_name") not in canonical_names[resource_kind]:
            raise ValueError("safety refusal resource is not canonical")
        required_label = _require_mapping(
            proof.get("required_label"), "safety refusal required label"
        )
        if required_label.get("value") != invocation_id:
            raise ValueError("safety refusal label does not match invocation")
        return
    if phase.get("execution") == "interruption":
        return
    _require_docker_command(phase, phase_name)
    if phase_name == "save_load":
        failed_stage = _validate_save_load_failure_command(payload, phase)
        _validate_save_load_failure_proof(payload, phase, failed_stage)
    else:
        _validate_phase_command(phase_name, phase)
        if phase_name != "cleanup":
            _validate_phase_command_identity(payload, phase_name, phase)
    exit_code = phase.get("exit_code")
    if (
        isinstance(exit_code, bool)
        or not isinstance(exit_code, int)
        or exit_code == 0
    ):
        raise ValueError("fail evidence requires a nonzero failed phase exit")


def _validate_successful_failure_prefix_phase(
    payload: Mapping[str, object], phase_name: str
) -> None:
    """Retain deep validation for each reached predecessor of a failure."""
    record = _require_pass_record(payload, phase_name)
    _validate_phase_command(phase_name, record)
    if phase_name not in {"save_load", "headless_smoke", "gui_smoke"}:
        _validate_phase_command_identity(payload, phase_name, record)
    if phase_name not in {"headless_smoke", "save_load"}:
        return
    invocation_id, invocation = _validate_invocation(payload)
    primary_api_proof = _validate_quick_smoke(payload, invocation)
    if phase_name == "save_load":
        _validate_save_load_proof(
            payload, invocation_id, invocation, primary_api_proof
        )


def _validate_fail_requirements(payload: Mapping[str, object]) -> None:
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.endswith("_failed"):
        raise ValueError("fail evidence reason must identify the failed phase")
    phase_name = reason[: -len("_failed")]
    if phase_name not in PHASES:
        raise ValueError("fail evidence reason names an unknown phase")
    _require_cli_version_record(payload)
    _require_daemon_info_record(payload)
    invocation_id, invocation = _validate_invocation(payload)

    if phase_name == "cleanup":
        seen_not_run = False
        for name in NON_CLEANUP_PHASES:
            status = _require_mapping(payload.get(name), name).get("status")
            if status == "fail":
                raise ValueError(
                    "cleanup-only failure cannot hide a primary failure"
                )
            if status == "not_run":
                seen_not_run = True
                continue
            if status != "pass" or seen_not_run:
                raise ValueError(
                    "cleanup-only failure has an invalid phase prefix"
                )
            _validate_successful_failure_prefix_phase(payload, name)
        _validate_failed_phase(payload, "cleanup")
        _validate_cleanup_evidence(payload, invocation_id, invocation)
        return

    primary_index = NON_CLEANUP_PHASES.index(phase_name)
    for index, name in enumerate(NON_CLEANUP_PHASES):
        status = _require_mapping(payload.get(name), name).get("status")
        if index < primary_index:
            if status != "pass":
                raise ValueError("failure predecessor phase must pass")
            _validate_successful_failure_prefix_phase(payload, name)
        elif index == primary_index:
            _validate_failed_phase(payload, name)
        elif status != "not_run":
            raise ValueError("failure successor phase must remain not_run")

    cleanup_status = _require_mapping(
        payload.get("cleanup"), "cleanup"
    ).get("status")
    if cleanup_status == "pass":
        cleanup = _require_pass_record(payload, "cleanup")
        _validate_phase_command("cleanup", cleanup)
    elif cleanup_status == "fail":
        _validate_failed_phase(payload, "cleanup")
    elif cleanup_status != "not_run":
        raise ValueError("cleanup status is invalid")
    _validate_cleanup_evidence(payload, invocation_id, invocation)


def _validate_not_run_requirements(payload: Mapping[str, object]) -> None:
    reason = payload.get("reason")
    if reason not in REASONS:
        raise ValueError("not_run evidence reason is invalid")
    phase_records = {
        name: _require_mapping(payload.get(name), name) for name in PHASES
    }
    if any(
        record.get("status") != "not_run"
        for record in phase_records.values()
    ):
        raise ValueError("not_run evidence cannot claim a live phase")
    cli = _require_mapping(payload.get("cli"), "cli")
    daemon = _require_mapping(payload.get("daemon"), "daemon")
    cli_status = cli.get("status")
    daemon_status = daemon.get("status")
    allowed = {
        "docker_cli_unavailable": ("not_run", "not_run"),
        "docker_daemon_unavailable": ("pass", "not_run"),
        "live_verification_not_run": ("pass", "pass"),
    }
    if (cli_status, daemon_status) != allowed[reason]:
        raise ValueError(f"{reason} capability classification is inconsistent")
    cli_argv = _command_tokens(cli, "cli")
    daemon_argv = _command_tokens(daemon, "daemon")
    expected_cli = ["docker", "--version"]
    expected_daemon = [
        "docker",
        "info",
        "--format",
        "{{json .ServerVersion}}",
    ]

    if reason == "docker_cli_unavailable":
        if cli_argv and cli_argv != expected_cli:
            raise ValueError("cli unavailable evidence has an invalid query")
        if not cli_argv and cli.get("exit_code") is not None:
            raise ValueError(
                "cli unavailable evidence has an unrecorded query"
            )
        if cli.get("exit_code") == 0:
            raise ValueError(
                "cli unavailable evidence cannot have a successful query"
            )
        if daemon_argv or daemon.get("exit_code") is not None:
            raise ValueError(
                "daemon must remain untouched when the CLI is unavailable"
            )
        return

    if reason == "docker_daemon_unavailable":
        _require_cli_version_record(payload)
        if daemon_argv != expected_daemon:
            raise ValueError(
                "daemon unavailable evidence must record a Docker info query"
            )
        if daemon.get("exit_code") == 0:
            raise ValueError(
                "daemon unavailable evidence cannot have a successful query"
            )
        return

    _require_cli_version_record(payload)
    _require_daemon_info_record(payload)


def new_evidence() -> dict[str, object]:
    """Create the initial Docker evidence document."""
    checked_at = _timestamp()

    def not_run(detail: str) -> dict[str, object]:
        return _record("not_run", detail, timestamp=checked_at)

    payload: dict[str, object] = {
        "schema": SCHEMA,
        "checked_at": checked_at,
        "status": "not_run",
        # The initial builder is deliberately conservative. ``detect`` changes
        # this to a daemon-unavailable or live-not-run state only after each
        # respective capability query has succeeded.
        "reason": "docker_cli_unavailable",
        "platform": {
            "os": platform.system(),
            "architecture": platform.machine(),
        },
        "cli": not_run("Docker CLI capability has not been confirmed"),
        "daemon": not_run("Docker daemon has not been checked"),
    }
    payload.update(
        {
            phase: not_run("Live Docker verification has not run")
            for phase in PHASES
        }
    )
    return payload


def run_command(argv: Sequence[str], cwd: Path) -> object:
    """Run an allowed read-only Docker capability command."""
    command = [str(item) for item in argv]
    if not (
        command == ["docker", "--version"]
        or command[:2] == ["docker", "version"]
        or command[:2] == ["docker", "info"]
    ):
        raise ValueError(
            "only read-only Docker version/info commands are allowed"
        )
    return subprocess.run(
        command,
        cwd=Path(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )


def detect(
    repo_root: Path,
    *,
    which: Callable[[str], str | None] | None = None,
    command_runner: CommandRunner | None = None,
    expected_root: Path | None = None,
) -> dict[str, object]:
    """Detect Docker capability without changing Docker state."""
    payload = new_evidence()
    root = validate_project_root(repo_root, expected_root=expected_root)
    cli_lookup = shutil.which if which is None else which
    runner = run_command if command_runner is None else command_runner
    if cli_lookup("docker") is None:
        payload["reason"] = "docker_cli_unavailable"
        payload["cli"] = _record("not_run", "Docker CLI unavailable")
        payload["daemon"] = _record("not_run", "Docker daemon not checked")
        validate_evidence(payload)
        return payload

    cli_command = ["docker", "--version"]
    cli_started_at = _timestamp()
    try:
        cli_result = runner(cli_command, root)
    except subprocess.TimeoutExpired as exc:
        cli_finished_at = _timestamp()
        payload["reason"] = "docker_cli_unavailable"
        payload["cli"] = _record(
            "not_run",
            "Docker CLI query timed out",
            argv=cli_command,
            stdout=_timeout_stream(exc, "stdout"),
            stderr=_timeout_stream(exc, "stderr"),
            started_at=cli_started_at,
            finished_at=cli_finished_at,
        )
        payload["daemon"] = _record("not_run", "Docker daemon not checked")
        validate_evidence(payload)
        return payload
    except OSError:
        cli_finished_at = _timestamp()
        payload["reason"] = "docker_cli_unavailable"
        payload["cli"] = _record(
            "not_run",
            "Docker CLI could not be queried",
            argv=cli_command,
            started_at=cli_started_at,
            finished_at=cli_finished_at,
        )
        payload["daemon"] = _record("not_run", "Docker daemon not checked")
        validate_evidence(payload)
        return payload

    cli_exit_code = getattr(cli_result, "returncode", 1)
    cli_stdout = getattr(cli_result, "stdout", "")
    cli_stderr = getattr(cli_result, "stderr", "")
    cli_finished_at = _timestamp()
    if cli_exit_code != 0:
        payload["reason"] = "docker_cli_unavailable"
        payload["cli"] = _record(
            "not_run",
            f"Docker CLI query exited {cli_exit_code}",
            argv=cli_command,
            exit_code=cli_exit_code,
            stdout=cli_stdout,
            stderr=cli_stderr,
            started_at=cli_started_at,
            finished_at=cli_finished_at,
        )
        payload["daemon"] = _record("not_run", "Docker daemon not checked")
        validate_evidence(payload)
        return payload

    payload["cli"] = _record(
        "pass",
        "Docker CLI detected",
        argv=cli_command,
        exit_code=cli_exit_code,
        stdout=cli_stdout,
        stderr=cli_stderr,
        version=_sanitized_version(cli_stdout, cli=True),
        started_at=cli_started_at,
        finished_at=cli_finished_at,
    )
    daemon_command = ["docker", "info", "--format", "{{json .ServerVersion}}"]
    daemon_started_at = _timestamp()
    try:
        daemon_result = runner(daemon_command, root)
    except subprocess.TimeoutExpired as exc:
        daemon_finished_at = _timestamp()
        payload["reason"] = "docker_daemon_unavailable"
        payload["daemon"] = _record(
            "not_run",
            "Docker daemon query timed out",
            argv=daemon_command,
            stdout=_timeout_stream(exc, "stdout"),
            stderr=_timeout_stream(exc, "stderr"),
            started_at=daemon_started_at,
            finished_at=daemon_finished_at,
        )
        validate_evidence(payload)
        return payload
    except OSError:
        daemon_result = None
    daemon_finished_at = _timestamp()
    if daemon_result is None:
        daemon_exit_code = None
        daemon_stdout = ""
        daemon_stderr = ""
    else:
        daemon_exit_code = getattr(daemon_result, "returncode", 1)
        daemon_stdout = getattr(daemon_result, "stdout", "")
        daemon_stderr = getattr(daemon_result, "stderr", "")
    if daemon_exit_code != 0:
        payload["reason"] = "docker_daemon_unavailable"
        payload["daemon"] = _record(
            "not_run",
            "Docker daemon unavailable",
            argv=daemon_command,
            exit_code=daemon_exit_code,
            stdout=daemon_stdout,
            stderr=daemon_stderr,
            started_at=daemon_started_at,
            finished_at=daemon_finished_at,
        )
        validate_evidence(payload)
        return payload

    payload["daemon"] = _record(
        "pass",
        "Docker daemon responded",
        argv=daemon_command,
        exit_code=daemon_exit_code,
        stdout=daemon_stdout,
        stderr=daemon_stderr,
        version=_sanitized_version(daemon_stdout, cli=False),
        started_at=daemon_started_at,
        finished_at=daemon_finished_at,
    )
    payload["reason"] = "live_verification_not_run"
    validate_evidence(payload)
    return payload


def validate_evidence(payload: object) -> None:
    """Reject malformed, unsafe, or unsupported evidence documents."""
    document = _require_mapping(payload, "Docker evidence")
    _require_allowed_keys(document, _EVIDENCE_KEYS, "Docker evidence")
    if document.get("schema") != SCHEMA:
        raise ValueError("invalid Docker evidence schema")
    _require_timestamp(document.get("checked_at"), "Docker evidence")
    status = _require_status(document.get("status"), "Docker evidence")
    reason = document.get("reason")
    if not isinstance(reason, str) or len(reason) > MAX_DETAIL_LENGTH:
        raise ValueError("Docker evidence reason is invalid")

    platform_data = _require_mapping(document.get("platform"), "platform")
    _require_allowed_keys(platform_data, _PLATFORM_KEYS, "platform")
    for name in ("os", "architecture"):
        value = platform_data.get(name)
        if not isinstance(value, str) or not value:
            raise ValueError(f"platform {name} is invalid")

    for name in ("cli", "daemon", *PHASES):
        _validate_record(name, document.get(name))
        if name in PHASES:
            record = _require_mapping(document.get(name), name)
            if record.get("status") == "not_run":
                _validate_untouched_not_run_phase(name, record)
    gui_smoke = _require_mapping(document.get("gui_smoke"), "gui_smoke")
    gui_build = _require_mapping(document.get("gui_build"), "gui_build")
    if (
        gui_smoke.get("status") == "pass"
        and gui_build.get("status") != "pass"
    ):
        raise ValueError("GUI smoke pass requires a GUI build pass")
    _reject_private_values(document)
    _validate_present_api_results(document)
    _validate_gui_frame_proof(document)
    if status == "pass":
        _validate_pass_requirements(document)
    else:
        _validate_nonpass_successful_build_claims(document)
        if status == "fail":
            _validate_fail_requirements(document)
        else:
            _validate_not_run_requirements(document)


def _is_reparse_point(path: Path) -> bool:
    """Return whether an existing path component redirects lookup."""
    try:
        junction_check = getattr(path, "is_junction", None)
        return path.is_symlink() or (
            callable(junction_check) and bool(junction_check())
        )
    except (OSError, RuntimeError) as exc:
        raise DockerStatusError(
            "repository root cannot inspect a reparse point: "
            f"{type(exc).__name__}"
        ) from exc


def _contains_reparse_point(path: Path) -> bool:
    """Inspect every existing component without resolving through a link."""
    try:
        absolute = Path(os.path.abspath(path))
        current = Path(absolute.anchor)
        for part in absolute.parts[1:]:
            current = current / part
            if _is_reparse_point(current):
                return True
    except (OSError, RuntimeError) as exc:
        raise DockerStatusError(
            f"repository root cannot inspect safely: {type(exc).__name__}"
        ) from exc
    return False


def expected_project_root() -> Path:
    """Return the canonical checkout root derived from this script."""
    try:
        return Path(__file__).resolve(strict=True).parents[2]
    except (OSError, RuntimeError) as exc:
        raise DockerStatusError(
            "expected repository root cannot be resolved safely: "
            f"{type(exc).__name__}"
        ) from exc


def validate_project_root(
    repo_root: Path, *, expected_root: Path | None = None
) -> Path:
    """Require exactly the canonical checkout, never a caller-selected root."""
    supplied = Path(repo_root)
    expected_input = (
        expected_project_root()
        if expected_root is None
        else Path(expected_root)
    )
    try:
        if _contains_reparse_point(supplied):
            raise DockerStatusError(
                "repository root cannot be a symlink or junction"
            )
        if _contains_reparse_point(expected_input):
            raise DockerStatusError(
                "expected repository root cannot be a reparse point"
            )
        root = supplied.resolve(strict=True)
        canonical_expected = expected_input.resolve(strict=True)
        if not root.is_dir() or not canonical_expected.is_dir():
            raise DockerStatusError(
                "repository root must be an existing directory"
            )
    except DockerStatusError:
        raise
    except (OSError, RuntimeError) as exc:
        raise DockerStatusError(
            f"repository root cannot be resolved safely: {type(exc).__name__}"
        ) from exc
    if root != canonical_expected:
        raise DockerStatusError("repository root does not match this checkout")
    return root


def resolve_protected_output_path(
    repo_root: Path,
    requested: Path,
    *,
    expected_root: Path | None = None,
) -> Path:
    """Resolve an output target while protecting immutable judge inputs."""
    try:
        root = validate_project_root(repo_root, expected_root=expected_root)
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
        archive = (root / SOURCE_ARCHIVE).resolve()
        official_data = (root / OFFICIAL_DATA_DIRECTORY).resolve()
    except (OSError, RuntimeError) as exc:
        raise DockerStatusError(
            f"output path cannot be resolved safely: {type(exc).__name__}"
        ) from exc
    if (
        candidate == archive
        or candidate == official_data
        or candidate.is_relative_to(official_data)
    ):
        raise DockerStatusError("output path targets protected judge input")
    return candidate


def write_evidence(output: Path, payload: object) -> None:
    """Atomically publish a validated Docker evidence document."""
    validate_evidence(payload)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(
    argv: Sequence[str] | None = None, *, expected_root: Path | None = None
) -> int:
    """Write current-host Docker capability evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/evidence/docker/docker-status.json"),
    )
    args = parser.parse_args(argv)
    try:
        root = validate_project_root(
            args.repo_root, expected_root=expected_root
        )
        output = resolve_protected_output_path(
            root, args.output, expected_root=root
        )
    except (DockerStatusError, OSError, ValueError) as exc:
        print(f"Docker evidence output rejected: {exc}", file=sys.stderr)
        return 2

    try:
        payload = detect(root, expected_root=root)
        validate_evidence(payload)
        write_evidence(output, payload)
    except (DockerStatusError, OSError, ValueError) as exc:
        print(f"Docker evidence unavailable: {exc}", file=sys.stderr)
        return 2

    status = payload["status"]
    reason = payload["reason"]
    print(json.dumps({"reason": reason, "status": status}, ensure_ascii=False))
    return 1 if status == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
