"""Task 20 boundary tests for the judge-facing public documentation."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.release import check_docs


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _minimal_repo(root: Path) -> None:
    for relative in check_docs.PUBLIC_DOCS:
        _write(root, relative, "# 公开文档\n\n内容合规。\n")


@pytest.mark.parametrize(
    ("rule", "line"),
    [
        ("role_codes", "分工见 TL 与 IA 表格"),
        ("internal_task_docs", "详情见 docs/tasks/current-status.md"),
        ("verify_route", "运行 scripts/verify_route.py"),
        ("old_algorithm_name", "使用 --algorithm ca_maxpressure"),
        ("old_algorithm_option", "运行 --algorithm actuated --seed 1"),
        ("flow_multiplier_claim", "1.5x 流量矩阵覆盖 360 组"),
        ("unsupported_live_pass", "Docker live verification: pass"),
        ("personal_windows_path", "仓库位于 D:\\Desktop\\挑战杯项目\\challenge-cup"),
        ("quick_flag", "python scripts/run_pdf_matrix.py --quick"),
        ("steps_flag", "python scripts/run_pdf_matrix.py --steps 36000"),
        ("steps_count", "formal 矩阵以 36000 步运行"),
        ("frozen_360", "360-run 旧矩阵已完成"),
    ],
)
def test_scanner_flags_stale_wording(rule: str, line: str, tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    target = check_docs.PUBLIC_DOCS[0]
    doc = tmp_path / target
    doc.write_text(doc.read_text(encoding="utf-8") + f"\n{line}\n", encoding="utf-8")
    violations = check_docs.scan_repository(tmp_path)
    assert any(v["rule"] == rule and v["file"] == target for v in violations), violations


def test_scanner_flags_missing_public_doc(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    (tmp_path / check_docs.PUBLIC_DOCS[1]).unlink()
    violations = check_docs.scan_repository(tmp_path)
    assert any(v["rule"] == "missing_public_doc" for v in violations)


def test_scanner_flags_broken_local_link(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    target = check_docs.PUBLIC_DOCS[0]
    doc = tmp_path / target
    doc.write_text(
        doc.read_text(encoding="utf-8") + "\n[缺失](docs/nowhere.md)\n",
        encoding="utf-8",
    )
    violations = check_docs.scan_repository(tmp_path)
    assert any(v["rule"] == "broken_local_link" for v in violations)


def test_scanner_allows_external_links_and_documented_sumo_path(
    tmp_path: Path,
) -> None:
    _minimal_repo(tmp_path)
    target = check_docs.PUBLIC_DOCS[0]
    doc = tmp_path / target
    doc.write_text(
        doc.read_text(encoding="utf-8")
        + "\n[SUMO](https://www.eclipse.org/sumo/) 安装于"
        " `C:\\Program Files (x86)\\Eclipse\\Sumo`。\n",
        encoding="utf-8",
    )
    assert check_docs.scan_repository(tmp_path) == []


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _minimal_repo(tmp_path)
    assert check_docs.main(["--root", str(tmp_path)]) == 0
    doc = tmp_path / check_docs.PUBLIC_DOCS[0]
    doc.write_text(
        doc.read_text(encoding="utf-8") + "\nTODO stale verify_route\n",
        encoding="utf-8",
    )
    capsys.readouterr()
    assert check_docs.main(["--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "verify_route" in captured.out


def test_real_repository_public_docs_are_clean() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    violations = check_docs.scan_repository(repo_root)
    assert violations == []
