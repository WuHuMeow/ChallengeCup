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
    assert "scripts/verify_ia_ib.py" in deployment
    assert "output/verification" in deployment
    assert "scripts/verify_ia_ib.py" in scripts
