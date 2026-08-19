"""Classify release files without deleting or rewriting repository content."""

from __future__ import annotations

from pathlib import Path

from scripts.release.preflight import SOURCE_ARCHIVE


_CACHE_COMPONENTS = frozenset(
    {
        ".git",
        ".mypy-cache",
        ".pytest-cache",
        ".ruff-cache",
        ".tox",
        ".venv",
        ".venv-native",
        "--pycache--",
        "env",
        "node_modules",
        "venv",
    }
)
_INTERNAL_MARKERS = (
    "internal-",
    "member-assignment",
    "team-assignment",
    "weekly-progress",
    "weekly-task",
)
_STALE_ROUTE_MARKERS = (
    "legacy-route",
    "old-route",
    "route-verification",
    "verify-route",
)


def preserved_source_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return source paths that release cleanup is never allowed to mutate."""
    repo_root = Path(repo_root).resolve()
    return (
        repo_root / SOURCE_ARCHIVE,
        repo_root / "data" / "intersection_data",
    )


def _normalized_parts(path: Path) -> tuple[str, ...]:
    return tuple(part.casefold().replace("_", "-") for part in path.parts)


def _contains_parts(parts: tuple[str, ...], sequence: tuple[str, ...]) -> bool:
    width = len(sequence)
    return any(parts[index : index + width] == sequence for index in range(len(parts)))


def _classification(path: Path) -> tuple[str, str]:
    parts = _normalized_parts(Path(path))
    name = Path(path).name.casefold()
    joined = "/".join(parts)

    if name == SOURCE_ARCHIVE.casefold():
        return "preserved", "official source archive"
    if _contains_parts(parts, ("data", "intersection-data")):
        return "preserved", "official intersection source data"

    if (
        any(part in _CACHE_COMPONENTS for part in parts)
        or any(part.startswith(".venv-") for part in parts)
        or name.endswith((".pyc", ".pyo"))
    ):
        return "cache", "cache or local dependency environment"

    if _contains_parts(parts, ("docs", "superpowers")) or any(
        marker in joined for marker in _INTERNAL_MARKERS
    ):
        return "internal", "internal planning or collaboration material"

    if any(marker in joined for marker in _STALE_ROUTE_MARKERS):
        return "stale", "superseded route-specific evidence"

    if _contains_parts(parts, ("experiments", "results")):
        return "stale", "legacy experiment output"
    if "output" in parts:
        output_index = parts.index("output")
        output_tail = parts[output_index + 1 :]
        if output_tail and (
            output_tail[0] in {"runs", "tmp"}
            or output_tail[0].startswith("pytest-")
        ):
            return "stale", "disposable runtime output"
        if output_tail and output_tail[0] == "deliverables":
            return "release", "judge-facing deliverable"
        if output_tail and output_tail[0] == "evidence":
            return "release", "current release evidence"
        if output_tail == ("readme.md",):
            return "release", "output ownership documentation"
        return "stale", "unclassified generated output"

    if name in {".env", ".env.local"} or name.endswith((".key", ".pem")):
        return "internal", "secret-bearing local file"

    return "release", "runtime source or judge-facing documentation"


def is_release_path(path: Path) -> bool:
    """Return whether a path is permitted in the judge-facing package."""
    classification, _ = _classification(Path(path))
    return classification in {"preserved", "release"}


def audit_output_tree(root: Path) -> list[dict[str, object]]:
    """Return a repository-relative, read-only release classification report."""
    root = Path(root).resolve()
    report: list[dict[str, object]] = []
    for path in sorted(
        (candidate for candidate in root.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root)
        classification, reason = _classification(relative)
        report.append(
            {
                "path": relative.as_posix(),
                "classification": classification,
                "release": classification in {"preserved", "release"},
                "preserved": classification == "preserved",
                "reason": reason,
            }
        )
    return report
