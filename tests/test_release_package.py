"""Task 23 tests for release-candidate verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.release import verify_package


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_release_copy(tmp_path: Path, *, with_archive: bool = False) -> Path:
    repo = tmp_path / "repo"
    (repo / "data" / "intersection_data" / "1").mkdir(parents=True)
    (repo / "data" / "intersection_data" / "1" / "demo_1.sumocfg").write_text(
        "<configuration/>", encoding="utf-8"
    )
    (repo / "scripts" / "release").mkdir(parents=True)
    (repo / "scripts" / "run_judge.py").write_text("print('judge')\n", encoding="utf-8")
    (repo / "docker").mkdir()
    (repo / "docker" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (repo / "docker" / "README.md").write_text("# docker\n", encoding="utf-8")
    (repo / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "README.md").write_text("# docs index\n", encoding="utf-8")
    (repo / "output").mkdir(exist_ok=True)
    (repo / "output" / "README.md").write_text("# output\n", encoding="utf-8")
    (repo / "algorithms").mkdir()
    (repo / "algorithms" / "registry.py").write_text("# canonical ids only\n", encoding="utf-8")
    (repo / "api" / "static" / "dist").mkdir(parents=True)
    (repo / "api" / "static" / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    (repo / "README.md").write_text("# judge release\n", encoding="utf-8")
    (repo / "docs" / "release").mkdir(parents=True)
    (repo / "docs" / "release" / "README.md").write_text("# release docs\n", encoding="utf-8")
    (repo / "docs" / "release" / "experiment-protocol.md").write_text(
        "# protocol\n", encoding="utf-8"
    )
    (repo / "docs" / "release" / "evidence-contract.md").write_text(
        "# evidence\n", encoding="utf-8"
    )
    (repo / "docs" / "release" / "algorithm-extension.md").write_text(
        "# algorithms\n", encoding="utf-8"
    )
    (repo / "docs" / "deployment.md").write_text("# deployment\n", encoding="utf-8")
    (repo / "output" / "evidence").mkdir(parents=True)
    (repo / "output" / "evidence" / "keep.txt").write_text("x", encoding="utf-8")
    (repo / "output" / "runs").mkdir()
    (repo / "output" / "runs" / "junk.txt").write_text("generated", encoding="utf-8")
    if with_archive:
        (repo / "赛题资料.7z").write_bytes(b"archive-bytes")
    from scripts.release import clean_release

    clean_release.build_release_copy(repo, tmp_path / "release")
    return tmp_path / "release"


def test_verify_release_copy_passes_on_clean_candidate(tmp_path: Path) -> None:
    release = _build_release_copy(tmp_path, with_archive=True)
    result = verify_package.verify_release_copy(release)
    assert result.ok, result.checks
    assert set(result.checks) == {
        "release_manifest",
        "manifest_hashes",
        "public_entrypoints",
        "no_internal_files",
        "no_stale_algorithms",
        "official_source_archive",
        "official_scene_data",
        "web_build_present",
        "documentation_boundary",
    }


def test_verify_release_copy_reports_absent_archive_honestly(tmp_path: Path) -> None:
    release = _build_release_copy(tmp_path, with_archive=False)
    result = verify_package.verify_release_copy(release)
    assert result.checks["official_source_archive"] == "fail"
    assert result.checks["manifest_hashes"] == "pass"


def test_verify_release_copy_detects_tampered_hash(tmp_path: Path) -> None:
    release = _build_release_copy(tmp_path)
    readme = release / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    result = verify_package.verify_release_copy(release)
    assert result.checks["manifest_hashes"] == "fail"
    assert result.details["manifest_hash_mismatches"] == ["README.md"]


def test_verify_release_copy_detects_internal_leak(tmp_path: Path) -> None:
    release = _build_release_copy(tmp_path)
    leak = release / "docs" / "tasks"
    leak.mkdir()
    (leak / "internal.md").write_text("internal", encoding="utf-8")
    result = verify_package.verify_release_copy(release)
    assert result.checks["no_internal_files"] == "fail"
    assert result.details["internal_files"] == ["docs/tasks/internal.md"]


def test_verify_release_copy_detects_stale_algorithm(tmp_path: Path) -> None:
    release = _build_release_copy(tmp_path)
    registry = release / "algorithms" / "registry.py"
    registry.write_text("OLD = 'ca_maxpressure'\n", encoding="utf-8")
    result = verify_package.verify_release_copy(release)
    assert result.checks["no_stale_algorithms"] == "fail"


def test_verify_release_copy_detects_broken_doc_boundary(tmp_path: Path) -> None:
    release = _build_release_copy(tmp_path)
    readme = release / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8") + "\n分工详见 docs/tasks/x.md\n",
        encoding="utf-8",
    )
    manifest_path = release / verify_package.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["entries"]:
        item = release / entry["relative_path"]
        if item.is_file():
            entry["sha256"] = _sha256(item)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    result = verify_package.verify_release_copy(release)
    assert result.checks["documentation_boundary"] == "fail"
