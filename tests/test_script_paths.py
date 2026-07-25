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
