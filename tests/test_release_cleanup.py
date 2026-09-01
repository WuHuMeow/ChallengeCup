"""Task 21 safety tests for recoverable cleanup and the release copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.release import clean_release


def _official_skeleton(root: Path) -> None:
    """Create a synthetic repository at ``root`` (a dedicated subdirectory)."""
    (root / "data" / "intersection_data" / "1" / "sumo工程").mkdir(parents=True)
    (root / "data" / "intersection_data" / "1" / "sumo工程" / "demo_1.sumocfg").write_text(
        "<configuration/>", encoding="utf-8"
    )
    (root / "README.md").write_text("# judge release\n", encoding="utf-8")
    (root / "requirements.txt").write_text("traci>=1.18.0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (root / "output" / "runs" / "i1" / "run1").mkdir(parents=True)
    (root / "output" / "runs" / "i1" / "run1" / "summary.json").write_text("{}", encoding="utf-8")
    (root / "output" / "tmp" / "pytest-x").mkdir(parents=True)


def test_cleanup_plan_never_targets_official_archive(tmp_path: Path) -> None:
    _official_skeleton(tmp_path)
    (tmp_path / "赛题资料.7z").write_bytes(b"archive")
    plan = clean_release.plan_cleanup(tmp_path)
    assert Path("赛题资料.7z") not in plan.target_paths
    assert all(
        "data/intersection_data" not in str(path) for path in plan.target_paths
    )
    assert Path("output/runs") in plan.target_paths


def test_cleanup_plan_skips_missing_paths_and_never_includes_official_data(
    tmp_path: Path,
) -> None:
    _official_skeleton(tmp_path)
    plan = clean_release.plan_cleanup(tmp_path)
    for target in plan.targets:
        assert target["recoverable"] is True
        assert "data/intersection_data" not in str(target["path"])


def test_apply_cleanup_quarantines_and_preserves_official_sources(
    tmp_path: Path,
) -> None:
    _official_skeleton(tmp_path)
    official_before = sorted(
        p.relative_to(tmp_path).as_posix()
        for p in (tmp_path / "data" / "intersection_data").rglob("*")
    )
    plan = clean_release.plan_cleanup(tmp_path)
    report = clean_release.apply_cleanup(plan, tmp_path)
    assert "output/runs" in report.moved and "output/tmp" in report.moved
    assert report.quarantine_root
    quarantined = tmp_path / report.quarantine_root
    assert (quarantined / "output" / "runs" / "i1" / "run1" / "summary.json").exists()
    assert not (tmp_path / "output" / "runs").exists()
    official_after = sorted(
        p.relative_to(tmp_path).as_posix()
        for p in (tmp_path / "data" / "intersection_data").rglob("*")
    )
    assert official_before == official_after


def test_apply_cleanup_refuses_protected_target(tmp_path: Path) -> None:
    plan = clean_release.CleanupPlan(
        targets=[{"path": "data/intersection_data", "reason": "x", "recoverable": True}]
    )
    with pytest.raises(ValueError, match="protected"):
        clean_release.apply_cleanup(plan, tmp_path)


def test_release_copy_excludes_internal_route_scripts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _official_skeleton(repo)
    scripts = repo / "scripts"
    (scripts / "release").mkdir(parents=True)
    (scripts / "run_judge.py").write_text("print('judge')", encoding="utf-8")
    (scripts / "release" / "__init__.py").write_text("", encoding="utf-8")
    (scripts / "release" / "clean_release.py").write_text("# tool", encoding="utf-8")
    destination = tmp_path / "release-copy"
    manifest = clean_release.build_release_copy(repo, destination)
    names = {entry["relative_path"] for entry in manifest.entries}
    assert not any("verify_route" in name for name in names)
    assert "README.md" in names
    assert "scripts/run_judge.py" in names
    assert (destination / "release-manifest.json").exists()


def test_release_copy_manifest_hashes_and_protected_status(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _official_skeleton(repo)
    destination = tmp_path / "release-copy"
    manifest = clean_release.build_release_copy(repo, destination)
    assert manifest.protected_inputs["official_data"]["present"] is True
    assert manifest.protected_inputs["source_archive"]["present"] is False
    for entry in manifest.entries:
        assert len(str(entry["sha256"])) == 64
        assert entry["byte_length"] >= 0
    on_disk = json.loads(
        (destination / "release-manifest.json").read_text(encoding="utf-8")
    )
    assert len(on_disk["entries"]) == len(manifest.entries)


def test_release_copy_refuses_destination_inside_copied_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _official_skeleton(repo)
    (repo / "algorithms").mkdir()
    with pytest.raises(ValueError, match="overlaps"):
        clean_release.build_release_copy(repo, repo / "algorithms" / "copy")


def test_release_copy_allows_gitignored_output_destination(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _official_skeleton(repo)
    destination = repo / "output" / "release-candidate"
    manifest = clean_release.build_release_copy(repo, destination)
    assert manifest.entries
