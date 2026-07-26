"""Create an offline source bundle with truthful Docker and machine evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".worktrees",
    "__pycache__",
    "output",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_files(root: Path, output_dir: Path):
    output_resolved = output_dir.resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if output_resolved in path.resolve().parents:
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        yield path, relative


def _second_machine_evidence(path: Path | None) -> dict:
    if path is None:
        return {
            "status": "not_run",
            "detail": "no independently supplied second-machine evidence",
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"machine", "timestamp", "commands"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"second-machine evidence missing: {sorted(missing)}")
    commands = payload["commands"]
    if not isinstance(commands, list) or not commands:
        raise ValueError("second-machine evidence commands must be non-empty")
    if any("exit_code" not in command for command in commands):
        raise ValueError("every second-machine command needs exit_code")
    return {
        "status": (
            "pass"
            if all(int(command["exit_code"]) == 0 for command in commands)
            else "fail"
        ),
        "evidence": payload,
    }


def _docker_evidence(output_dir: Path, image: str) -> tuple[dict, Path | None]:
    docker = shutil.which("docker")
    if docker is None:
        return {
            "status": "not_run",
            "detail": "Docker unavailable; image export not run",
        }, None
    inspect = subprocess.run(
        [docker, "image", "inspect", image, "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode:
        return {
            "status": "not_run",
            "detail": f"Docker image {image!r} is not available locally",
            "inspect_exit_code": inspect.returncode,
        }, None
    image_tar = output_dir / "ca-mp-ia-ib.tar"
    save_command = [docker, "save", image, "-o", str(image_tar)]
    saved = subprocess.run(
        save_command,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "status": "pass" if saved.returncode == 0 else "fail",
        "image": image,
        "digest": inspect.stdout.strip(),
        "save_command": save_command,
        "save_exit_code": saved.returncode,
        "stderr": saved.stderr.strip(),
    }, image_tar if saved.returncode == 0 else None


def package_offline(
    root: Path,
    output_dir: Path,
    *,
    image: str = "ca-mp:ia-ib",
    second_machine_evidence: Path | None = None,
) -> Path:
    """Package source, dependencies, hashes, and conditional Docker evidence."""
    root = Path(root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_archive = output_dir / "challenge-cup-source.zip"
    with zipfile.ZipFile(
        source_archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path, relative in _source_files(root, output_dir):
            archive.write(path, relative.as_posix())

    requirements_source = root / "requirements.txt"
    requirements_copy = output_dir / "requirements.txt"
    shutil.copy2(requirements_source, requirements_copy)
    docker, image_tar = _docker_evidence(output_dir, image)

    files = {
        "source_archive": {
            "path": source_archive.name,
            "sha256": _sha256(source_archive),
            "bytes": source_archive.stat().st_size,
        },
        "requirements": {
            "path": requirements_copy.name,
            "sha256": _sha256(requirements_copy),
            "bytes": requirements_copy.stat().st_size,
        },
    }
    if image_tar is not None:
        files["docker_image"] = {
            "path": image_tar.name,
            "sha256": _sha256(image_tar),
            "bytes": image_tar.stat().st_size,
        }

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "docker": docker,
        "second_machine": _second_machine_evidence(second_machine_evidence),
        "commands": {
            "load": "docker load -i ca-mp-ia-ib.tar",
            "run": (
                "docker run --rm -v ${PWD}/output:/app/output ca-mp:ia-ib "
                "--intersection 1 --algorithm fixed_time --steps 100 "
                "--output-dir /app/output/runs"
            ),
        },
    }
    manifest_path = output_dir / "offline_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--image", default="ca-mp:ia-ib")
    parser.add_argument("--second-machine-evidence", type=Path)
    args = parser.parse_args()
    path = package_offline(
        args.root,
        args.output_dir,
        image=args.image,
        second_machine_evidence=args.second_machine_evidence,
    )
    print(path)


if __name__ == "__main__":
    sys.exit(main())
