"""Collect portable release-environment evidence without changing sources."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Sequence


REQUIRED_SUMO_VERSION = "1.27.1"
SOURCE_ARCHIVE = "赛题资料.7z"
SOURCE_ARCHIVE_SHA256 = (
    "12a6f2fd69acbcbf38c286a84232c4be64000edaf06c61ff6d3b3e09f8995c0f"
)
PACKAGE_NAMES = (
    "fastapi",
    "numpy",
    "pandas",
    "scipy",
    "sumolib",
    "traci",
)
VALID_STATUSES = frozenset({"pass", "fail", "not_run"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command_output(command: Sequence[str], cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return (completed.stdout or completed.stderr).strip()


def _git_bytes(repo_root: Path, *args: str) -> bytes | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout


def _head_hash(repo_root: Path, raw_path: str) -> str | None:
    content = _git_bytes(repo_root, "show", f"HEAD:{raw_path}")
    return hashlib.sha256(content).hexdigest() if content is not None else None


def _untracked_files(repo_root: Path, raw_path: str) -> list[str]:
    output = _git_bytes(
        repo_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        "--",
        raw_path,
    )
    if output is None:
        return []
    return sorted(
        path
        for path in output.decode("utf-8", errors="surrogateescape").split("\0")
        if path
    )


def _relative_record(
    repo_root: Path,
    raw_path: str,
    git_status: str,
    *,
    role: str = "path",
    prefer_head: bool = False,
) -> dict[str, str]:
    normalized = Path(raw_path).as_posix()
    candidate = repo_root / Path(raw_path)
    digest = _head_hash(repo_root, raw_path) if prefer_head else None
    if digest is None and candidate.is_file():
        digest = _sha256(candidate)
    if digest is None:
        digest = "unavailable"
    return {
        "path": normalized,
        "git_status": git_status,
        "role": role,
        "sha256": digest,
    }


def collect_worktree_inventory(repo_root: Path) -> dict[str, object]:
    """Return relative identities and hashes for every changed source path."""
    repo_root = Path(repo_root).resolve()
    output = _git_bytes(repo_root, "status", "--porcelain=v1", "-z")
    if output is None:
        return {"git_available": False, "changed": [], "untracked": []}
    entries = output.decode("utf-8", errors="surrogateescape").split("\0")
    changed: list[dict[str, str]] = []
    untracked: list[dict[str, str]] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        raw_path = entry[3:]
        if status == "??":
            candidate = repo_root / Path(raw_path)
            if candidate.is_dir():
                for relative in _untracked_files(repo_root, raw_path):
                    untracked.append(
                        _relative_record(repo_root, relative, status)
                    )
            else:
                untracked.append(_relative_record(repo_root, raw_path, status))
            continue
        if "R" in status or "C" in status:
            source_path = entries[index] if index < len(entries) else ""
            index += 1
            if source_path:
                changed.append(
                    _relative_record(
                        repo_root,
                        source_path,
                        status,
                        role="source",
                        prefer_head=True,
                    )
                )
            changed.append(
                _relative_record(repo_root, raw_path, status, role="destination")
            )
            continue
        changed.append(
            _relative_record(
                repo_root,
                raw_path,
                status,
                prefer_head="D" in status,
            )
        )
    return {
        "git_available": True,
        "changed": sorted(changed, key=lambda item: (item["path"], item["role"])),
        "untracked": sorted(untracked, key=lambda item: item["path"]),
    }


def detect_sumo_version() -> str | None:
    output = _command_output(["sumo", "--version"], Path.cwd())
    if not output:
        return None
    first_line = output.splitlines()[0]
    parts = first_line.split()
    return parts[-1] if parts else None


def _package_versions() -> dict[str, str]:
    versions = {}
    for name in PACKAGE_NAMES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not_installed"
    return versions


def _git_commit(repo_root: Path) -> str:
    return _command_output(["git", "rev-parse", "HEAD"], repo_root) or "unknown"


def _archive_record(repo_root: Path) -> dict[str, object]:
    archive = repo_root / SOURCE_ARCHIVE
    if not archive.is_file():
        return {"path": SOURCE_ARCHIVE, "presence": "missing"}
    return {
        "path": SOURCE_ARCHIVE,
        "presence": "present",
        "size_bytes": archive.stat().st_size,
        "sha256": _sha256(archive),
    }


def collect_environment(repo_root: Path) -> dict[str, object]:
    """Collect reproducible environment facts without personal absolute paths."""
    repo_root = Path(repo_root).resolve()
    docker_available = shutil.which("docker") is not None
    return {
        "environment": {
            "python": {
                "version": ".".join(map(str, sys.version_info[:3])),
                "implementation": platform.python_implementation(),
            },
            "sumo": {"version": detect_sumo_version() or "not_installed"},
            "packages": _package_versions(),
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
            "git_commit": _git_commit(repo_root),
            "source_archive": _archive_record(repo_root),
            "docker": {
                "cli_available": docker_available,
                "status": "not_run",
                "detail": (
                    "CLI detected; live Docker validation has not run"
                    if docker_available
                    else "Docker CLI unavailable"
                ),
            },
        },
        "worktree_inventory": collect_worktree_inventory(repo_root),
    }


def _record(check: str, status: str, detail: str) -> dict[str, str]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid preflight status: {status}")
    return {"check": check, "status": status, "detail": detail}


def _writable_output(repo_root: Path) -> tuple[str, str]:
    output = repo_root / "output"
    try:
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output, delete=True):
            pass
    except OSError as exc:
        return "fail", f"output is not writable: {type(exc).__name__}"
    return "pass", "output is writable"


def _sumo_imports() -> tuple[str, str]:
    failures = []
    for name in ("traci", "sumolib"):
        try:
            importlib.import_module(name)
        except ImportError as exc:
            failures.append(f"{name}: {type(exc).__name__}")
    if failures:
        return "fail", "; ".join(failures)
    return "pass", "traci and sumolib import successfully"


def run_preflight(repo_root: Path) -> list[dict[str, str]]:
    """Run non-destructive native checks using pass/fail/not_run vocabulary."""
    repo_root = Path(repo_root).resolve()
    python_ok = sys.version_info >= (3, 10)
    sumo_version = detect_sumo_version()
    archive = _archive_record(repo_root)
    archive_hash = archive.get("sha256")
    writable_status, writable_detail = _writable_output(repo_root)
    import_status, import_detail = _sumo_imports()
    docker_available = shutil.which("docker") is not None
    return [
        _record(
            "python_version",
            "pass" if python_ok else "fail",
            f"Python {'.'.join(map(str, sys.version_info[:3]))}; requires >= 3.10",
        ),
        _record(
            "sumo_version",
            "pass" if sumo_version == REQUIRED_SUMO_VERSION else "fail",
            f"detected {sumo_version or 'none'}; requires {REQUIRED_SUMO_VERSION}",
        ),
        _record(
            "source_archive",
            "pass" if archive_hash == SOURCE_ARCHIVE_SHA256 else "fail",
            (
                f"SHA-256 {archive_hash}; expected {SOURCE_ARCHIVE_SHA256}"
                if archive_hash
                else f"missing; expected SHA-256 {SOURCE_ARCHIVE_SHA256}"
            ),
        ),
        _record("writable_output", writable_status, writable_detail),
        _record("sumo_python_imports", import_status, import_detail),
        _record(
            "docker_cli",
            "not_run",
            (
                "CLI detected; live Docker validation has not run"
                if docker_available
                else "Docker CLI unavailable"
            ),
        ),
    ]


def _json_safe(payload: object) -> object:
    if isinstance(payload, float) and not math.isfinite(payload):
        return None
    if isinstance(payload, dict):
        return {str(key): _json_safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_json_safe(value) for value in payload]
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/evidence/release-baseline/environment.json"),
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    output = args.output
    if not output.is_absolute():
        output = repo_root / output
    payload = collect_environment(repo_root)
    payload["preflight"] = run_preflight(repo_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            _json_safe(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, output)
    print(json.dumps(payload["preflight"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
