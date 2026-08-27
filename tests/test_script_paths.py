from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_flat_validation_scripts_resolve_repository_root():
    from scripts import batch_validate, validate_all

    assert batch_validate.ROOT == REPOSITORY_ROOT
    assert validate_all.ROOT == REPOSITORY_ROOT


def test_config_resolves_repository_root_from_flat_core():
    from core.config import Config

    Config._instance = None
    config = Config()

    assert config.path("paths.data_root") == REPOSITORY_ROOT / "data" / "intersection_data"


def test_active_docs_reference_current_verification_commands():
    deployment = (REPOSITORY_ROOT / "docs" / "deployment.md").read_text(encoding="utf-8")
    scripts = (REPOSITORY_ROOT / "scripts" / "README.md").read_text(encoding="utf-8")
    # Task 20 boundary: the public deployment guide references the
    # seconds-based matrix pipeline; internal acceptance scripts live in
    # scripts/README.md only.
    assert "scripts/run_pdf_matrix.py" in deployment
    assert "output/evidence" in deployment
    assert "scripts/verify_ia_ib.py" not in deployment
    assert "scripts/verify_ia_ib.py" in scripts


def test_authoritative_docs_include_required_validation_output_roots():
    root_readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    docs_readme = (REPOSITORY_ROOT / "docs" / "README.md").read_text(
        encoding="utf-8"
    )

    for text in (root_readme, docs_readme):
        assert "scripts/validate_all.py --output-root" in text
        assert "scripts/batch_validate.py --output-root" in text


def test_generated_reports_use_flat_document_paths():
    from scripts import batch_validate
    from scripts.verify_ia_ib import REPORT_PATH

    assert batch_validate.REPORT == REPOSITORY_ROOT / "docs" / "batch_validate_report.md"
    assert REPORT_PATH == REPOSITORY_ROOT / "docs" / "ia-ib-final-verification.md"


def _active_docs_text():
    paths = [
        "README.md",
        "docs/interface.md",
        "docs/architecture/interface.md",
        "docs/deployment.md",
        "docs/operations/deployment.md",
        "scripts/README.md",
        "tests/README.md",
        "algorithms/README.md",
    ]
    return "\n".join(
        (REPOSITORY_ROOT / path).read_text(encoding="utf-8")
        for path in paths
    )


def test_active_docs_use_run_id_artifact_layout():
    text = _active_docs_text()

    assert "s{seed}/{run_id}" in text
    assert "output_root/csv" not in text


def test_active_docs_have_pdf_api_matrix_and_offline_commands():
    text = _active_docs_text()

    assert "docs/api/postman_collection.json" in text
    assert "scripts/run_pdf_matrix.py" in text
    assert "scripts/package_offline.py" in text
    assert "--output-root" in text


def test_active_docs_do_not_call_ca_mp_mvi():
    text = _active_docs_text()

    assert "CA-MP MVI" not in text
    assert "MVI: 最大排队方向" not in text
