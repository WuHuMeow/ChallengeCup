"""Recoverable cleanup and allowlisted release copy (Task 21).

Safety contract:
- ``plan_cleanup`` only ever proposes stale *generated* artifacts; the
  protected judge inputs (``赛题资料.7z`` and ``data/intersection_data``) can
  never appear in a plan.
- ``apply_cleanup`` defaults to a recoverable quarantine (move, not delete)
  and never touches official sources.
- ``build_release_copy`` copies an explicit allowlist into a clean release
  candidate and records SHA-256 for every entry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

SOURCE_ARCHIVE = "赛题资料.7z"
OFFICIAL_DATA = Path("data") / "intersection_data"
PROTECTED_PATHS = (SOURCE_ARCHIVE, OFFICIAL_DATA)

# Stale generated artifacts, relative to the repository root.  Each entry is
# (relative path, reason).  Missing paths are skipped in plan/apply.
STALE_GENERATED_TARGETS: tuple[tuple[str, str], ...] = (
    ("output/tmp", "pytest temporary trees"),
    ("output/runs", "generated run artifacts"),
    ("output/cachetmp", "legacy cache directory"),
    ("web/test-results", "Playwright test artifacts"),
    ("web/playwright-report", "Playwright HTML report"),
    (".pytest_cache", "pytest cache"),
    ("output/quarantine", "previous quarantine rounds"),
)

# Release-copy allowlist: (relative path, kind).  Directories are copied
# recursively; single files are copied verbatim.
RELEASE_COPY_DIRECTORIES: tuple[str, ...] = (
    "algorithms",
    "api",
    "cloud",
    "config",
    "core",
    "engine",
    "experiments",
    "ml",
    "scenes",
    "scripts",
    "visualization",
    "data/intersection_data",
    "docs/release",
    "docs/api",
    "docs/guides",
    "docs/notes",
    "docs/pdf",
)
RELEASE_COPY_FILES: tuple[str, ...] = (
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "docker-compose.yml",
    ".dockerignore",
    ".gitignore",
    "docker/Dockerfile",
    "docker/Dockerfile.gui",
    "docker/README.md",
    "docker/requirements.in",
    "docker/requirements.lock",
    "docs/deployment.md",
    "docs/sumo_env_setup.md",
    "docs/interface.md",
    "docs/edge_mapping.md",
    "docs/migration_log.md",
    "docs/batch_validate_report.md",
    "docs/README.md",
    "output/README.md",
    "scripts/start_judge.ps1",
    "scripts/start_judge.bat",
)
RELEASE_COPY_BUILT_ASSETS = "api/static/dist"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_protected(relative: Path) -> bool:
    normalized = relative.as_posix()
    if normalized == SOURCE_ARCHIVE:
        return True
    return normalized == OFFICIAL_DATA.as_posix() or normalized.startswith(
        OFFICIAL_DATA.as_posix() + "/"
    )


@dataclass
class CleanupPlan:
    targets: list[dict[str, object]] = field(default_factory=list)

    @property
    def target_paths(self) -> list[Path]:
        return [Path(str(item["path"])) for item in self.targets]


@dataclass
class CleanupReport:
    mode: str
    moved: list[str] = field(default_factory=list)
    skipped_missing: list[str] = field(default_factory=list)
    quarantine_root: str | None = None


@dataclass
class ReleaseManifest:
    root: str
    entries: list[dict[str, object]] = field(default_factory=list)
    protected_inputs: dict[str, object] = field(default_factory=dict)
    generated_at: str = ""

    def to_json(self) -> str:
        return json.dumps(self.__dict__, ensure_ascii=False, indent=2, sort_keys=True)


def plan_cleanup(repo_root: Path) -> CleanupPlan:
    """Propose stale generated artifacts; never protected judge inputs."""
    repo_root = repo_root.resolve()
    plan = CleanupPlan()
    for relative, reason in STALE_GENERATED_TARGETS:
        path = repo_root / relative
        if not path.exists():
            continue
        if _is_protected(Path(relative)):
            raise ValueError(f"protected path leaked into cleanup plan: {relative}")
        plan.targets.append(
            {
                "path": relative,
                "reason": reason,
                "recoverable": True,
            }
        )
    return plan


def apply_cleanup(
    plan: CleanupPlan,
    repo_root: Path,
    *,
    mode: str = "quarantine",
) -> CleanupReport:
    """Move planned targets into a recoverable quarantine (never delete)."""
    if mode != "quarantine":
        raise ValueError("apply_cleanup only supports the recoverable quarantine mode")
    repo_root = repo_root.resolve()
    quarantine = repo_root / "output" / "quarantine" / time.strftime("%Y%m%d-%H%M%S")
    report = CleanupReport(mode=mode)
    for target in plan.target_paths:
        # Fail closed: the protection check must fire even for paths that do
        # not currently exist, so a crafted plan can never probe or race the
        # official inputs.
        if _is_protected(target):
            raise ValueError(f"refusing to quarantine protected input: {target}")
        source = repo_root / target
        if not source.exists():
            report.skipped_missing.append(target.as_posix())
            continue
        destination = quarantine / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        report.moved.append(target.as_posix())
    if report.moved:
        report.quarantine_root = quarantine.relative_to(repo_root).as_posix()
    return report


def build_release_copy(repo_root: Path, destination: Path) -> ReleaseManifest:
    """Copy only allowlisted files plus built assets into ``destination``."""
    repo_root = repo_root.resolve()
    destination = destination.resolve()
    # The destination may live under output/ (gitignored); what must never
    # happen is writing INTO a tree that the copier reads from.
    copied_roots = [repo_root / rel for rel in (*RELEASE_COPY_DIRECTORIES,)]
    copied_roots += [repo_root / rel for rel in RELEASE_COPY_FILES]
    copied_roots.append(repo_root / RELEASE_COPY_BUILT_ASSETS)
    copied_roots.append(repo_root / SOURCE_ARCHIVE)
    for source_root in copied_roots:
        if not source_root.exists():
            continue
        source_resolved = source_root.resolve()
        if destination == source_resolved or source_resolved in destination.parents:
            raise ValueError(
                f"release destination overlaps a copied source tree: {source_root}"
            )
    manifest = ReleaseManifest(
        root=repo_root.name,
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    if destination.exists():
        raise ValueError(f"release destination already exists: {destination}")
    destination.mkdir(parents=True)
    copied: set[str] = set()

    def copy_tree(source: Path, target: Path) -> None:
        for item in sorted(source.rglob("*")):
            if item.is_dir():
                continue
            relative = item.relative_to(source)
            final = target / relative
            final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, final)

    for relative in RELEASE_COPY_DIRECTORIES:
        source = repo_root / relative
        if source.is_dir():
            copy_tree(source, destination / relative)
    for relative in RELEASE_COPY_FILES:
        source = repo_root / relative
        if source.is_file():
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    built = repo_root / RELEASE_COPY_BUILT_ASSETS
    if built.is_dir():
        copy_tree(built, destination / RELEASE_COPY_BUILT_ASSETS)
    # The protected source archive travels with the release candidate; its
    # digest is recorded under protected_inputs and re-verified by the
    # packaging-host protection gate.
    archive = repo_root / SOURCE_ARCHIVE
    if archive.is_file():
        shutil.copy2(archive, destination / SOURCE_ARCHIVE)

    for item in sorted(destination.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(destination).as_posix()
        copied.add(relative)
        manifest.entries.append(
            {
                "relative_path": relative,
                "sha256": _sha256(item),
                "byte_length": item.stat().st_size,
            }
        )
    for relative in copied:
        if "verify_route" in relative:
            raise ValueError(f"internal route script leaked into release: {relative}")
    archive = repo_root / SOURCE_ARCHIVE
    manifest.protected_inputs = {
        "source_archive": {
            "present": archive.is_file(),
            "expected_sha256": (
                "12A6F2FD69ACBCBF38C286A84232C4BE64000EDAF06C61FF6D3B3E09F8995C0F"
            ),
            **({"sha256": _sha256(archive)} if archive.is_file() else {}),
        },
        "official_data": {
            "present": (repo_root / OFFICIAL_DATA).is_dir(),
            "files": (
                len(list((repo_root / OFFICIAL_DATA).rglob("*")))
                if (repo_root / OFFICIAL_DATA).is_dir()
                else 0
            ),
        },
    }
    manifest_path = destination / "release-manifest.json"
    manifest_path.write_text(manifest.to_json() + "\n", encoding="utf-8", newline="\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)
    plan_parser = sub.add_parser("plan", help="list stale generated artifacts")
    plan_parser.add_argument("--format", choices=("text", "json"), default="text")
    sub.add_parser("apply", help="move stale generated artifacts to quarantine")
    copy_parser = sub.add_parser(
        "release_copy", help="build an allowlisted release copy"
    )
    copy_parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    if args.command == "plan":
        plan = plan_cleanup(root)
        if args.format == "json":
            print(json.dumps(plan.targets, ensure_ascii=False, indent=2))
        else:
            for item in plan.targets:
                print(f"{item['path']}: {item['reason']}")
        return 0
    if args.command == "apply":
        report = apply_cleanup(plan_cleanup(root), root)
        print(
            f"moved={report.moved} missing={report.skipped_missing} "
            f"quarantine={report.quarantine_root}"
        )
        return 0
    manifest = build_release_copy(root, args.destination)
    print(
        f"entries={len(manifest.entries)} destination={args.destination.resolve()}"
    )
    return 0


if __name__ == "__main__":
    sys_exit = main()
    raise SystemExit(sys_exit)
