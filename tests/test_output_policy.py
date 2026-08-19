from pathlib import Path

import pytest

from scripts.release.output_policy import (
    audit_output_tree,
    is_release_path,
    preserved_source_paths,
)


def test_official_archive_and_scene_tree_are_always_preserved(tmp_path):
    archive = tmp_path / "赛题资料.7z"
    scene_root = tmp_path / "data" / "intersection_data"
    archive.write_bytes(b"official")
    scene_root.mkdir(parents=True)
    scene = scene_root / "intersection_1" / "network.net.xml"
    scene.parent.mkdir()
    scene.write_text("<net/>", encoding="utf-8")

    assert preserved_source_paths(tmp_path) == (archive, scene_root)
    assert is_release_path(archive) is True
    assert is_release_path(scene) is True


@pytest.mark.parametrize(
    "relative_path",
    [
        ".pytest_cache/state",
        ".venv-native/pyvenv.cfg",
        "scripts/release/__pycache__/policy.pyc",
        "node_modules/package/index.js",
        "output/tmp/frame.png",
        "output/runs/old-run/summary.json",
        "output/pytest-task/check/state",
        "experiments/results/legacy.csv",
    ],
)
def test_cache_runtime_and_personal_environment_are_not_release_paths(
    tmp_path, relative_path
):
    assert is_release_path(tmp_path / relative_path) is False


@pytest.mark.parametrize(
    "relative_path",
    [
        "docs/internal-progress.md",
        "docs/team-assignment.md",
        "docs/weekly-tasks.md",
        "docs/development-roadmap.md",
        "docs/development-route.md",
        "docs/project-division.md",
        "docs/member-code-notes.md",
        "docs/internal-verification-report.md",
        "output/evidence/verify_route_1/report.json",
        "output/evidence/legacy-route-check/report.json",
    ],
)
def test_internal_and_superseded_route_material_is_not_released(
    tmp_path, relative_path
):
    assert is_release_path(Path(relative_path)) is False


@pytest.mark.parametrize(
    "relative_path",
    [
        "README.md",
        "output/README.md",
        "output/deliverables/judge-guide.pdf",
        "output/evidence/release-baseline/README.md",
        "output/evidence/formal-matrix/summary.json",
        "scripts/start_judge.py",
    ],
)
def test_judge_facing_sources_and_current_evidence_are_release_paths(
    tmp_path, relative_path
):
    assert is_release_path(Path(relative_path)) is True


def test_audit_classifies_files_without_mutating_them(tmp_path):
    files = {
        "赛题资料.7z": b"official",
        "data/intersection_data/1/network.net.xml": b"<net/>",
        "output/evidence/formal-matrix/summary.json": b"{}",
        "output/runs/old/summary.json": b"{}",
        "docs/team-assignment.md": b"internal",
        ".pytest_cache/state": b"cache",
    }
    for relative_path, content in files.items():
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    before = {path: (tmp_path / path).read_bytes() for path in files}

    report = audit_output_tree(tmp_path)

    by_path = {item["path"]: item for item in report}
    assert by_path["赛题资料.7z"]["classification"] == "preserved"
    assert (
        by_path["data/intersection_data/1/network.net.xml"]["classification"]
        == "preserved"
    )
    assert (
        by_path["output/evidence/formal-matrix/summary.json"]["classification"]
        == "release"
    )
    assert by_path["output/runs/old/summary.json"]["classification"] == "stale"
    assert by_path["docs/team-assignment.md"]["classification"] == "internal"
    assert by_path[".pytest_cache/state"]["classification"] == "cache"
    assert all(item["reason"] for item in report)
    assert {path: (tmp_path / path).read_bytes() for path in files} == before


def test_audit_uses_only_repository_relative_paths(tmp_path):
    target = tmp_path / "output" / "deliverables" / "judge-guide.md"
    target.parent.mkdir(parents=True)
    target.write_text("guide", encoding="utf-8")

    report = audit_output_tree(tmp_path)

    assert report == [
        {
            "path": "output/deliverables/judge-guide.md",
            "classification": "release",
            "release": True,
            "preserved": False,
            "reason": "judge-facing deliverable",
        }
    ]
    assert str(tmp_path) not in str(report)
