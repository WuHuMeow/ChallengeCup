import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.release import preflight


def _check(records, name):
    return next(item for item in records if item["check"] == name)


def test_preflight_requires_exact_sumo_version(monkeypatch, tmp_path):
    monkeypatch.setattr(preflight, "detect_sumo_version", lambda: "1.26.0")

    record = _check(preflight.run_preflight(tmp_path), "sumo_version")

    assert record["status"] == "fail"
    assert "1.27.1" in record["detail"]


def test_environment_does_not_record_personal_absolute_paths(tmp_path):
    payload = preflight.collect_environment(tmp_path)
    encoded = json.dumps(payload, ensure_ascii=False)

    assert "Users" not in encoded
    assert str(tmp_path) not in encoded
    assert "environment" in payload


def test_docker_detection_stays_not_run_without_live_verification(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(preflight.shutil, "which", lambda command: "docker.exe")

    payload = preflight.collect_environment(tmp_path)
    record = _check(preflight.run_preflight(tmp_path), "docker_cli")

    assert payload["environment"]["docker"]["status"] == "not_run"
    assert record["status"] == "not_run"


@pytest.mark.parametrize(
    ("broken_package", "expected_status"),
    [(None, "pass"), ("traci", "fail"), ("sumolib", "fail")],
)
def test_sumo_python_check_imports_both_packages(
    monkeypatch, tmp_path, broken_package, expected_status
):
    imported = []

    def import_module(name):
        imported.append(name)
        if name == broken_package:
            raise ImportError(f"broken {name}")
        return object()

    monkeypatch.setattr(preflight.importlib, "import_module", import_module)

    record = _check(preflight.run_preflight(tmp_path), "sumo_python_imports")

    assert imported == ["traci", "sumolib"]
    assert record["status"] == expected_status


def test_archive_hash_gate_rejects_non_official_bytes(tmp_path):
    (tmp_path / preflight.SOURCE_ARCHIVE).write_bytes(b"not official")

    record = _check(preflight.run_preflight(tmp_path), "source_archive")

    assert record["status"] == "fail"
    assert preflight.SOURCE_ARCHIVE_SHA256 in record["detail"]


def test_worktree_inventory_records_modified_deleted_and_untracked(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "changed.txt").write_text("old", encoding="utf-8")
    (tmp_path / "deleted.txt").write_text("deleted", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=tmp_path, check=True)
    (tmp_path / "changed.txt").write_text("new", encoding="utf-8")
    (tmp_path / "deleted.txt").unlink()
    (tmp_path / "untracked.txt").write_text("new file", encoding="utf-8")

    inventory = preflight.collect_worktree_inventory(tmp_path)
    by_path = {
        item["path"]: item
        for item in inventory["changed"] + inventory["untracked"]
    }

    assert set(by_path) == {"changed.txt", "deleted.txt", "untracked.txt"}
    assert by_path["changed.txt"]["sha256"] == hashlib.sha256(b"new").hexdigest()
    assert by_path["deleted.txt"]["sha256"] == hashlib.sha256(
        b"deleted"
    ).hexdigest()


def test_worktree_inventory_excludes_gitignored_files_inside_untracked_directory(
    tmp_path,
):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    source_dir = tmp_path / "package"
    source_dir.mkdir()
    (source_dir / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache_dir = source_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "module.pyc").write_bytes(b"cache")

    inventory = preflight.collect_worktree_inventory(tmp_path)

    assert [item["path"] for item in inventory["untracked"]] == [
        ".gitignore",
        "package/module.py",
    ]


def test_cli_writes_private_path_free_json(tmp_path):
    output = tmp_path / "evidence" / "environment.json"

    result = preflight.main(
        ["--repo-root", str(tmp_path), "--output", str(output)]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    encoded = json.dumps(payload, ensure_ascii=False)

    assert result == 0
    assert str(tmp_path) not in encoded
    assert {item["status"] for item in payload["preflight"]} <= {
        "pass",
        "fail",
        "not_run",
    }


def test_environment_records_current_python_without_executable_path(tmp_path):
    payload = preflight.collect_environment(tmp_path)["environment"]["python"]

    assert payload["version"] == ".".join(map(str, sys.version_info[:3]))
    assert "executable" not in payload
