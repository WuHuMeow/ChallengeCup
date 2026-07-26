from pathlib import Path


def test_development_requirements_pin_test_tools():
    text = Path("requirements-dev.txt").read_text(encoding="utf-8")

    assert "-r requirements.txt" in text
    assert "pytest>=8.0,<9" in text
    assert "flake8>=7.0,<8" in text
    assert "httpx2>=2.9,<3" in text


def test_flat_layout_exposes_core_and_algorithm_modules():
    from algorithms.ca_max_pressure import CAMaxPressureAlgorithm
    from core.types import JointState, VehicleState

    assert CAMaxPressureAlgorithm is not None
    assert JointState is not None
    assert VehicleState is not None
